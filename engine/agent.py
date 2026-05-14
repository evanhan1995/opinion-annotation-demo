"""扫地僧 Agent —— 基于 Wiki 知识库的问答引擎。

用法:
    from engine.agent import ask_agent, search_wiki
    result = ask_agent("最近一周有多少P0案例？", config)
    pages = search_wiki("P0 严重度")
"""

import json
import re
from pathlib import Path
from typing import Optional

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"


# ═══════════════════════════════════════════════════════════════════════════════
# Wiki 搜索
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter fields from a wiki page."""
    meta = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key in ("title", "type", "severity", "action", "platform",
                               "tags", "confidence", "created", "updated"):
                        meta[key] = val
            meta["_body"] = parts[2].strip()
    if "_body" not in meta:
        meta["_body"] = content
    return meta


def _tokenize_query(query: str) -> list[str]:
    """Extract meaningful search tokens from a Chinese/English query."""
    # Split on Chinese/English script boundaries
    query = re.sub(r'([a-zA-Z0-9]+)', r' \1 ', query)
    tokens = []
    raw = re.split(r'[\s,，。！？、；：""''「」【】《》?!.;]+', query)
    for t in raw:
        t = t.strip().lower()
        if not t:
            continue
        tokens.append(t)
        # For Chinese-only text, also generate character bigrams
        # so "有多少案例" can match "案例" in files
        if re.match(r'^[一-鿿]+$', t) and len(t) >= 2:
            for i in range(len(t) - 1):
                tokens.append(t[i:i+2])
    return tokens


def search_wiki(query: str, max_results: int = 5) -> list[dict]:
    """Search wiki pages by keyword relevance.

    Returns list of dicts: {path, title, type, dirname, excerpt, score, content}
    Sorted by relevance score descending.
    """
    tokens = _tokenize_query(query)
    if not tokens:
        return []

    def _score_and_add(f: Path, dirname: str) -> None:
        """Score a single file and add to results if relevant."""
        try:
            text = f.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)

            score = 0
            title_lower = meta.get("title", "").lower()
            tags_str = meta.get("tags", "").lower()
            body_lower = meta["_body"].lower()

            for token in tokens:
                if token in title_lower:
                    score += 3
                if token in tags_str:
                    score += 2
                score += body_lower.count(token)

            if score > 0:
                excerpt = meta["_body"][:200].replace("\n", " ")
                results.append({
                    "path": f"{dirname}/{f.name}",
                    "title": meta.get("title", f.stem),
                    "type": meta.get("type", dirname),
                    "dirname": dirname,
                    "excerpt": excerpt,
                    "score": score,
                    "content": meta["_body"],
                    "frontmatter": {k: v for k, v in meta.items() if k != "_body"},
                })
        except Exception:
            pass

    results = []

    # Root wiki files (index.md, log.md) — include them for aggregate queries
    for f in WIKI_DIR.glob("*.md"):
        _score_and_add(f, "")

    # Subdirectory pages
    for dirname in ("concepts", "entities", "sources", "syntheses", "cases"):
        dir_path = WIKI_DIR / dirname
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("*.md")):
            _score_and_add(f, dirname)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


# ═══════════════════════════════════════════════════════════════════════════════
# Agent prompt builder
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """你是「扫地僧」——一个基于舆情标注知识库的智能助手。

你的知识来源是下方的 Wiki 页面。回答时遵循以下规则：
1. **基于来源回答**——只使用提供的 Wiki 页面中的信息，不要编造
2. **引用出处**——每个关键论断后标注来源页面，如 [[cases/case-001]]
3. **承认边界**——如果知识库中没有相关信息，诚实说"知识库中暂无相关记录"
4. **简洁**——直接回答问题，不铺垫，不废话
5. **结构化**——涉及多个条目时用列表或表格呈现

当前知识库包含：
- 标注规范（syntheses/）
- 概念框架（concepts/）：严重度评级、情感分析、分流判断、真实性评估、平台适配
- 案例库（cases/）：已有多个标注案例，含判据链
- 实体说明（entities/）：舆情工具介绍
- 工作复盘（sources/）：来自实际舆情工作的经验提炼
- 跨平台关联（syntheses/cross-platform-*.md）：同一事件在不同平台的讨论碎片自动聚合

跨平台查询引导：
- 当用户问"某事件在哪些平台有讨论"或"跨平台对比"时，优先查看 syntheses/ 中的跨平台关联条目
- 跨平台条目中 listed related_cases 字段会列出关联的案例，展开每个案例的平台和严重度
- 如果知识库中已有多个平台的案例但未自动关联，请如实说明各平台情况
- 回答这类问题时用表格呈现：平台 | 案例编号 | 严重度 | 摘要"""


def _load_case_summary(case_ref: str) -> str | None:
    """Load a short summary from a case file referenced by synthesis. Returns None if not found."""
    case_file = WIKI_DIR / case_ref
    if not case_file.exists():
        return None
    try:
        text = case_file.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        title = meta.get("title", case_file.stem)
        sev = meta.get("severity", "?")
        plat = meta.get("platform", "?")
        action = meta.get("action", "?")
        # Extract first meaningful paragraph after frontmatter
        body = meta.get("_body", "")
        first_para = ""
        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 20:
                first_para = line[:120]
                break
        return f"{title} | P={sev} | 平台={plat} | 分流={action} | {first_para}"
    except Exception:
        return None


def build_agent_context(results: list[dict], expand_syntheses: bool = True) -> str:
    """Assemble search results into a context block for the LLM.

    When expand_syntheses is True and a result is from syntheses/ with
    related_cases frontmatter, also load and append those case summaries.
    """
    blocks = []
    for i, r in enumerate(results):
        type_label = {
            "concepts": "概念",
            "entities": "实体",
            "sources": "来源",
            "syntheses": "规范",
            "cases": "案例",
        }.get(r["dirname"], r["type"])

        fm = r.get("frontmatter", {})
        meta_line = f"类型: {type_label}"
        if fm.get("severity"):
            meta_line += f" | 严重度: {fm['severity']}"
        if fm.get("action"):
            meta_line += f" | 分流: {fm['action']}"
        if fm.get("platform"):
            meta_line += f" | 平台: {fm['platform']}"

        blocks.append(
            f"### [{i+1}] {r['title']}\n"
            f"路径: {r['path']}\n"
            f"{meta_line}\n\n"
            f"{r['content'][:1500]}"
        )

        # Expand related cases for synthesis entries
        if expand_syntheses and r.get("dirname") == "syntheses":
            related = fm.get("related_cases", "")
            if related:
                case_refs = re.findall(r'\[\[([^\]]+)\]\]', related)
                if case_refs:
                    blocks.append("\n**关联案例详情：**")
                    for ref in case_refs:
                        summary = _load_case_summary(ref)
                        if summary:
                            blocks.append(f"- [[{ref}]]: {summary}")

    return "\n\n---\n\n".join(blocks)


# ═══════════════════════════════════════════════════════════════════════════════
# Query API
# ═══════════════════════════════════════════════════════════════════════════════

def ask_agent(
    query: str,
    config: dict,
    chat_history: Optional[list[dict]] = None,
    max_search: int = 5,
) -> dict:
    """Answer a question using the wiki knowledge base.

    Args:
        query: User's question
        config: LLM config dict (provider, api_key, model, api_base, api_style, ...)
        chat_history: Optional list of {"role": "user"|"assistant", "content": "..."}
        max_search: Max wiki pages to include as context

    Returns:
        {"answer": str, "citations": [...], "search_results": [...]}
        or {"error": True, "message": str}
    """
    # Step 1: Search
    results = search_wiki(query, max_results=max_search)
    if not results:
        return {
            "answer": "知识库中暂无与您问题相关的页面。试试换个关键词，或者先用标注功能添加一些案例。",
            "citations": [],
            "search_results": [],
        }

    # Step 2: Build prompt
    context = build_agent_context(results)

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({
        "role": "user",
        "content": f"请基于以下知识库页面回答用户的问题。\n\n"
                   f"## 知识库检索结果\n\n{context}\n\n"
                   f"## 用户问题\n\n{query}",
    })

    # Step 3: Call LLM
    api_style = config.get("api_style", "openai")
    try:
        if api_style == "anthropic":
            raw = _call_anthropic(messages, config)
        else:
            raw = _call_openai_style(messages, config)
    except Exception as e:
        return {"error": True, "message": f"Agent API 调用失败: {e}"}

    # Step 4: Build citations
    citations = [
        {"title": r["title"], "path": r["path"], "type": r["dirname"]}
        for r in results
    ]

    return {
        "answer": raw,
        "citations": citations,
        "search_results": [{"title": r["title"], "path": r["path"], "score": r["score"]} for r in results],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LLM backends
# ═══════════════════════════════════════════════════════════════════════════════

def _call_openai_style(messages: list[dict], config: dict) -> str:
    """Call OpenAI-compatible API (DeepSeek, OpenAI)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=config["api_key"],
        base_url=config.get("api_base", "https://api.deepseek.com"),
    )
    resp = client.chat.completions.create(
        model=config.get("model", "deepseek-chat"),
        messages=messages,
        max_tokens=config.get("max_tokens", 2048),
        temperature=config.get("temperature", 0.3),
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(messages: list[dict], config: dict) -> str:
    """Call Anthropic API."""
    import anthropic

    system = ""
    user_messages = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            user_messages.append(m)

    client = anthropic.Anthropic(api_key=config["api_key"])
    resp = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        system=system,
        messages=user_messages,
        max_tokens=config.get("max_tokens", 2048),
    )
    return resp.content[0].text

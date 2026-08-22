"""扫地僧 Agent —— 基于 Wiki 知识库的问答引擎。

用法:
    from engine.agent import ask_agent, search_wiki
    result = ask_agent("最近一周有多少P0案例？", config)
    pages = search_wiki("P0 严重度")
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from engine._compat import call_with_timeout
from engine.constants import PLATFORM_KEY_TO_LABEL, normalize_platform

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
                               "status", "case_id", "url", "category",
                               "tags", "confidence", "created", "updated",
                               "source_keyword"):
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


def _expand_taxonomy_tokens(tokens: list[str]) -> None:
    """Expand search tokens with matching taxonomy labels (in-place).

    If a token matches a taxonomy keyword (e.g. '食品安全'), add the
    full narrative label to boost related case recall.
    """
    try:
        from engine.taxonomy_mgr import load_taxonomy
        nt = load_taxonomy("narrative_categories")
        rt = load_taxonomy("risk_tags")
        expanded = []
        query_text = "".join(tokens)
        for tax in (nt, rt):
            for l1 in tax.nodes:
                for l2 in l1.children:
                    # Match query against L2 keywords
                    for kw in l2.keywords:
                        if kw in query_text:
                            if tax.taxonomy_type == "narrative_category":
                                expanded.append(f"{l1.name}/{l2.name}")
                            else:
                                expanded.append(l2.name)
                            break
                    # Match query against L2 name itself
                    if l2.name in query_text:
                        if tax.taxonomy_type == "narrative_category":
                            expanded.append(f"{l1.name}/{l2.name}")
                        else:
                            expanded.append(l2.name)
        # Add expanded tokens (avoid dups)
        for t in expanded:
            if t not in tokens:
                tokens.append(t)
    except Exception:
        pass  # taxonomy not available, skip expansion


def _embedding_search(query: str, max_results: int) -> list[dict] | None:
    """Try hybrid semantic+keyword search. Returns None if embeddings unavailable."""
    try:
        from engine.embeddings import EmbeddingService
        svc = EmbeddingService()
        if svc.case_count == 0:
            return None
        hybrid_results = svc.hybrid_search(query, top_k=max_results * 2)
        if not hybrid_results:
            return None
        results = []
        for hr in hybrid_results:
            p = Path(hr["path"])
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = _parse_frontmatter(text)
            # Determine dirname from path relative to WIKI_DIR
            try:
                rel = p.relative_to(WIKI_DIR)
                dirname = str(rel.parent) if rel.parent != Path(".") else ""
            except ValueError:
                dirname = ""
            excerpt = meta["_body"][:200].replace("\n", " ")
            results.append({
                "path": str(rel) if dirname else p.name,
                "title": meta.get("title", p.stem),
                "type": meta.get("type", dirname),
                "dirname": dirname,
                "excerpt": excerpt,
                "score": int(hr["score"] * 100),
                "content": meta["_body"],
                "frontmatter": {k: v for k, v in meta.items() if k != "_body"},
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:max_results]
    except Exception:
        return None


def _bigram_search(query: str, max_results: int) -> list[dict]:
    """Fallback keyword-based search using bigram token matching."""
    tokens = _tokenize_query(query)
    if not tokens:
        return []

    _expand_taxonomy_tokens(tokens)

    def _score_and_add(f: Path, dirname: str) -> None:
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
                if dirname == "cases":
                    score = int(score * 1.5)
                excerpt = meta["_body"][:200].replace("\n", " ")
                results.append({
                    "path": f"{dirname}/{f.name}" if dirname else f.name,
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

    for f in WIKI_DIR.glob("*.md"):
        _score_and_add(f, "")

    for dirname in ("concepts", "entities", "sources", "syntheses", "cases", "authors"):
        dir_path = WIKI_DIR / dirname
        if not dir_path.exists():
            continue
        glob_fn = dir_path.rglob if dirname == "cases" else dir_path.glob
        for f in sorted(glob_fn("*.md")):
            _score_and_add(f, dirname)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


_log = logging.getLogger("yuqing")


def search_wiki(query: str, max_results: int = 5) -> list[dict]:
    """Search wiki pages by hybrid semantic+keyword relevance.

    Uses embedding similarity when available, falls back to bigram token matching.
    Returns list of dicts: {path, title, type, dirname, excerpt, score, content}
    Sorted by relevance score descending. 查询里明确提到平台/严重度时，
    对命中的案例做温和元数据加权（见 _weight_search_results）。
    """
    # Phase 2: try embedding-based hybrid search first
    results = _embedding_search(query, max_results)
    if results is not None:
        if results:
            _log.info("Embedding search returned %d results for: %s", len(results), query[:80])
        return _weight_search_results(query, results)

    # Fallback: bigram keyword search (Phase 1)
    _log.info("Embedding search unavailable, falling back to bigram for: %s", query[:80])
    return _weight_search_results(query, _bigram_search(query, max_results))


# ═══════════════════════════════════════════════════════════════════════════════
# 元数据加权（查询里明确提到平台/严重度时，温和加权同平台/同严重度案例）
# ═══════════════════════════════════════════════════════════════════════════════

_SEVERITY_BOOST = 1.3
_PLATFORM_BOOST = 1.3
_SEVERITY_CODES = ("P0", "P1", "P2", "P3")


def _detect_query_severities(query: str) -> set[str]:
    """识别查询里出现的严重度代码（P0-P3），大小写不敏感。"""
    upper = query.upper()
    return {s for s in _SEVERITY_CODES if s in upper}


def _detect_query_platforms(query: str) -> set[str]:
    """识别查询里提到的平台（中英文都覆盖），返回归一化后的中文平台名集合。"""
    query_lower = query.lower()
    aliases = set(PLATFORM_KEY_TO_LABEL.keys()) | set(PLATFORM_KEY_TO_LABEL.values())
    found = set()
    for alias in aliases:
        if len(alias) >= 2 and alias.lower() in query_lower:
            found.add(normalize_platform(alias))
    return found


def _weight_search_results(query: str, results: list[dict]) -> list[dict]:
    """对 search_wiki 结果做元数据加权重排（只作用于 cases，不改动其他 wiki 内容）。

    查询里命中平台关键词 → 同平台案例 ×1.3；命中严重度代码 → 同严重度案例 ×1.3；
    两者都命中则相乘（≈1.69）。无关键词命中时原样返回，保证与改动前完全一致。
    """
    sevs = _detect_query_severities(query)
    plats = _detect_query_platforms(query)
    if not sevs and not plats:
        return results

    for r in results:
        if r.get("dirname") != "cases":
            continue
        fm = r.get("frontmatter") or {}
        factor = 1.0
        if sevs and fm.get("severity") in sevs:
            factor *= _SEVERITY_BOOST
        if plats and normalize_platform(fm.get("platform", "")) in plats:
            factor *= _PLATFORM_BOOST
        if factor != 1.0:
            r["score"] = round(r["score"] * factor, 2)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Agent prompt builder
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """你是「扫地僧」——舆情标注知识库的智能分析助手。你的用户是 PR 舆情团队，需要快速准确地从案例库中提取情报。

## 知识来源
下方会提供知识库检索结果。每个案例包含：
- 元数据行：类型 | 严重度 | 分流 | 平台 | 抓取关键词（如有）
- 原始输入：被监控内容的标题、正文、发布者
- 判据链：为何这样评级和分流
- AI 原始标注：情感、风险标签等结构化标注

## 回答规则

### 必须遵守
1. 只使用提供的知识库内容，绝不编造事实
2. 每个结论标注来源案例编号，如 [[case-001]]
3. 知识库没有的信息，直接说"知识库中暂无相关记录"，不要猜测
4. 先找证据再回答，不要凭案例标题推测

### 回答格式
- 统计类问题：先给总数，再用表格列出每个案例的关键字段
- 原因类问题：先给结论一句话，再逐案例列出证据
- 对比类问题：用表格呈现

### 关键概念
- 抓取关键词 = Monitor 监控的关键词，不是 Sentiment/SnowNLP 分值
- "[快速通道]" = Sentinel 预筛选器直接判定（跳过 LLM），不是抓取方式
- "Sentinel pre-filter" = 标注方法（快速通道），不是内容来源
- 案例的发现途径和标注途径是两个不同概念

### 禁止
- 不要把 "[Sentinel pre-filter]" 当作案例的抓取来源
- 不要把 "快速通道" 当作抓取关键词
- 不要重复每个案例的模板文字（"边界讨论""处置备注"等）

## 示例

问：这些案例是根据什么关键词抓取的？
答：所有 17 个案例的抓取关键词均为「爱数伴」。

| 案例 | 平台 | 抓取关键词 | 标注方式 |
|------|------|-----------|----------|
| [[case-001]] | 抖音 | 爱数伴 | 快速通道 |
| [[case-002]] | 抖音 | 爱数伴 | LLM 标注 |
| [[case-003]] | 抖音 | 爱数伴 | 快速通道 |

问：最近一周有多少 P0/P1 案例？
答：最近一周共有 X 个案例，其中 P0 0 个、P1 Y 个、P2 Z 个、P3 W 个。[表格列出 P0/P1 案例详情]

问：抖音平台的情感分布如何？
答：抖音平台共 N 个案例。正面 X 个 (X%)，中性 Y 个 (Y%)，负面 Z 个 (Z%)。[表格]"""


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


def _extract_key_sections(content: str) -> str:
    """Extract only key sections from a case page, skipping boilerplate.

    Removes 边界讨论, 处置备注, 对标注规范的影响 — template text that
    is identical across cases and wastes ~40% of LLM context.
    """
    # Split on ## headers
    sections = re.split(r'\r?\n(?=## )', content)
    kept = []
    skip_prefixes = ('## 边界讨论', '## 处置备注', '## 对标注规范的影响')

    for section in sections:
        if not section.startswith(skip_prefixes):
            # Trim section content to avoid per-section bloat
            if section.startswith('## 原始输入') and len(section) > 600:
                section = section[:600] + "\n[...]"
            elif section.startswith('## AI 原始标注'):
                # Keep full JSON block — it's structured and compact
                pass
            elif section.startswith('## 判据链') and len(section) > 500:
                section = section[:500] + "\n[...]"
            kept.append(section)

    return "\n".join(kept)


def build_agent_context(results: list[dict], expand_syntheses: bool = True) -> str:
    """Assemble search results into a context block for the LLM.

    For case entries: strips boilerplate sections (边界讨论, 处置备注,
    对标注规范的影响) and limits raw content to key sections only.
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
            "authors": "作者",
        }.get(r["dirname"], r["type"])

        fm = r.get("frontmatter", {})
        meta_line = f"类型: {type_label}"
        if fm.get("severity"):
            meta_line += f" | 严重度: {fm['severity']}"
        if fm.get("action"):
            meta_line += f" | 分流: {fm['action']}"
        if fm.get("platform"):
            meta_line += f" | 平台: {fm['platform']}"
        if fm.get("source_keyword"):
            meta_line += f" | 抓取关键词: {fm['source_keyword']}"

        # Strip boilerplate sections for case pages
        content = r.get("content", "")
        if r.get("dirname") == "cases" and content:
            content = _extract_key_sections(content)

        blocks.append(
            f"### [{i+1}] {r['title']}\n"
            f"路径: {r['path']}\n"
            f"{meta_line}\n\n"
            f"{content[:2000]}"
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
# Query helpers
# ═══════════════════════════════════════════════════════════════════════════════

_STATS_KEYWORDS = [
    "多少", "几个", "统计", "分布", "大部分", "占比", "比例",
    "数量", "汇总", "哪些", "什么状态", "情况如何", "怎么样",
    "有多少", "几件", "几条", "几个平台", "现状",
]


def _is_stats_query(query: str) -> bool:
    return any(kw in query for kw in _STATS_KEYWORDS)


def _build_search_stats(results: list[dict]) -> str:
    """Build a structured stats summary from case files in search results."""
    case_results = [r for r in results if r.get("dirname") == "cases"]
    if len(case_results) < 2:
        return ""

    status_counts: dict[str, int] = {}
    sev_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}

    for r in case_results:
        fm = r.get("frontmatter", {})
        st = fm.get("status", "?")
        sev = fm.get("severity", "?")
        pf = fm.get("platform", "?")
        status_counts[st] = status_counts.get(st, 0) + 1
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        platform_counts[pf] = platform_counts.get(pf, 0) + 1

    lines = [
        f"\n## 📊 搜索命中案例统计（共命中 {len(case_results)} 个案例）\n",
        f"- 状态分布: {', '.join(f'{k} {v}条' for k, v in sorted(status_counts.items(), key=lambda x: -x[1]))}",
        f"- 严重度分布: {', '.join(f'{k} {v}条' for k, v in sorted(sev_counts.items()))}",
        f"- 平台分布: {', '.join(f'{k} {v}条' for k, v in sorted(platform_counts.items(), key=lambda x: -x[1]))}",
        "",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Query API
# ═══════════════════════════════════════════════════════════════════════════════

def answer_from_search_only(query: str, results: list[dict] | None = None) -> dict:
    """LLM 失败降级：直接拼接检索结果，不调 LLM 总结/解释。

    复用 search_wiki（bigram/embedding 检索）+ build_agent_context 的格式化，
    返回带 degraded=True 标记的回答，供 UI 提示「模型暂不可用、结果未经 AI 总结」。
    """
    if results is None:
        results = search_wiki(query, max_results=15)
    if not results:
        return {
            "answer": "知识库中暂无与您问题相关的页面。",
            "citations": [], "search_results": [], "degraded": True,
        }
    body = build_agent_context(results)
    answer = f"⚠️ 模型暂不可用，以下为知识库检索结果（未做 AI 总结）：\n\n{body}"
    citations = [{"title": r["title"], "path": r["path"], "type": r["dirname"]} for r in results]
    return {
        "answer": answer,
        "citations": citations,
        "search_results": [{"title": r["title"], "path": r["path"], "score": r["score"]} for r in results],
        "degraded": True,
    }


def ask_agent(
    query: str,
    config: dict,
    chat_history: Optional[list[dict]] = None,
    max_search: int = 15,
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

    # Inject structured stats for aggregate queries (counts, distributions, etc.)
    if _is_stats_query(query):
        stats_block = _build_search_stats(results)
        if stats_block:
            context = stats_block + "\n---\n" + context

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({
        "role": "user",
        "content": f"请基于以下知识库页面回答用户的问题。\n\n"
                   f"## 知识库检索结果\n\n{context}\n\n"
                   f"## 用户问题\n\n{query}",
    })

    # Step 3: Call LLM — use reasoning model for agent Q&A
    agent_config = dict(config)
    agent_config["model"] = config.get("agent_model", "deepseek-reasoner")
    api_style = config.get("api_style", "openai")
    try:
        if api_style == "anthropic":
            raw = _call_anthropic(messages, agent_config)
        else:
            raw = _call_openai_style(messages, agent_config)
    except Exception as e:
        # 降级：LLM 失败 → 直接拼接 bigram/embedding 检索结果（不调 LLM 总结）
        from engine.model_degradation import record_llm_failure
        record_llm_failure("curator", str(e))
        _log.warning("Agent LLM 调用失败，降级为检索回答: %s", e)
        return answer_from_search_only(query, results)
    from engine.model_degradation import record_llm_success
    record_llm_success("curator")

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

    def _call():
        return client.chat.completions.create(
            model=config.get("model", "deepseek-chat"),
            messages=messages,
            max_tokens=config.get("max_tokens", 2048),
            temperature=config.get("temperature", 0.3),
            timeout=90,
        )

    resp, err = call_with_timeout(_call, 90)
    if err:
        return f"[Agent API 错误: {err}]"
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

    def _call():
        return client.messages.create(
            model=config.get("model", "claude-sonnet-4-6"),
            system=system,
            messages=user_messages,
            max_tokens=config.get("max_tokens", 2048),
            timeout=90,
        )

    resp, err = call_with_timeout(_call, 90)
    if err:
        return f"[Agent API 错误: {err}]"
    return resp.content[0].text

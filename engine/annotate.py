#!/usr/bin/env python3
"""舆情标注引擎 —— 加载 Wiki 知识库，调用 LLM API，对舆情内容进行结构化标注。

用法:
    python annotate.py --input example_input.json                    # 输出到 stdout
    python annotate.py --input example_input.json --output result.json  # 输出到文件
    python annotate.py --input example_input.json --dry-run          # 预览而不调用 API
    python annotate.py --input batch.json --output batch_results.json   # 批量处理
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Windows 终端 UTF-8 编码适配
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════════════════════════

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CONFIG_PATH = ENGINE_DIR / "config.json"

# 系统提示词固定层（案例层由 _get_relevant_case_layers() 按内容相关性动态选择）
_FIXED_PROMPT_LAYERS = [
    ("core",       "syntheses/opinion-annotation-spec.md"),
    ("concept",    "concepts/severity-rating-matrix.md"),
    ("concept",    "concepts/sentiment-analysis-dimensions.md"),
    ("concept",    "concepts/public-opinion-triaging.md"),
    ("concept",    "concepts/content-authenticity-assessment.md"),
    ("concept",    "concepts/platform-adaptation.md"),
]

MAX_CASE_LAYERS = 5  # Relevance-based: fewer but more targeted cases


def _tokenize_for_search(text: str) -> list[str]:
    """Extract search tokens from content for case matching.
    Chinese bigrams + English words + platform/product names.
    """
    tokens = []
    # English tokens
    for t in re.findall(r'[a-zA-Z0-9]+', text):
        t_lower = t.lower()
        if len(t_lower) >= 2 and t_lower not in ("http", "https", "www", "com"):
            tokens.append(t_lower)
    # Chinese bigrams
    chinese = re.findall(r'[一-鿿]+', text)
    for segment in chinese:
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
    return tokens


def _score_case_file(filepath: Path, tokens: list[str]) -> int:
    """Score a case file against search tokens. Higher = more relevant."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return 0
    score = 0
    text_lower = text.lower()
    # Title match (first line after frontmatter or frontmatter title)
    parts = text.split("---", 2)
    fm = parts[1] if len(parts) >= 3 else ""
    body = parts[2] if len(parts) >= 3 else text
    body_lower = body.lower()
    for token in tokens:
        if token in fm.lower():
            score += 3
        score += body_lower.count(token)
    return score


def _get_relevant_case_layers(user_content: str) -> list[tuple[str, str]]:
    """Select top cases by content relevance instead of recency."""
    cases_dir = WIKI_DIR / "cases"
    if not cases_dir.exists() or not user_content:
        return []

    tokens = _tokenize_for_search(user_content)
    if not tokens:
        return []

    scored = []
    for f in cases_dir.glob("case-*.md"):
        s = _score_case_file(f, tokens)
        if s > 0:
            scored.append((s, f))

    scored.sort(key=lambda x: -x[0])
    return [("case", f"cases/{f.name}") for _, f in scored[:MAX_CASE_LAYERS]]


def _get_prompt_layers(user_content: str = "") -> list[tuple[str, str]]:
    """Build prompt layers: fixed concepts + content-relevant cases.
    Falls back to newest-first when no user_content provided.
    """
    if user_content:
        return _FIXED_PROMPT_LAYERS + _get_relevant_case_layers(user_content)
    return _FIXED_PROMPT_LAYERS + _get_relevant_case_layers("")

PLATFORM_LIST = [
    "小红书", "YouTube", "Instagram", "TikTok", "X", "X (Twitter)", "Twitter",
    "Reddit", "新闻媒体", "论坛", "其他"
]

CATEGORY_OPTIONS = [
    "商品问题", "商品侵权问题", "售后问题", "数据泄露", "软件问题", "其他"
]

# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def strip_yaml_frontmatter(text: str) -> str:
    """去除 YAML frontmatter（--- ... ---），返回正文。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。混合中英文：中文字符≈1.5 token，英文≈0.25 token。"""
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    total_chars = len(text)
    other_chars = total_chars - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.3)


def extract_json_from_response(text: str) -> str:
    """从 LLM 响应中提取 JSON。支持 markdown 代码块包裹。"""
    text = text.strip()
    # 尝试 ```json ... ``` 包裹
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试 { ... } 直接匹配
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        return m.group(0).strip()
    return text


def redact_key(key: str) -> str:
    """脱敏显示 API key（仅显示前6后4字符）。"""
    if not key or len(key) < 12:
        return "***"
    return key[:6] + "..." + key[-4:]


# ═══════════════════════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════════════════════

# Provider 注册表
PROVIDER_DEFAULTS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com",
        "api_style": "openai",  # OpenAI-compatible
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-4-6",
        "api_base": "https://api.anthropic.com",
        "api_style": "anthropic",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o",
        "api_base": "https://api.openai.com/v1",
        "api_style": "openai",
    },
}


def load_config():
    """加载配置：环境变量 > config.json。自动检测 provider。"""
    file_config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            file_config = json.load(f)

    provider = file_config.get("provider", "deepseek")
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])

    config = {
        "provider": provider,
        "api_key": os.environ.get(defaults["api_key_env"], file_config.get("api_key", "")),
        "model": file_config.get("model", defaults["model"]),
        "api_base": file_config.get("api_base", defaults["api_base"]),
        "api_style": defaults["api_style"],
        "max_tokens": file_config.get("max_tokens", 4096),
        "temperature": file_config.get("temperature", 0.1),
        "kb_password": file_config.get("kb_password", ""),
    }

    return config


# ═══════════════════════════════════════════════════════════════════════════════
# 知识库加载
# ═══════════════════════════════════════════════════════════════════════════════

def build_system_prompt(user_content: str = "") -> tuple[str, dict]:
    """遍历 wiki/ 目录，按层级组装系统提示词。返回 (完整提示词, 各层级统计)。

    Args:
        user_content: 待标注的原文内容，用于相关性案例筛选。
                      空字符串时使用全量案例（向后兼容 CLI 模式）。
    """
    layers_content = {}
    stats = {"layers": {}, "total_chars": 0, "total_estimated_tokens": 0}

    for layer_name, rel_path in _get_prompt_layers(user_content):
        file_path = WIKI_DIR / rel_path
        if not file_path.exists():
            stats["layers"][rel_path] = {"status": "missing", "chars": 0, "tokens": 0}
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()

        body = strip_yaml_frontmatter(raw)
        layers_content[rel_path] = body
        tokens = estimate_tokens(body)
        stats["layers"][rel_path] = {
            "status": "loaded",
            "chars": len(body),
            "tokens": tokens,
        }

    # 组装角色指令
    role_instruction = """你是资深舆情分析师。对每一条输入的舆情内容，严格遵循下方的标注规范和案例库完成：

1. 舆情分类(可多选: 商品问题/商品侵权问题/售后问题/数据泄露/软件问题/其他) → 2. 多维度情感分析 → 3. 严重度评级(P0-P3) → 4. 分流建议 → 5. 真实性评估 → 6. 摘要+风险标签 → 7. 评论区分析（如有评论数据）

核心原则：
- 宁可误报，不可漏报——对高敏内容保持低阈值
- 判断必须附理由——每个标签背后有原文证据
- 不确定时升一级——P1/P2 边界模糊时，按 P1 处理
- 规则来自案例——当遇到规则未覆盖的情况时，寻找最相似已有案例
- P0红线优先标注——识别到红线先标P0，再补全其余字段

## 评论区分析（如有评论数据）

对评论列表逐条进行情感判断，以红绿灯形式呈现：
- 红色(负面)：批评、抱怨、攻击品牌/产品、劝退他人购买
- 黄色(中性)：提问、客观讨论、无关内容、语气模糊
- 绿色(正面)：推荐、维护品牌、分享正面体验、反驳负面评论

在标注 JSON 中增加 "评论区分析" 字段：
```
{
  "评论红绿灯": {"红": N, "黄": N, "绿": N},
  "评论详情": [
    {"序号": 1, "内容": "评论原文", "情感": "正面|中性|负面", "关键短语": "判断依据"},
    ...
  ],
  "评论总结": "一句话概括前排评论整体风向（≤60字）"
}
```

## 舆情问题分类

根据原文内容的问题性质，从以下类别中选择适用的分类（可多选）：
- 商品问题：产品质量缺陷、功能故障、性能不达标、商品与描述不符
- 商品侵权问题：专利/商标/版权侵权指控、仿冒品、设计抄袭
- 售后问题：客服体验差、退换货难、维修纠纷、物流配送投诉
- 数据泄露：用户隐私泄露、数据安全事件、未授权数据收集
- 软件问题：App/固件Bug、系统稳定性、兼容性问题、更新故障
- 其他：不属以上类别的舆情内容

在标注 JSON 中增加 "舆情分类" 字段，值为一个数组（可多选）。如不确定，选最接近的一个。

输出纯 JSON，不要包含 markdown 代码块标记，不要包含额外解释文字。"""

    # 按层级拼接
    core_content = layers_content.get("syntheses/opinion-annotation-spec.md", "")
    concept_pages = "\n\n---\n\n".join(
        layers_content[r] for _, r in _get_prompt_layers() if r.startswith("concepts/") and r in layers_content
    )
    case_pages = "\n\n---\n\n".join(
        layers_content[r] for _, r in _get_prompt_layers() if r.startswith("cases/") and r in layers_content
    )

    full_prompt = f"""{role_instruction}

---

# 标注规范（核心）
{core_content}

---

# 概念框架（决策依据）
{concept_pages}

---

# 案例库（校准基准）
{case_pages}"""

    stats["total_chars"] = len(full_prompt)
    stats["total_estimated_tokens"] = estimate_tokens(full_prompt)
    return full_prompt, stats


# ═══════════════════════════════════════════════════════════════════════════════
# 输入处理
# ═══════════════════════════════════════════════════════════════════════════════

def load_input(path: str) -> dict:
    """加载输入文件，返回 {"mode": "single"|"batch", "items": [...]}。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return {"mode": "batch", "items": data}
    if isinstance(data, dict) and "items" in data:
        return {"mode": "batch", "items": data["items"]}
    return {"mode": "single", "items": [data]}


def validate_item(item: dict, index: int = 0) -> list[str]:
    """验证单条输入，返回 warning 列表。"""
    warnings = []
    prefix = f"[#{index + 1}] " if index > 0 else ""

    if not item.get("原文内容", "").strip():
        warnings.append(f"{prefix}缺少必填字段：原文内容")

    platform = item.get("来源平台", "")
    if platform and platform not in PLATFORM_LIST:
        warnings.append(f"{prefix}来源平台 '{platform}' 不在已知列表中，API 仍可处理但建议使用标准名称")

    return warnings


def format_user_message(item: dict) -> str:
    """将单条舆情输入格式化为 user message（含评论区数据）。"""
    fields = {
        "原文内容": item.get("原文内容", ""),
        "来源平台": item.get("来源平台", "未知"),
        "发布者类型": item.get("发布者类型", "未知"),
        "互动数据": item.get("互动数据", "暂无"),
        "发布时间": item.get("发布时间", "未知"),
        "原文链接": item.get("原文链接", ""),
    }

    lines = ["请按照标注规范对以下舆情内容进行完整标注。", "", "## 输入信息", ""]
    for label, value in fields.items():
        lines.append(f"- **{label}**：{value}")

    # 评论区数据
    comments = item.get("评论列表", [])
    if comments:
        lines.append("")
        lines.append("## 评论区（前10条）")
        lines.append("")
        for c in comments:
            text = c.get("内容", c) if isinstance(c, dict) else str(c)
            likes = c.get("点赞", "") if isinstance(c, dict) else ""
            like_str = f" (赞:{likes})" if likes and likes != "0" else ""
            lines.append(f"- {text[:200]}{like_str}")

    lines.append("")
    lines.append("请严格按照标注规范的 JSON Schema 输出完整标注结果（含舆情分类和评论区分析，舆情分类从[商品问题,商品侵权问题,售后问题,数据泄露,软件问题,其他]中选择）。只输出 JSON，不要包含其他文字。")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# API 调用
# ═══════════════════════════════════════════════════════════════════════════════

def _annotate_openai_style(user_message: str, system_prompt: str, config: dict) -> dict:
    """通过 OpenAI 兼容接口调用（DeepSeek、OpenAI 等）。"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": True, "message": "缺少 openai 库。请运行：pip install openai"}

    client = OpenAI(api_key=config["api_key"], base_url=config["api_base"])

    try:
        response = client.chat.completions.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
            timeout=90,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        raw_text = response.choices[0].message.content
        json_text = extract_json_from_response(raw_text)

        try:
            result = json.loads(json_text)
            result["_meta"] = {
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
            }
            return result
        except json.JSONDecodeError:
            return {
                "error": True,
                "message": "API 返回内容无法解析为 JSON",
                "raw_response": raw_text,
            }

    except Exception as e:
        return {"error": True, "message": f"API 错误: {e}"}


def _annotate_anthropic(user_message: str, system_prompt: str, config: dict) -> dict:
    """通过 Anthropic 原生接口调用。"""
    try:
        import anthropic
    except ImportError:
        return {"error": True, "message": "缺少 anthropic 库。请运行：pip install anthropic"}

    client = anthropic.Anthropic(api_key=config["api_key"])

    try:
        response = client.messages.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text
        json_text = extract_json_from_response(raw_text)

        try:
            result = json.loads(json_text)
            result["_meta"] = {
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }
            return result
        except json.JSONDecodeError:
            return {
                "error": True,
                "message": "API 返回内容无法解析为 JSON",
                "raw_response": raw_text,
            }

    except Exception as e:
        return {"error": True, "message": f"API 错误: {e}"}


def annotate_one_stream(user_message: str, system_prompt: str, config: dict):
    """流式标注生成器。逐 chunk 返回进度，最后返回完整结果。

    Yields:
        {"type": "progress", "chars": int} — 实时进度
        {"type": "result", "data": dict}  — 最终结果（含 _meta）
    """
    api_key = config.get("api_key", "")
    if not api_key:
        yield {"type": "result", "data": {
            "error": True,
            "message": "未配置 API Key。请在侧边栏加载知识库或设置环境变量。",
        }}
        return

    api_style = config.get("api_style", "openai")
    if api_style == "anthropic":
        # Anthropic streaming NYI, fall back to non-streaming
        result = _annotate_anthropic(user_message, system_prompt, config)
        yield {"type": "result", "data": result}
        return

    try:
        from openai import OpenAI
    except ImportError:
        yield {"type": "result", "data": {
            "error": True, "message": "缺少 openai 库。",
        }}
        return

    client = OpenAI(api_key=api_key, base_url=config["api_base"])

    try:
        stream = client.chat.completions.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
            timeout=90,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )

        accumulated = []
        char_count = 0
        last_yield = 0
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                accumulated.append(text)
                char_count += len(text)
                # Yield progress every ~100 chars to avoid spamming
                if char_count - last_yield >= 100:
                    yield {"type": "progress", "chars": char_count}
                    last_yield = char_count

        raw_text = "".join(accumulated)
        json_text = extract_json_from_response(raw_text)
        result = json.loads(json_text)
        result["_meta"] = {
            "model": config["model"],
            "streamed": True,
            "output_chars": char_count,
        }
        yield {"type": "result", "data": result}

    except json.JSONDecodeError:
        yield {"type": "result", "data": {
            "error": True,
            "message": "API 返回内容无法解析为 JSON",
            "raw_response": raw_text if 'raw_text' in dir() else "",
        }}
    except Exception as e:
        yield {"type": "result", "data": {"error": True, "message": f"API 错误: {e}"}}


def annotate_one(user_message: str, system_prompt: str, config: dict) -> dict:
    """调用 LLM API 对单条舆情进行标注（自动选择 provider）。"""
    api_key = config.get("api_key", "")
    if not api_key:
        provider = config.get("provider", "deepseek")
        info = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
        return {
            "error": True,
            "message": (
                f"未配置 {provider.upper()} API Key。请通过以下任一方式设置：\n"
                f'  1. 环境变量：set {info["api_key_env"]}=你的key  (Windows)\n'
                f'  2. 在 engine/config.json 中填写 "api_key" 字段\n'
                f"  Provider: {provider} | API Base: {info['api_base']}"
            ),
        }

    api_style = config.get("api_style", "openai")
    if api_style == "anthropic":
        return _annotate_anthropic(user_message, system_prompt, config)
    else:
        return _annotate_openai_style(user_message, system_prompt, config)


# ═══════════════════════════════════════════════════════════════════════════════
# 输出
# ═══════════════════════════════════════════════════════════════════════════════

def output_results(results: list[dict], output_path: str | None, input_mode: str):
    """输出标注结果到文件或 stdout。"""
    if input_mode == "single":
        output_data = results[0]
    else:
        output_data = {"count": len(results), "results": results}

    json_str = json.dumps(output_data, ensure_ascii=False, indent=2)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\n结果已保存至: {output_path.resolve()}")
    else:
        print("\n" + "=" * 60)
        print(json_str)


# ═══════════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="舆情标注引擎 —— 基于 Wiki 知识库 + LLM API 的智能舆情打标工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python annotate.py --input example_input.json                    # 标注并打印到终端
  python annotate.py --input example_input.json --output res.json  # 标注并保存
  python annotate.py --input example_input.json --dry-run          # 预览知识库而不调用 API
  python annotate.py --input batch.json --output batch_res.json    # 批量标注
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", "-o", default=None, help="输出 JSON 文件路径（缺省输出到 stdout）")
    parser.add_argument("--dry-run", action="store_true", help="仅加载知识库和解析输入，不调用 API")
    parser.add_argument("--show-prompt", action="store_true", help="dry-run 时打印完整 system prompt")
    args = parser.parse_args()

    # 加载配置
    config = load_config()
    api_key = config.get("api_key", "")

    # 加载知识库
    print("正在加载 Wiki 知识库...", end=" ", flush=True)
    system_prompt, kb_stats = build_system_prompt()
    loaded = sum(1 for v in kb_stats["layers"].values() if v["status"] == "loaded")
    total = len(kb_stats["layers"])
    est_tokens = kb_stats["total_estimated_tokens"]
    print(f"完成 ({loaded}/{total} 页面, 估算 ~{est_tokens} tokens)")

    if loaded == 0:
        print("错误: 未能加载任何 wiki 页面。请检查 wiki/ 目录是否存在。")
        sys.exit(1)

    # 加载输入
    try:
        input_data = load_input(args.input)
    except FileNotFoundError:
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: 输入文件 JSON 解析失败: {e}")
        sys.exit(1)

    items = input_data["items"]
    input_mode = input_data["mode"]
    print(f"输入模式: {input_mode}, 共计 {len(items)} 条")

    # 验证输入
    for i, item in enumerate(items):
        for w in validate_item(item, i if len(items) > 1 else -1):
            print(f"  [WARN] {w}")

    # Dry-run 模式
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN 模式 —— 不调用 API")
        print("=" * 60)
        print(f"\n[配置]")
        print(f"  Provider: {config['provider']}")
        print(f"  API Base: {config['api_base']}")
        print(f"  Model: {config['model']}")
        print(f"  Max Tokens: {config['max_tokens']}")
        print(f"  Temperature: {config['temperature']}")
        print(f"  API Key: {'已配置 (' + redact_key(api_key) + ')' if api_key else '[FAIL] 未配置'}")

        print(f"\n[知识库]")
        for rel_path, info in kb_stats["layers"].items():
            status = "[OK]" if info["status"] == "loaded" else "✗ (缺失)"
            print(f"  {status}  {rel_path}  ({info['chars']} 字符, ~{info['tokens']} tokens)")
        print(f"\n  总计: {kb_stats['total_chars']} 字符, ~{kb_stats['total_estimated_tokens']} tokens")

        print(f"\n[输入预览]")
        for i, item in enumerate(items):
            content_preview = item.get("原文内容", "")[:120]
            print(f"  [{i + 1}] 平台={item.get('来源平台', '?')}  "
                  f"发布者={item.get('发布者类型', '?')[:30]}  "
                  f"内容前120字: {content_preview}...")

        if args.show_prompt:
            print("\n" + "=" * 60)
            print("[完整 System Prompt]")
            print("=" * 60)
            print(system_prompt)

        print("\n[OK] Dry-run 完成。确认无误后去掉 --dry-run 执行正式标注。")
        return

    # 正式标注
    if not api_key:
        provider = config.get("provider", "deepseek")
        info = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
        print(f"\n[FAIL] 未配置 {provider.upper()} API Key，无法执行正式标注。")
        print(f"   请通过以下方式设置：")
        print(f"   1. 环境变量：set {info['api_key_env']}=你的key")
        print(f"   2. 或在 engine/config.json 中填写 api_key 字段")
        print(f"   提示：先用 --dry-run 预览知识库加载效果。")
        sys.exit(1)

    print(f"\n开始标注 (模型: {config['model']})...")
    results = []
    for i, item in enumerate(items):
        label = f"[{i + 1}/{len(items)}]" if len(items) > 1 else ""
        print(f"  {label} 处理中...", end=" ", flush=True)

        user_msg = format_user_message(item)
        result = annotate_one(user_msg, system_prompt, config)

        if result.get("error"):
            print(f"[FAIL] {result.get('message', '未知错误')}")
        else:
            severity = result.get("严重度评级", "?")
            action = result.get("分流建议", "?")
            tokens = result.get("_meta", {}).get("usage", {})
            print(f"[OK] P={severity} 分流={action}  "
                  f"(in:{tokens.get('input_tokens','?')} out:{tokens.get('output_tokens','?')})")

        results.append(result)

    # 输出
    output_results(results, args.output, input_mode)

    # 汇总
    errors = sum(1 for r in results if r.get("error"))
    success = len(results) - errors
    print(f"\n完成: {success}/{len(results)} 条成功" + (f", {errors} 条失败" if errors else ""))


# ═══════════════════════════════════════════════════════════════════════════════
# Annotation history & diff
# ═══════════════════════════════════════════════════════════════════════════════

_OUTPUTS_DIR = PROJECT_DIR / "outputs"


def _load_output_file(filepath: Path) -> dict | None:
    """Load a single annotation output file. Returns None on failure."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_annotation_history(url: str) -> list[dict]:
    """Find all annotation outputs for a given URL, newest first.

    Returns list of {file, date, annotation, scraped} dicts.
    """
    if not url or not _OUTPUTS_DIR.exists():
        return []
    history = []
    for f in sorted(_OUTPUTS_DIR.glob("*_annotation.json"), reverse=True):
        payload = _load_output_file(f)
        if not payload:
            continue
        scraped = payload.get("scraped_data", {})
        annotation = payload.get("annotation_result", {})
        if scraped.get("原文链接") == url:
            history.append({
                "file": f.name,
                "date": f.stem.split("_")[0] if "_" in f.stem else "",
                "annotation": {k: v for k, v in annotation.items() if k != "_meta"},
                "scraped": scraped,
            })
    return history


_FIELDS_TO_DIFF = [
    ("严重度评级", "严重度"),
    ("分流建议", "分流"),
    ("摘要", "摘要"),
    ("严重度理由", "严重度理由"),
    ("分流理由", "分流理由"),
    ("风险标签", "风险标签"),
]


def diff_annotations(old: dict, new: dict) -> list[dict]:
    """Compare two annotation results, return list of changed fields.

    Each diff: {field, label, old_value, new_value}
    """
    diffs = []
    for field, label in _FIELDS_TO_DIFF:
        ov = old.get(field)
        nv = new.get(field)
        if ov != nv:
            diffs.append({"field": field, "label": label, "old_value": ov, "new_value": nv})
    # Sentiment
    old_sent = old.get("情感分析", {}).get("整体情感", "")
    new_sent = new.get("情感分析", {}).get("整体情感", "")
    if old_sent != new_sent:
        diffs.append({"field": "情感分析.整体情感", "label": "情感", "old_value": old_sent, "new_value": new_sent})
    # Comment traffic lights
    old_tl = old.get("评论区分析", {}).get("评论红绿灯", {})
    new_tl = new.get("评论区分析", {}).get("评论红绿灯", {})
    if old_tl != new_tl:
        diffs.append({"field": "评论区红绿灯", "label": "评论红绿灯",
                       "old_value": f"红{old_tl.get('红','?')}/黄{old_tl.get('黄','?')}/绿{old_tl.get('绿','?')}",
                       "new_value": f"红{new_tl.get('红','?')}/黄{new_tl.get('黄','?')}/绿{new_tl.get('绿','?')}"})
    return diffs


def find_similar_cases(tags: list[str], top_k: int = 3) -> list[dict]:
    """Scan wiki/cases/ for cases with tag overlap. Returns top_k matches sorted by hits."""
    cases_dir = WIKI_DIR / "cases"
    if not cases_dir.exists() or not tags:
        return []
    tags_lower = [t.lower() for t in tags]
    scored = []
    for f in sorted(cases_dir.glob("case-*.md")):
        try:
            text = f.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            if len(parts) < 3:
                continue
            fm = parts[1]
            m = re.search(r'tags:\s*\[(.*?)\]', fm)
            if not m:
                continue
            case_tags = [t.strip().strip("'\"") for t in m.group(1).split(",")]
            hits = sum(1 for ct in case_tags if any(tl in ct.lower() for tl in tags_lower))
            if hits > 0:
                title_m = re.search(r'title:\s*(.+)', fm)
                sev_m = re.search(r'severity:\s*(\S+)', fm)
                scored.append({
                    "filename": f.name,
                    "title": title_m.group(1).strip() if title_m else f.stem,
                    "severity": sev_m.group(1) if sev_m else "?",
                    "hits": hits,
                })
        except Exception:
            continue
    scored.sort(key=lambda x: -x["hits"])
    return scored[:top_k]


if __name__ == "__main__":
    main()

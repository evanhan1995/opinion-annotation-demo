"""纠偏处理器 —— 对比 AI 标注 vs 人工修正，自动生成 Wiki 校准案例。

当用户在 Web UI 中修正 AI 的标注结果时，此模块负责：
1. 对比差异，判断是否需要生成新案例
2. 自动创建 case-XXX.md 写入 wiki/cases/
3. 更新 wiki/cases/index.md 案例库索引
4. 更新 wiki/log.md 操作日志

差异等级：
- significant: 严重度或分流建议不同 → 生成新案例
- minor: 仅文字微调 → 仅记录日志
"""

import json
import re
from datetime import datetime
from pathlib import Path

# 路径配置
ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CASES_DIR = WIKI_DIR / "cases"
INDEX_PATH = CASES_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"

SIGNIFICANT_FIELDS = [
    "严重度评级",
    "分流建议",
    "情感分析.整体情感",
    "评论区分析.评论红绿灯",
    "评论区分析.评论总结",
]

def _get_next_case_id() -> str:
    """获取下一个案例编号。"""
    existing = list(CASES_DIR.glob("case-*.md"))
    max_id = 0
    for f in existing:
        m = re.search(r'case-(\d+)', f.name)
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"case-{max_id + 1:03d}"


def _parse_date(date_str: str) -> str:
    """解析各种日期格式为 YYYY-MM-DD。"""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    # 已经是 YYYY-MM-DD
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]
    return datetime.now().strftime("%Y-%m-%d")


def _get_nested(d: dict, path: str):
    """获取嵌套字典值，路径用 . 分隔，如 '情感分析.整体情感'。"""
    keys = path.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def _format_value(v) -> str:
    """格式化值为可读字符串。"""
    if v is None:
        return "(无)"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def compare_and_decide(ai_output: dict, human_correction: dict) -> tuple[str, dict]:
    """对比 AI 输出与人工修正，返回 (差异等级, 差异摘要)。

    Returns:
        (level, diff): level 为 "significant" / "minor" / "none"
    """
    diffs = {}
    for field in SIGNIFICANT_FIELDS:
        ai_val = _get_nested(ai_output, field)
        human_val = _get_nested(human_correction, field)
        if ai_val != human_val:
            diffs[field] = {"ai": ai_val, "human": human_val}

    if not diffs:
        return ("none", {})

    for field in ["严重度评级", "分流建议"]:
        if field in diffs:
            return ("significant", diffs)

    return ("minor", diffs)


def generate_case(
    original_input: dict,
    ai_output: dict,
    human_correction: dict,
    diff_level: str,
    diffs: dict,
    url: str = "",
) -> str:
    """生成案例 Markdown 页面。返回生成的文件路径（相对 wiki/cases）。"""
    case_id = _get_next_case_id()
    filename = f"{case_id}.md"

    # 提取关键信息
    title_text = human_correction.get("摘要", original_input.get("原文内容", ""))[:60].replace("\n", " ")
    severity = human_correction.get("严重度评级", "?")
    action = human_correction.get("分流建议", "?")
    platform = original_input.get("来源平台", "未知")
    today = datetime.now().strftime("%Y-%m-%d")

    # 构建差异分析
    diff_lines = []
    for field, vals in diffs.items():
        diff_lines.append(f"- **{field}**：AI 判为「{_format_value(vals['ai'])}」→ 人工修正为「{_format_value(vals['human'])}」")

    url_line = f"url: {url}" if url else ""
    content = f"""---
title: 案例{case_id.split('-')[1]}: {title_text}
type: case
created: {today}
severity: {severity}
action: {action}
platform: {platform}
source: human_correction
{url_line}
original_ai_output:
  severity: {ai_output.get('严重度评级', '?')}
  action: {ai_output.get('分流建议', '?')}
tags: [纠偏案例, {severity}]
---

## 原始输入

```
平台：{original_input.get('来源平台', '未知')}
发布者：{original_input.get('发布者类型', '未知')}
互动数据：{original_input.get('互动数据', '暂无')}
时间：{original_input.get('发布时间', '未知')}
链接：{url}

原文内容：
{original_input.get('原文内容', '(无)')[:800]}
```

## AI 原始标注

```json
{json.dumps(ai_output, ensure_ascii=False, indent=2)}
```

## 人工修正标注

```json
{json.dumps(human_correction, ensure_ascii=False, indent=2)}
```

## 差异分析

{chr(10).join(diff_lines) if diff_lines else '(无显著差异)'}

## 对标注规范的影响

（待分析：此纠偏案例揭示的规则盲区或阈值调整建议。）
"""

    filepath = CASES_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


def update_case_index(new_filename: str, human_correction: dict) -> None:
    """更新 wiki/cases/index.md，添加新案例到总览表和维度索引。

    Delegates to engine.index_mgr (shared with ingestor).
    """
    from engine.index_mgr import update_case_index as do_update

    severity = human_correction.get("严重度评级", "?")
    action = human_correction.get("分流建议", "?")
    title = human_correction.get("摘要", "纠偏案例")[:40]
    categories = human_correction.get("舆情分类", [])

    do_update(
        new_filename=new_filename,
        severity=severity,
        action=action,
        title=title,
        platform="—",
        tags=["纠偏案例"],
        categories=categories,
        source="human_correction",
    )


def append_log(case_filename: str, diff_level: str, input_url: str = "") -> None:
    """追加操作日志。"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    case_id = case_filename.replace(".md", "")

    entry = f"""
### {today} | 纠偏 | 生成 [[cases/{case_id}]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：{diff_level}
- **来源链接**：{input_url if input_url else '手动输入'}
- **说明**：用户修正了 AI 标注结果，差异等级为 {diff_level}。新案例已写入 cases/。
"""

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def handle_correction(
    original_input: dict,
    ai_output: dict,
    human_correction: dict,
    url: str = "",
) -> dict:
    """完整的纠偏处理流程。

    Args:
        original_input: 原始舆情输入
        ai_output: AI 标注输出（不含 _meta）
        human_correction: 人工修正后的标注
        url: 原文链接

    Returns:
        {"action": "generated_case"|"logged_only"|"no_change",
         "case_file": "...",
         "diff_level": "...",
         "diffs": {...}}
    """
    diff_level, diffs = compare_and_decide(ai_output, human_correction)

    if diff_level == "none":
        return {"action": "no_change", "case_file": None, "diff_level": "none", "diffs": {}}

    if diff_level == "significant":
        filename = generate_case(original_input, ai_output, human_correction, diff_level, diffs, url)
        update_case_index(filename, human_correction)
        append_log(filename, diff_level, url)
        return {
            "action": "generated_case",
            "case_file": filename,
            "diff_level": "significant",
            "diffs": diffs,
        }

    # minor
    append_log("(无新案例)", diff_level, url)
    return {
        "action": "logged_only",
        "case_file": None,
        "diff_level": "minor",
        "diffs": diffs,
    }

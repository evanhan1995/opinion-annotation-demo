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
import logging
from datetime import date, datetime
from pathlib import Path

from engine.constants import extract_annotation_diffs

_log = logging.getLogger("yuqing")

# 路径配置
ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CASES_DIR = WIKI_DIR / "cases"
INDEX_PATH = CASES_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"
OUTPUT_DIR = PROJECT_DIR / "outputs"


def _get_next_case_id() -> str:
    """获取下一个案例编号。Delegates to canonical ingestor implementation."""
    from engine.ingestor import get_next_case_id
    return get_next_case_id()


def _parse_date(date_str: str) -> str:
    """解析各种日期格式为 YYYY-MM-DD。"""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    # 已经是 YYYY-MM-DD
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]
    return datetime.now().strftime("%Y-%m-%d")


def _format_value(v) -> str:
    """格式化值为可读字符串。"""
    if v is None:
        return "(无)"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def compare_and_decide(ai_output: dict, human_correction: dict) -> tuple[str, dict]:
    """对比 AI 输出与人工修正，返回 (差异等级, 差异摘要)。

    字段范围由 engine.constants.ANNOTATION_COMPARABLE_FIELDS 统一定义。

    Returns:
        (level, diff): level 为 "significant" / "minor" / "none"
            diff 结构为 {field: {"ai": ..., "human": ...}}（保持既有返回结构）。
    """
    diffs = {}
    for d in extract_annotation_diffs(ai_output, human_correction):
        diffs[d["field"]] = {"ai": d["old_value"], "human": d["new_value"]}

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

    from engine.ingestor import _get_case_dir
    platform = original_input.get("来源平台", "未知")
    target_dir = _get_case_dir(platform)
    filepath = target_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


def update_case_index(new_filename: str, human_correction: dict, platform: str = "") -> None:
    """更新 wiki/cases/index.md，添加新案例到总览表和维度索引。

    Delegates to engine.index_mgr (shared with ingestor).
    """
    from engine.index_mgr import update_case_index as do_update
    from engine.ingestor import PLATFORM_SUBDIR

    severity = human_correction.get("严重度评级", "?")
    action = human_correction.get("分流建议", "?")
    title = human_correction.get("摘要", "纠偏案例")[:40]
    categories = human_correction.get("舆情分类", [])

    do_update(
        new_filename=new_filename,
        severity=severity,
        action=action,
        title=title,
        platform=platform or "—",
        tags=["纠偏案例"],
        categories=categories,
        source="human_correction",
        platform_subdir=PLATFORM_SUBDIR.get(platform, ""),
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


def _notify_urgent_disposal(original_input: dict, human_correction: dict, url: str = "") -> None:
    """Send a Feishu urgent-disposal alert when a case is corrected to 立即处理.

    Fires only on the correction path (B scenario): the AI annotation is being
    corrected by a human, and the 分流建议 is being changed INTO 立即处理.
    Mirrors engine/ingestor.py's A-scenario notification.
    """
    if (human_correction or {}).get("分流建议") != "立即处理":
        return
    try:
        from shared.notify import send_urgent_disposal_card
        social = (original_input or {}).get("社媒数据", {}) or {}
        sent = send_urgent_disposal_card(
            title=str((human_correction or {}).get("摘要", "")
                      or (original_input or {}).get("原文内容", ""))[:60],
            severity=str((human_correction or {}).get("严重度评级", "")),
            platform=str((original_input or {}).get("来源平台", "")),
            url=url or str((original_input or {}).get("原文链接", "")),
        )
        if sent == 0:
            _log.warning("飞书紧急处置通知未送达（0 个 webhook 接受），correction url=%s", (url or "")[:60])
    except Exception as e:
        _log.exception("飞书紧急处置通知发送异常: %s", e)


def _save_correction_json(
    url: str,
    platform: str,
    diff_level: str,
    ai_output: dict,
    human_correction: dict,
    diffs: dict,
    case_file: str | None = None,
) -> str | None:
    """落盘纠偏数据为 outputs/*_correction.json（significant 与 minor 统一数据源）。

    命名规则对齐 outputs/*_annotation.json：{date}_{abbrev}_{content_id}_correction.json。
    diffs 由 compare_and_decide 的 {field: {ai, human}} 转为扁平 [{field, old_value, new_value}]。
    """
    from engine.constants import PLATFORM_ABBREV
    from engine.scraper import _extract_content_id

    today = date.today().isoformat()
    abbrev = PLATFORM_ABBREV.get(platform, "web")
    content_id = _extract_content_id(url, platform) if url else "manual"
    filename = f"{today}_{abbrev}_{content_id}_correction.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename

    flat_diffs = [
        {"field": field, "old_value": vals["ai"], "new_value": vals["human"]}
        for field, vals in (diffs or {}).items()
    ]
    payload = {
        "source": "human_correction",
        "url": url or "",
        "platform": platform or "未知",
        "corrected_at": datetime.now().isoformat(),
        "diff_level": diff_level,
        "ai_output": ai_output,
        "human_correction": human_correction,
        "diffs": flat_diffs,
        "case_file": case_file,
    }
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return filename
    except OSError:
        return None


def handle_correction(
    original_input: dict,
    ai_output: dict,
    human_correction: dict,
    url: str = "",
) -> dict:
    """完整的纠偏处理流程。

    Args:
        original_input: 原始舆情输入
        ai_output: AI 标注输出（可含 _meta，入口统一清洗）
        human_correction: 人工修正后的标注（可含 _meta，入口统一清洗）
        url: 原文链接

    Returns:
        {"action": "generated_case"|"logged_only"|"no_change",
         "case_file": "...",
         "diff_level": "...",
         "diffs": {...}}
    """
    # 入口统一清洗 _meta，保证 generate_case 与 _save_correction_json 消费同一份数据，
    # 避免 ai_output / human_correction 两侧 _meta 不对称（两条落盘路径共用清洗后的变量）。
    ai_output = {k: v for k, v in (ai_output or {}).items() if k != "_meta"}
    human_correction = {k: v for k, v in (human_correction or {}).items() if k != "_meta"}

    diff_level, diffs = compare_and_decide(ai_output, human_correction)

    # 分流建议被人工改为「立即处理」→ 飞书紧急告警（B 场景，与 ingest 的 A 场景独立）。
    # 仅在字段确实发生变更时触发，避免 AI 本就判立即处理时重复告警。
    if diff_level in ("significant", "minor") and "分流建议" in diffs:
        if (human_correction or {}).get("分流建议") == "立即处理":
            _notify_urgent_disposal(original_input, human_correction, url)

    if diff_level == "none":
        return {"action": "no_change", "case_file": None, "diff_level": "none", "diffs": {}}

    case_file = None
    if diff_level == "significant":
        case_file = generate_case(original_input, ai_output, human_correction, diff_level, diffs, url)
        update_case_index(case_file, human_correction, (original_input or {}).get("来源平台", "未知"))

    # significant 与 minor 都落盘 correction json（统一数据源，方便统计脚本只读一处）。
    platform = (original_input or {}).get("来源平台", "未知")
    _save_correction_json(
        url=url or (original_input or {}).get("原文链接", ""),
        platform=platform,
        diff_level=diff_level,
        ai_output=ai_output,
        human_correction=human_correction,
        diffs=diffs,
        case_file=case_file,
    )

    if diff_level == "significant":
        append_log(case_file, diff_level, url)
        return {
            "action": "generated_case",
            "case_file": case_file,
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

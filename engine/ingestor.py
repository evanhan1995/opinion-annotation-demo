"""自动 Ingest 管线 —— 标注完成后自动生成 Wiki 案例。

职责:
1. 接收 scraped_data + annotation_result
2. 生成 wiki/cases/case-XXX.md（auto_ingest 模板）
3. 边界检查（P1 未覆盖、异常组合等）
4. 更新 wiki/cases/index.md 和 wiki/index.md
5. 写入 wiki/log.md
"""

import json
import re
from datetime import datetime, date
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CASES_DIR = WIKI_DIR / "cases"
INDEX_PATH = CASES_DIR / "index.md"
GLOBAL_INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def ingest(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
) -> dict:
    """Auto-ingest: generate case from annotation if URL is new.

    Returns:
        {"action": "case_generated"|"skipped"|"error",
         "case_file": str|None,
         "boundary_check": {...}}
    """
    if annotation_result.get("error"):
        return {"action": "error", "case_file": None, "boundary_check": {}}

    if url:
        existing = _find_existing_case_by_url(url)
        if existing:
            return {"action": "skipped", "case_file": existing, "boundary_check": {}}

    boundary = _check_boundaries(annotation_result)
    case_file = _generate_auto_case(scraped_data, annotation_result, url)
    _update_case_index(case_file, annotation_result)
    _update_global_index(case_file, annotation_result)
    _append_ingest_log(case_file, annotation_result, url)

    return {
        "action": "case_generated",
        "case_file": case_file,
        "boundary_check": boundary,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Dedup
# ═══════════════════════════════════════════════════════════════════════════════

def _find_existing_case_by_url(url: str) -> str | None:
    """Scan existing case files for the URL. Returns filename or None."""
    if not url or not CASES_DIR.exists():
        return None
    for f in sorted(CASES_DIR.glob("case-*.md")):
        content = f.read_text(encoding="utf-8")
        if url in content:
            return f.name
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Case ID
# ═══════════════════════════════════════════════════════════════════════════════

def _get_next_case_id() -> str:
    """Get next case-XXX id by scanning existing files."""
    existing = CASES_DIR.glob("case-*.md") if CASES_DIR.exists() else []
    max_id = 0
    for f in existing:
        m = re.search(r'case-(\d+)', f.name)
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"case-{max_id + 1:03d}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary check (V1: simple heuristics)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_boundaries(annotation_result: dict) -> dict:
    """Run simple boundary heuristics on the annotation result."""
    severity = annotation_result.get("严重度评级", "")
    action = annotation_result.get("分流建议", "")
    platform = annotation_result.get("来源平台", "")

    result = {"p1_uncovered": False, "unusual_combo": False, "new_platform": False}

    if severity == "P1":
        result["p1_uncovered"] = True

    unusual_combos = [
        ("P0", "可忽略"),
        ("P0", "正面可利用"),
        ("P3", "立即处理"),
        ("P2", "正面可利用"),
    ]
    if (severity, action) in unusual_combos:
        result["unusual_combo"] = True

    if INDEX_PATH.exists():
        content = INDEX_PATH.read_text(encoding="utf-8")
        if f"| {platform} |" not in content:
            result["new_platform"] = True

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Case generation (auto_ingest template)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_auto_case(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
) -> str:
    """Generate auto-ingest case page. Returns filename (e.g. 'case-008.md')."""
    case_id = _get_next_case_id()
    filename = f"{case_id}.md"

    title_text = annotation_result.get("摘要", scraped_data.get("原文内容", ""))[:60].replace("\n", " ")
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    platform = scraped_data.get("来源平台", "未知")
    today = date.today().isoformat()

    severity_reason = annotation_result.get("严重度理由", "(无)")
    action_reason = annotation_result.get("分流理由", "(无)")
    authenticity = annotation_result.get("真实性评估", {}).get("判断", "未评估")
    tags = annotation_result.get("风险标签", [])

    ai_output_clean = {k: v for k, v in annotation_result.items() if k != "_meta"}
    ai_output_json = json.dumps(ai_output_clean, ensure_ascii=False, indent=2)

    # Build boundary discussion
    boundary = _check_boundaries(annotation_result)
    boundary_lines = []
    if boundary.get("p1_uncovered"):
        boundary_lines.append("- **P1 边界案例**：当前案例属于 P1 严重度，这是案例库的覆盖盲区，建议优先人工复核。")
    if boundary.get("unusual_combo"):
        boundary_lines.append(f"- **异常组合**：严重度「{severity}」+ 分流建议「{action}」的组合在现有案例中不常见，值得关注。")
    if boundary.get("new_platform"):
        boundary_lines.append(f"- **新平台**：「{platform}」在现有案例库中尚无覆盖，扩展了知识库的平台维度。")
    if not boundary_lines:
        boundary_lines.append("- 此案例落在现有规则覆盖范围内，无明显边界异常。")

    content = f"""---
title: 案例{case_id.split('-')[1]}: {title_text}
type: case
created: {today}
severity: {severity}
action: {action}
platform: {platform}
source: auto_ingest
tags: [auto_ingest, {severity}]
---

## 原始输入

```
平台：{scraped_data.get('来源平台', '未知')}
发布者：{scraped_data.get('发布者类型', '未知')}
互动数据：{scraped_data.get('互动数据', '暂无')}
时间：{scraped_data.get('发布时间', '未知')}
链接：{url}

原文内容：
{scraped_data.get('原文内容', '(无)')[:800]}
```

## AI 原始标注

```json
{ai_output_json}
```

## 判据链

- **严重度判决**：{severity_reason}
- **分流判决**：{action_reason}
- **真实性判断**：{authenticity}
- **风险标签**：{', '.join(tags) if tags else '(无)'}

## 边界讨论

{chr(10).join(boundary_lines)}

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）
"""

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CASES_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


# ═══════════════════════════════════════════════════════════════════════════════
# Index update: wiki/cases/index.md
# ═══════════════════════════════════════════════════════════════════════════════

def _update_case_index(new_filename: str, annotation_result: dict) -> None:
    """Add new case row to wiki/cases/index.md table + dimension indexes."""
    if not INDEX_PATH.exists():
        return

    case_id = new_filename.replace(".md", "")
    case_num = case_id.split("-")[1]
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    platform = annotation_result.get("来源平台", "?")
    title = annotation_result.get("摘要", "auto-ingest")[:40]
    tags = annotation_result.get("风险标签", [])
    tags_str = ", ".join(tags[:3]) if tags else "-"

    new_row = f"| [[cases/{case_id}|{case_num}]] | {title} | {severity} | {action} | {platform} | {tags_str} |"

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find last case-row in the overview table and append after it
    last_case_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'\|\s*\[\[cases/case-\d+\|\d+\]\]', line):
            last_case_line_idx = i

    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line.rstrip())
        if i == last_case_line_idx:
            new_lines.append(new_row)

    # Update dimension indexes: append case ref under matching severity/platform rows
    case_ref = f"[[cases/{case_id}|{case_num}]]"
    section = None

    for i, line in enumerate(new_lines):
        s = line.strip()
        if s.startswith("### 按严重度"):
            section = "severity"
        elif s.startswith("### 按分流建议"):
            section = "action"
        elif s.startswith("### 按平台"):
            section = "platform"
        elif s.startswith("## "):
            section = None

        if section == "severity" and line.strip().startswith(f"| {severity} |"):
            if case_ref not in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    existing = parts[2].strip()
                    if existing in ("—", "-", "（**待添加**）"):
                        parts[2] = f" {case_ref}"
                    else:
                        parts[2] = existing + f", {case_ref}"
                    new_lines[i] = "|".join(parts)

        if section == "platform" and line.strip().startswith(f"| {platform} |"):
            if case_ref not in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    existing = parts[2].strip()
                    if existing in ("—", "-", "（**待添加**）"):
                        parts[2] = f" {case_ref}"
                    else:
                        parts[2] = existing + f", {case_ref}"
                    new_lines[i] = "|".join(parts)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


# ═══════════════════════════════════════════════════════════════════════════════
# Index update: wiki/index.md (global index)
# ═══════════════════════════════════════════════════════════════════════════════

def _update_global_index(new_filename: str, annotation_result: dict) -> None:
    """Append new case row to the global index's case table."""
    if not GLOBAL_INDEX_PATH.exists():
        return

    case_id = new_filename.replace(".md", "")
    case_num = case_id.split("-")[1]
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    title = annotation_result.get("摘要", "auto-ingest案例")[:40]
    today = date.today().isoformat()

    new_row = f"| [[cases/{case_id}|{case_num}-{title[:30]}]] | {title[:40]} | {severity} | {action} | {today} |"

    with open(GLOBAL_INDEX_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find last case table row
    last_case_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'\|\s*\[\[cases/case-\d+\|', line):
            last_case_line_idx = i

    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line.rstrip())
        if i == last_case_line_idx:
            new_lines.append(new_row)

    with open(GLOBAL_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


# ═══════════════════════════════════════════════════════════════════════════════
# Log
# ═══════════════════════════════════════════════════════════════════════════════

def _append_ingest_log(
    case_filename: str,
    annotation_result: dict,
    input_url: str = "",
) -> None:
    """Append auto-ingest entry to wiki/log.md."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    case_id = case_filename.replace(".md", "")
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    tags = annotation_result.get("风险标签", [])
    tag_str = ", ".join(tags[:3]) if tags else "-"

    entry = f"""
### {now} | 自动Ingest | 生成 [[cases/{case_id}]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：{severity}
- **分流建议**：{action}
- **风险标签**：{tag_str}
- **来源链接**：{input_url if input_url else '手动输入'}
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。
"""

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

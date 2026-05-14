"""Wiki 案例索引管理器 —— 统一的 index.md 更新逻辑。

ingestor.py 和 correction_handler.py 共用此模块，避免双轨实现导致格式不一致。

用法:
    from engine.index_mgr import update_case_index

    update_case_index(
        new_filename="case-012.md",
        severity="P2",
        action="持续观察",
        title="案例摘要文本",
        platform="小红书",
        tags=["质量", "客服"],
        source="auto_ingest",
    )
"""

import re
from datetime import date
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
INDEX_PATH = PROJECT_DIR / "wiki" / "cases" / "index.md"


# ═══════════════════════════════════════════════════════════════════════════════
# Table cell helpers (protect [[...]] during split)
# ═══════════════════════════════════════════════════════════════════════════════

def _split_table_cells(line: str) -> list:
    """Split a Markdown table row by `|`, protecting `[[...]]` boundaries."""
    protected = []
    def _replace(m):
        protected.append(m.group(0))
        return f"\x00PROT{len(protected)-1}\x00"
    line = re.sub(r'\[\[.*?\]\]', _replace, line)
    parts = line.split("|")
    for i, part in enumerate(parts):
        parts[i] = re.sub(
            r'\x00PROT(\d+)\x00',
            lambda m: protected[int(m.group(1))],
            part,
        )
    return parts


def _rebuild_row(parts: list) -> str:
    """Rebuild a table row from cell parts."""
    return "|".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Structured table API (parse markdown table → list[dict] → serialize back)
# ═══════════════════════════════════════════════════════════════════════════════

_DIMENSION_HEADERS = {
    "severity": ["严重度", "案例"],
    "action": ["分流建议", "案例"],
    "platform": ["平台", "案例"],
}

_OVERVIEW_HEADERS_AUTO = ["案例", "标题", "严重度", "分流建议", "平台", "风险标签"]
_OVERVIEW_HEADERS_CORRECTION = ["案例", "标题", "严重度", "分流建议", "平台", "类型", "日期"]


def _is_table_row(line: str) -> bool:
    """Check if a line is a markdown table data row (not header separator)."""
    stripped = line.strip()
    return bool(re.match(r'\|\s*\[\[cases/case-\d+\|', stripped))


def _parse_row_to_dict(line: str, headers: list[str]) -> dict:
    """Convert a markdown table row to {header: value} dict."""
    parts = _split_table_cells(line)
    result = {}
    for i, h in enumerate(headers):
        if i + 1 < len(parts):
            result[h] = parts[i + 1].strip()
        else:
            result[h] = ""
    return result


def _dict_to_row(d: dict, headers: list[str]) -> str:
    """Convert a {header: value} dict back to a markdown table row."""
    cells = [f" {d.get(h, '')} " for h in headers]
    return "|" + "|".join(cells) + "|"


def _parse_table_section(lines: list[str], section_heading: str) -> tuple[list[str], list[dict]]:
    """Extract a table from a section. Returns (headers, rows).

    Scans from section_heading to the next `## ` or end of file.
    """
    in_section = False
    after_separator = False
    headers = []
    rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(section_heading):
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("## "):
            break

        if not after_separator:
            # Detect header separator (|---|...|)
            if re.match(r'^\|[\s\-:|]+\|', stripped):
                after_separator = True
                continue
            # Detect header row (starts with `|`, contains non-separator text)
            if stripped.startswith("|") and not re.match(r'^\|[\s\-:|]+\|', stripped):
                parts = _split_table_cells(line)
                headers = [c.strip() for c in parts[1:-1]]  # skip leading/trailing empty
        else:
            if _is_table_row(line):
                rows.append(_parse_row_to_dict(line, headers))

    return headers, rows


# ═══════════════════════════════════════════════════════════════════════════════
# Dimension row update (DRY: used by severity / action / platform)
# ═══════════════════════════════════════════════════════════════════════════════

def _upsert_dimension_row(line: str, dimension_value: str, case_ref: str) -> str:
    """Append case_ref to a dimension index row if not already present.

    Args:
        line: e.g. "| P2 | [[cases/case-002|002]], [[cases/case-007|007]] |"
        dimension_value: e.g. "P2"
        case_ref: e.g. "[[cases/case-012|012]]"

    Returns updated line, or original line if already present or not the right row.
    """
    if not line.strip().startswith(f"| {dimension_value} |"):
        return line
    if case_ref in line:
        return line

    parts = _split_table_cells(line)
    if len(parts) < 3:
        return line

    existing = parts[2].strip()
    if existing in ("—", "-") or "**待添加**" in existing:
        parts[2] = f" {case_ref} "
    else:
        parts[2] = f" {existing}, {case_ref} "
    return _rebuild_row(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def update_case_index(
    new_filename: str,
    severity: str,
    action: str,
    title: str,
    platform: str = "?",
    tags: list = None,
    source: str = "auto_ingest",
) -> None:
    """Add new case to wiki/cases/index.md overview table + all dimension indexes.

    Uses structured parse→modify→serialize for the overview table.
    Dimension indexes continue to use _upsert_dimension_row (string-based,
    well-tested, and dimension tables are simple 2-column structures).

    Args:
        new_filename: e.g. "case-012.md"
        severity: P0/P1/P2/P3
        action: 立即处理/持续观察/可忽略/正面可利用
        title: case title (truncated to 40 chars)
        platform: source platform name
        tags: list of risk tags
        source: "auto_ingest" or "human_correction"
    """
    if not INDEX_PATH.exists():
        return

    case_id = new_filename.replace(".md", "")
    case_num = case_id.split("-")[1]
    title = title[:40]
    tags = tags or []
    today = date.today().isoformat()
    case_ref = f"[[cases/{case_id}|{case_num}]]"

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # --- Overview table: structured dict→row construction ---
    if source == "human_correction":
        use_headers = _OVERVIEW_HEADERS_CORRECTION
        new_row_dict = {
            "案例": case_ref,
            "标题": title,
            "严重度": severity,
            "分流建议": action,
            "平台": "—",
            "类型": "纠偏案例",
            "日期": today,
        }
    else:
        use_headers = _OVERVIEW_HEADERS_AUTO
        tags_str = ", ".join(tags[:3]) if tags else "-"
        new_row_dict = {
            "案例": case_ref,
            "标题": title,
            "严重度": severity,
            "分流建议": action,
            "平台": platform,
            "风险标签": tags_str,
        }

    new_row = _dict_to_row(new_row_dict, use_headers)
    # Find and insert after last case row
    last_case_line_idx = -1
    for i, line in enumerate(lines):
        if _is_table_row(line):
            last_case_line_idx = i

    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line.rstrip())
        if i == last_case_line_idx:
            new_lines.append(new_row)

    # --- Dimension tables: existing _upsert_dimension_row (well-tested) ---
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

        if section == "severity":
            new_lines[i] = _upsert_dimension_row(line, severity, case_ref)
        elif section == "action":
            new_lines[i] = _upsert_dimension_row(line, action, case_ref)
        elif section == "platform":
            new_lines[i] = _upsert_dimension_row(line, platform, case_ref)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

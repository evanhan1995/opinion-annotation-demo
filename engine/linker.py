"""跨条目关联检测 —— 同一事件在不同平台的碎片自动聚合。

用法:
    from engine.linker import auto_link
    result = auto_link("case-013.md")  # 在 ingest 后调用

原理:
    - 提取正文的中文 bigram 集合
    - 计算 Jaccard 相似度 (intersection / union)
    - 相似度 >= 阈值 且 平台不同 → 自动关联
    - 生成 wiki/syntheses/ 条目 + 双向 related_cases 链接
"""

import re
from datetime import date
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CASES_DIR = WIKI_DIR / "cases"
SYNTHESES_DIR = WIKI_DIR / "syntheses"

SIMILARITY_THRESHOLD = 0.25
MIN_BIGRAM_OVERLAP = 3  # at least 3 shared bigrams
TITLE_WEIGHT = 0.4      # title contributes 40% to final score
TAG_BONUS = 0.05        # bonus per shared tag


# ═══════════════════════════════════════════════════════════════════════════════
# Chinese bigram extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_text(case_path: Path) -> str:
    """Extract searchable text from a case file (original content + summary only).

    Excludes annotation template boilerplate (判据链, 边界讨论, etc.)
    to reduce false positives from shared structural text.
    """
    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text

    # Only use content up to 判据链 section (excludes analysis boilerplate)
    for marker in ["## 判据链", "## AI 原始标注", "## 人工修正标注", "## 差异分析"]:
        idx = body.find(marker)
        if idx > 0:
            body = body[:idx]
            break

    return body


def _extract_title(case_path: Path) -> str:
    """Extract case title from frontmatter."""
    return _read_frontmatter_key(case_path, "title") or ""


def _read_tags(case_path: Path) -> set:
    """Extract tags from frontmatter as a set of lowercase strings."""
    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return set()
    for line in parts[1].split("\n"):
        line = line.strip()
        if line.startswith("tags:"):
            tag_str = line.split(":", 1)[1].strip()
            # Parse [tag1, tag2] format
            import re as _re
            tags = _re.findall(r'[\w一-鿿]+', tag_str)
            return {t.lower() for t in tags}
    return set()


def _bigrams(text: str) -> set:
    """Extract Chinese character bigrams (overlapping 2-char windows)."""
    # Keep only Chinese characters and letters
    cleaned = re.sub(r'[^一-鿿\w]', '', text.lower())
    return {cleaned[i:i+2] for i in range(len(cleaned) - 1)}


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity: |intersection| / |union|."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


# ═══════════════════════════════════════════════════════════════════════════════
# Frontmatter helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _read_frontmatter_key(case_path: Path, key: str) -> str:
    """Read a single frontmatter field value."""
    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].split("\n"):
        line = line.strip()
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _append_frontmatter_related(case_path: Path, link_ref: str) -> None:
    """Append a related_cases entry to a case's frontmatter."""
    text = case_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return

    fm_lines = parts[1].split("\n")
    new_fm_lines = []
    has_related = False
    for line in fm_lines:
        new_fm_lines.append(line)
        if line.strip().startswith("related_cases:"):
            has_related = True
        elif has_related and line.strip().startswith("-"):
            # Insert before existing entries if not already present
            continue

    # Rebuild: insert the link into the related_cases list
    if has_related:
        # Find the related_cases block and append
        found_section = False
        result_lines = []
        for line in fm_lines:
            result_lines.append(line)
            if line.strip().startswith("related_cases:"):
                found_section = True
            elif found_section and not line.strip().startswith("-") and line.strip() != "":
                # End of related_cases block, insert before this line
                result_lines.insert(-1, f'  - "{link_ref}"')
                found_section = False
        if found_section:
            # Still in the block at end of frontmatter
            result_lines.append(f'  - "{link_ref}"')
        fm_lines = result_lines
    else:
        # No related_cases section, add one before closing ---
        fm_lines.append("related_cases:")
        fm_lines.append(f'  - "{link_ref}"')

    new_text = f"---\n{chr(10).join(fm_lines)}\n---{parts[2]}"
    case_path.write_text(new_text, encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# Synthesis generation
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_synthesis(case_a: Path, case_b: Path, score: float) -> Path:
    """Create a synthesis entry linking two related cases."""
    SYNTHESES_DIR.mkdir(parents=True, exist_ok=True)

    title_a = _read_frontmatter_key(case_a, "title") or case_a.stem
    title_b = _read_frontmatter_key(case_b, "title") or case_b.stem
    platform_a = _read_frontmatter_key(case_a, "platform") or "?"
    platform_b = _read_frontmatter_key(case_b, "platform") or "?"

    # Generate synthesis filename
    existing = sorted(SYNTHESES_DIR.glob("cross-platform-*.md"))
    num = len(existing) + 1
    filename = f"cross-platform-{num:02d}.md"

    today = date.today().isoformat()
    case_ref_a = f"cases/{case_a.name}"
    case_ref_b = f"cases/{case_b.name}"

    content = f"""---
title: 跨平台关联: {title_a[:30]} <-> {title_b[:30]}
type: synthesis
created: {today}
confidence: medium
source: auto_linker
related_cases:
  - "[[{case_ref_a}]]"
  - "[[{case_ref_b}]]"
tags: [cross-platform, auto-linked]
---

# 跨平台关联事件

## 涉及案例

- [[{case_ref_a}|{case_a.stem}: {title_a[:40]}]]
- [[{case_ref_b}|{case_b.stem}: {title_b[:40]}]]

## 关联分析

- **相似度**: {score:.2f} (Jaccard)
- **平台**: {platform_a} ↔ {platform_b}
- **检测方式**: 中文 bigram 重叠自动检测

## 对标注规范的影响

同一事件在两个平台的讨论可能呈现不同的严重度和情感倾向。
建议对比两个案例的标注结果，检查是否存在平台偏差。
"""

    filepath = SYNTHESES_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def find_related(case_filename: str, threshold: float = SIMILARITY_THRESHOLD) -> list[tuple[str, float]]:
    """Find existing cases related to the given case. Returns [(filename, score), ...].

    Scoring: body Jaccard (60%) + title Jaccard (40%) + shared tag bonus.
    Only cross-platform pairs are considered.
    """
    target_path = CASES_DIR / case_filename
    if not target_path.exists():
        return []

    target_body = _extract_text(target_path)
    target_bigrams = _bigrams(target_body)
    target_platform = _read_frontmatter_key(target_path, "platform")
    target_title = _extract_title(target_path)
    target_title_bigrams = _bigrams(target_title)
    target_tags = _read_tags(target_path)

    if not target_bigrams:
        return []

    results = []
    for other in sorted(CASES_DIR.glob("case-*.md")):
        if other.name == case_filename:
            continue
        other_platform = _read_frontmatter_key(other, "platform")
        if other_platform == target_platform or other_platform == "?":
            continue

        other_body = _extract_text(other)
        other_bigrams = _bigrams(other_body)
        if not other_bigrams:
            continue

        # Body Jaccard (60% weight)
        body_score = _jaccard(target_bigrams, other_bigrams)

        # Title Jaccard (40% weight)
        other_title = _extract_title(other)
        other_title_bigrams = _bigrams(other_title)
        title_score = _jaccard(target_title_bigrams, other_title_bigrams) if target_title_bigrams and other_title_bigrams else 0

        # Weighted score
        score = body_score * (1 - TITLE_WEIGHT) + title_score * TITLE_WEIGHT

        # Tag bonus
        other_tags = _read_tags(other)
        shared_tags = target_tags & other_tags
        if shared_tags:
            score += TAG_BONUS * len(shared_tags)

        overlap = len(target_bigrams & other_bigrams)

        if score >= threshold and overlap >= MIN_BIGRAM_OVERLAP:
            results.append((other.name, round(score, 3)))

    results.sort(key=lambda x: -x[1])
    return results


def auto_link(case_filename: str) -> dict:
    """Auto-link a new case to related existing cases. Call after ingest.

    Returns:
        {"linked": int, "syntheses": [str, ...]}
    """
    related = find_related(case_filename)
    if not related:
        return {"linked": 0, "syntheses": []}

    target_path = CASES_DIR / case_filename
    syntheses = []

    for other_name, score in related:
        other_path = CASES_DIR / other_name

        # Add bidirectional links in frontmatter
        link_a = f"[[cases/{other_name}|{other_name.replace('.md', '')}]]"
        link_b = f"[[cases/{case_filename}|{case_filename.replace('.md', '')}]]"

        _append_frontmatter_related(target_path, link_a)
        _append_frontmatter_related(other_path, link_b)

        # Generate synthesis
        syn_path = _generate_synthesis(target_path, other_path, score)
        syntheses.append(syn_path.name)

        # Log
        log_path = WIKI_DIR / "log.md"
        today = date.today().isoformat()
        entry = f"""
### {today} | 自动关联 | {case_filename} ↔ {other_name}

- **操作类型**：跨平台自动关联
- **相似度**：{score}
- **说明**：检测到两个案例涉及同一事件在不同平台的讨论，已生成关联条目并更新相关案例。
"""
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    return {"linked": len(related), "syntheses": syntheses}

# -*- coding: utf-8 -*-
"""taxonomy_mgr: 受控词表加载/校验/候选管理。

Usage:
    from engine.taxonomy_mgr import load_taxonomy, validate_tags, limit_tags
    nt = load_taxonomy("narrative_categories")
    rt = load_taxonomy("risk_tags")
    result = validate_tags(["品牌声誉受损", "病毒式传播"], rt)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────
ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
TAXONOMY_DIR = PROJECT_DIR / "wiki" / "taxonomy"
CANDIDATE_PATH = TAXONOMY_DIR / "candidate_tags.json"


# ═══════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TaxonomyNode:
    """A single category or tag in the taxonomy tree."""
    name: str
    description: str = ""
    children: list[TaxonomyNode] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    parent: str = ""  # parent L1 name (for L2 nodes)


@dataclass
class Taxonomy:
    """A complete taxonomy (narrative categories, risk tags, or disposition actions)."""
    name: str
    taxonomy_type: str
    version: int
    nodes: list[TaxonomyNode] = field(default_factory=list)

    # ── Derived views (computed once on load) ──

    def flat_labels(self) -> list[str]:
        """All selectable labels.
        Hierarchical (narrative_category): 'L1/L2' format.
        Flat (risk_tag, disposition_action): just the child name.
        """
        is_hierarchical = (self.taxonomy_type == "narrative_category")
        result = []
        for l1 in self.nodes:
            if l1.children:
                for l2 in l1.children:
                    if is_hierarchical:
                        result.append(f"{l1.name}/{l2.name}")
                    else:
                        result.append(l2.name)
            else:
                result.append(l1.name)
        return result

    def label_set(self) -> set[str]:
        """Lowercase label set for fast membership testing."""
        return {lbl.lower() for lbl in self.flat_labels()}

    def find_node(self, label: str) -> Optional[TaxonomyNode]:
        """Find a taxonomy node by its full path label (e.g. '产品质量/食品安全')."""
        parts = label.split("/")
        for l1 in self.nodes:
            if l1.name == parts[0]:
                if len(parts) == 1:
                    return l1
                for l2 in l1.children:
                    if l2.name == parts[1]:
                        return l2
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Parser: Markdown → Taxonomy
# ═══════════════════════════════════════════════════════════════════════════

def _parse_frontmatter(text: str) -> dict:
    """Extract YAML-ish frontmatter. Returns {} if none found."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    meta = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta


def _parse_taxonomy_body(body: str, is_flat: bool = False) -> list[TaxonomyNode]:
    """Parse the Markdown body of a taxonomy file into nodes.

    For hierarchical taxonomies (narrative_categories):
      ## L1名 → **子类**: → - L2名 (关键词)

    For flat taxonomies (risk_tags, disposition_actions):
      ## 大类名 → **标签**: → - 标签名: 描述
    """
    nodes = []
    current_l1: Optional[TaxonomyNode] = None
    in_children = False
    field_name = "标签" if is_flat else "子类"

    in_comment = False
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip HTML comments
        if line.startswith("<!--"):
            in_comment = True
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue

        # L1 heading: "## 产品质量"
        if line.startswith("## "):
            if current_l1:
                nodes.append(current_l1)
            name = line[3:].strip()
            desc_match = re.search(r'\*\*定义\*\*:\s*(.+)$', "")
            current_l1 = TaxonomyNode(name=name)
            in_children = False
            continue

        if not current_l1:
            continue

        # L1 definition: "- **定义**: ..."
        if line.startswith("- **定义**:") or line.startswith("- **定义**:"):
            current_l1.description = line.split(":", 1)[1].strip()
            continue

        # Child marker: "- **子类**:" or "- **标签**:"
        if f"- **{field_name}**:" in line:
            in_children = True
            continue

        # Child entries under the marker
        if in_children and line.startswith("- "):
            entry = line[2:].strip()
            if is_flat:
                # "标签名: 描述"
                if ":" in entry:
                    tag_name, _, tag_desc = entry.partition(":")
                    current_l1.children.append(TaxonomyNode(
                        name=tag_name.strip(),
                        description=tag_desc.strip(),
                        parent=current_l1.name,
                    ))
                else:
                    current_l1.children.append(TaxonomyNode(
                        name=entry, parent=current_l1.name,
                    ))
            else:
                # "L2名 (关键词1, 关键词2)"
                kw_match = re.match(r'^(.+?)\s*\((.+?)\)$', entry)
                if kw_match:
                    l2_name = kw_match.group(1).strip()
                    keywords = [k.strip() for k in kw_match.group(2).split(",")]
                else:
                    l2_name = entry.strip()
                    keywords = []
                current_l1.children.append(TaxonomyNode(
                    name=l2_name, keywords=keywords, parent=current_l1.name,
                ))

    if current_l1:
        nodes.append(current_l1)

    return nodes


def load_taxonomy(filename: str) -> Taxonomy:
    """Load a taxonomy from wiki/taxonomy/{filename}.md.

    Args:
        filename: e.g. 'narrative_categories', 'risk_tags', 'disposition_actions'

    Returns Taxonomy object. Raises FileNotFoundError, ValueError on bad format.
    """
    filepath = TAXONOMY_DIR / f"{filename}.md"
    text = filepath.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text

    is_flat = meta.get("taxonomy_type", "") in ("risk_tag", "disposition_action")
    nodes = _parse_taxonomy_body(body, is_flat=is_flat)

    return Taxonomy(
        name=meta.get("title", filename),
        taxonomy_type=meta.get("taxonomy_type", "unknown"),
        version=int(meta.get("version", 1)),
        nodes=nodes,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Validation & Candidate Management
# ═══════════════════════════════════════════════════════════════════════════

def validate_tags(tags: list[str], taxonomy: Taxonomy) -> dict:
    """Check tags against the taxonomy word list.

    Returns:
        {
          "valid": ["品牌声誉受损", ...],      # tags found in taxonomy
          "candidates": ["新标签名", ...],      # tags NOT in taxonomy → suggest as candidates
          "rejected": [],                       # tags already rejected before
        }
    """
    label_set = taxonomy.label_set()
    result = {"valid": [], "candidates": [], "rejected": []}

    for tag in tags:
        tag_clean = tag.strip()
        if not tag_clean:
            continue
        if tag_clean.lower() in label_set:
            result["valid"].append(tag_clean)
        else:
            # Check if previously rejected
            if _is_rejected(tag_clean, taxonomy.taxonomy_type):
                result["rejected"].append(tag_clean)
            else:
                result["candidates"].append(tag_clean)

    return result


def limit_tags(tags: list[str], max_n: int = 3) -> list[str]:
    """Enforce max tags per case. Returns trimmed list."""
    return tags[:max_n]


def suggest_candidates(candidates: list[str], taxonomy_type: str,
                       context: str = "", case_id: str = "") -> list[dict]:
    """Record candidate tag suggestions for later human review.

    Saves to wiki/taxonomy/candidate_tags.json.
    Returns list of newly added suggestions.
    """
    existing = _load_candidates()
    new_entries = []
    pending_labels = {c["label"] for c in existing.get("pending", [])}
    rejected_labels = {c["label"] for c in existing.get("rejected", [])}

    for label in candidates:
        if label in pending_labels or label in rejected_labels:
            continue
        entry = {
            "label": label,
            "category": taxonomy_type,
            "suggested_by": case_id or "manual",
            "suggested_at": __import__("datetime").date.today().isoformat(),
            "context": context[:200],
        }
        existing.setdefault("pending", []).append(entry)
        new_entries.append(entry)

    if new_entries:
        _save_candidates(existing)

    return new_entries


# ═══════════════════════════════════════════════════════════════════════════
# Prompt builder
# ═══════════════════════════════════════════════════════════════════════════

def build_taxonomy_prompt_section(narrative_tax: Taxonomy,
                                  risk_tax: Taxonomy) -> str:
    """Build the taxonomy section to inject into the LLM annotation prompt."""
    lines = [
        "## 受控词表（请从以下选项中选择，不要自由发挥）",
        "",
        "### 叙事分类（narrative_thread）",
        "选择一个主分类，格式为 'L1/L2'，例如 '产品质量/食品安全'",
        "",
    ]
    for l1 in narrative_tax.nodes:
        lines.append(f"- **{l1.name}**")
        for l2 in l1.children:
            kw_str = f"（关键词: {', '.join(l2.keywords)}）" if l2.keywords else ""
            lines.append(f"  - `{l1.name}/{l2.name}` {kw_str}")

    lines.extend([
        "",
        "### 风险标签（risk_tags_controlled）",
        "最多选择 3 个最核心的风险标签。找不到合适标签时，"
        "在 risk_tags_candidate 中建议新标签（标记为 [候选]）。",
        "",
    ])
    for cat in risk_tax.nodes:
        lines.append(f"- **{cat.name}**")
        for tag in cat.children:
            lines.append(f"  - `{tag.name}`: {tag.description}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Candidate persistence (local JSON — prototype, will stay in production)
# ═══════════════════════════════════════════════════════════════════════════

def _load_candidates() -> dict:
    """Load candidate_tags.json. Returns empty dict if file doesn't exist."""
    if not CANDIDATE_PATH.exists():
        return {"pending": [], "approved": [], "rejected": []}
    try:
        return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pending": [], "approved": [], "rejected": []}


def _save_candidates(data: dict) -> None:
    """Write candidate_tags.json atomically."""
    TAXONOMY_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_rejected(label: str, taxonomy_type: str) -> bool:
    """Check if a label was previously rejected."""
    existing = _load_candidates()
    for r in existing.get("rejected", []):
        if r["label"] == label and r.get("category") == taxonomy_type:
            return True
    return False


def approve_candidate(label: str) -> bool:
    """Move a candidate from pending → approved."""
    data = _load_candidates()
    for entry in data.get("pending", []):
        if entry["label"] == label:
            data["pending"].remove(entry)
            data.setdefault("approved", []).append(entry)
            _save_candidates(data)
            return True
    return False


def reject_candidate(label: str) -> bool:
    """Move a candidate from pending → rejected."""
    data = _load_candidates()
    for entry in data.get("pending", []):
        if entry["label"] == label:
            data["pending"].remove(entry)
            data.setdefault("rejected", []).append(entry)
            _save_candidates(data)
            return True
    return False

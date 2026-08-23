"""自动 Ingest 管线 —— 标注完成后自动生成 Wiki 案例。

职责:
1. 接收 scraped_data + annotation_result
2. 生成 wiki/cases/case-XXX.md（auto_ingest 模板）
3. 边界检查（P1 未覆盖、异常组合等）
4. 更新 wiki/cases/index.md 和 wiki/index.md
5. 写入 wiki/log.md
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, date
from pathlib import Path

_log = logging.getLogger("yuqing")

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent
WIKI_DIR = PROJECT_DIR / "wiki"
CASES_DIR = WIKI_DIR / "cases"
INDEX_PATH = CASES_DIR / "index.md"
GLOBAL_INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"
RAW_CASES_DIR = PROJECT_DIR / "raw" / "cases"
RAW_ARCHIVE_DIR = PROJECT_DIR / "raw" / "archive"
AUTHORS_DIR = WIKI_DIR / "authors"


# ═══════════════════════════════════════════════════════════════════════════════
# Author library
# ═══════════════════════════════════════════════════════════════════════════════

def _slugify(name: str) -> str:
    """Convert author name to filename-safe slug."""
    import re as _re
    slug = name.lower().strip()
    slug = _re.sub(r'[^a-z0-9一-鿿]+', '-', slug)
    return slug.strip('-')


def _upsert_author(social: dict, platform: str) -> str | None:
    """Create or update an author page. Returns filename (e.g. 'author-xxx.md')."""
    author_name = social.get("作者", "").strip()
    if not author_name:
        return None

    slug = _slugify(author_name)
    filename = f"author-{slug}.md"
    filepath = AUTHORS_DIR / filename
    today = date.today().isoformat()
    homepages = list(social.get("作者主页", []))

    merged_platforms = [platform]
    merged_homepages = list(homepages)
    existing_cases = []

    if filepath.exists():
        text = filepath.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            # Merge platforms
            pm = re.search(r'platforms:\s*\[(.*?)\]', fm)
            if pm:
                for p in re.split(r'[,\s]+', pm.group(1)):
                    p = p.strip().strip("'\"")
                    if p and p not in merged_platforms:
                        merged_platforms.append(p)
            # Merge homepages
            for m in re.finditer(r'^\s*-\s*(.+)$', fm, re.MULTILINE):
                hp = m.group(1).strip()
                if hp and hp not in merged_homepages:
                    merged_homepages.append(hp)
            # Preserve existing related_cases
            cm = re.search(r'related_cases:\s*\n((?:\s*-.*\n?)*)', fm)
            if cm:
                existing_cases = re.findall(r'\[\[([^\]]+)\]\]', cm.group(1))
    else:
        AUTHORS_DIR.mkdir(parents=True, exist_ok=True)

    hp_lines = "\n".join(f"  - {h}" for h in merged_homepages if h) if merged_homepages else "  - []"
    platforms_str = ", ".join(merged_platforms)
    cases_lines = "\n".join(f"  - \"[[{c}]]\"" for c in existing_cases) if existing_cases else "  - []"
    content = f"""---
title: {author_name}
type: author
created: {today}
platforms: [{platforms_str}]
followers: {social.get('粉丝', 0)}
homepages:
{hp_lines}
related_cases:
{cases_lines}
tags: [author, {platforms_str}]
---

# {author_name}

## 基本信息

- **平台**: {platforms_str}
- **粉丝**: {social.get('粉丝', 0):,}
- **国家**: {social.get('国家') or '未知'}

## 主页

{chr(10).join(f'- {h}' for h in merged_homepages if h) if merged_homepages else '- (暂无)'}

## 关联案例

{chr(10).join(f'- [[{c}]]' for c in existing_cases) if existing_cases else '（案例入库时自动追加）'}
"""
    filepath.write_text(content, encoding="utf-8")
    return filename


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def ingest(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
    notes: str = "",
    init_status: str = "待跟进",
    keyword: str = "",
    notify: bool = False,
    case_id: str = "",
) -> dict:
    """Auto-ingest: generate case from annotation if URL is new.

    Args:
        notify: 是否推送飞书通知。默认 False——巡检自动入库不通知；
            仅在「录入研判」人工筛选并提交时由 _do_ingest 显式传 True。
        case_id: 由 Orchestrator 统一生成传入（与 Handler.triage 共用同一 id）。
            为空时内部生成（兼容直接调用 engine.ingestor.ingest 的旧路径，如 UI）。

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
    boundary_suggestions = _generate_boundary_suggestion(boundary, annotation_result, scraped_data)
    # Author library: upsert before case so we can backlink
    social = scraped_data.get("社媒数据", {})
    if not isinstance(social, dict):
        social = {}
    platform = scraped_data.get("来源平台", "未知")
    author_file = _upsert_author(social, platform) if social else None
    case_file = _generate_auto_case(scraped_data, annotation_result, url, author_file,
                                     notes=notes, init_status=init_status,
                                     keyword=keyword, case_id=case_id)
    _update_case_index(case_file, annotation_result, scraped_data)
    _update_global_index(case_file, annotation_result)
    _append_ingest_log(case_file, annotation_result, url)
    _archive_raw_file(url)

    # Cross-entry linker: detect same-event across platforms
    linker_result = None
    try:
        from engine.linker import auto_link as _auto_link
        linker_result = _auto_link(case_file)
    except Exception:
        pass

    # Phase 2: generate embedding for semantic search (non-blocking)
    similar_cases = []
    try:
        from engine.embeddings import EmbeddingService
        svc = EmbeddingService()
        case_path = _get_case_dir(platform) / case_file
        svc.get_or_create_embedding(str(case_path))
        similar = svc.find_similar_cases(str(case_path), top_k=3)
        for s in similar:
            similar_cases.append({"path": s["path"], "score": s["score"]})
    except Exception:
        pass

    # Notify Feishu when a case enters the library (new URL only — the dedup
    # early-return above means existing URLs never reach here).
    #
    # 通知触发点绑定「录入研判」提交动作：仅当 notify=True（由 _do_ingest 传入）
    # 才推送。巡检自动入库（pipeline / run_active_monitor）始终 notify=False，
    # 不产生任何飞书通知——避免巡检抓取的无效噪音污染研判。
    if notify:
        try:
            from shared.notify import send_annotated_case_card
            case_url = url or str(scraped_data.get("原文链接", ""))
            sent = send_annotated_case_card(
                annotation_result=annotation_result,
                scraped_data=scraped_data,
                url=case_url,
                init_status=init_status,
            )
            if sent == 0:
                _log.warning("飞书研判入库通知未送达（0 个 webhook 接受），case_url=%s", case_url[:60])
        except Exception as e:
            _log.exception("飞书通知发送异常: %s", e)

    return {
        "action": "case_generated",
        "case_file": case_file,
        "boundary_check": boundary,
        "boundary_suggestions": boundary_suggestions,
        "linker": linker_result or {},
        "similar_cases": similar_cases,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Dedup & Archive
# ═══════════════════════════════════════════════════════════════════════════════

def _archive_raw_file(url: str) -> None:
    """Move raw case files matching URL from raw/cases/ to raw/archive/."""
    if not url or not RAW_CASES_DIR.exists():
        return
    for f in RAW_CASES_DIR.glob("*.json"):
        try:
            content = f.read_text(encoding="utf-8")
            if url in content:
                RAW_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
                dest = RAW_ARCHIVE_DIR / f.name
                f.rename(dest)
                return
        except Exception:
            continue

def _find_existing_case_by_url(url: str) -> str | None:
    """Scan case frontmatter for matching URL. Returns filename or None.

    Only reads the YAML frontmatter block (between --- delimiters) of each
    case file, not the full file body.  O(N) in number of cases, constant per file.
    Searches flat + platform subdirectories.
    """
    if not url or not CASES_DIR.exists():
        return None
    all_files = list(CASES_DIR.glob("case-*.md"))
    for sub in CASES_DIR.iterdir():
        if sub.is_dir():
            all_files.extend(sub.glob("case-*.md"))
    for f in sorted(all_files):
        text = f.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.split("\n"):
                stripped = line.strip()
                if stripped.startswith("url:") and url in stripped:
                    return f.name
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Platform subdirectory routing
# ═══════════════════════════════════════════════════════════════════════════════

PLATFORM_SUBDIR = {
    "小红书": "xiaohongshu",
    "抖音": "douyin",
    "YouTube": "youtube",
    "xiaohongshu": "xiaohongshu",
    "douyin": "douyin",
    "youtube": "youtube",
    "B站": "bilibili",
    "bilibili": "bilibili",
    "微博": "weibo",
    "weibo": "weibo",
    "微信公众号": "wechat",
    "wechat": "wechat",
}


def _get_case_dir(platform: str) -> Path:
    """Get the target directory for a case based on platform."""
    sub = PLATFORM_SUBDIR.get(platform)
    if sub:
        target = CASES_DIR / sub
        target.mkdir(parents=True, exist_ok=True)
        return target
    return CASES_DIR


# ═══════════════════════════════════════════════════════════════════════════════
# Case ID
# ═══════════════════════════════════════════════════════════════════════════════

# 进程内预留编号 + 锁：保证并发调用（如 Monitor 的 ThreadPoolExecutor）不碰撞。
# _case_id_reserved 是单调递增的内存计数器，即便对应 case 文件尚未落盘，
# 同一进程内的后续调用也不会复用该编号。None 表示尚未从磁盘播种。
_CASE_ID_LOCK = threading.Lock()
_case_id_reserved = None


def _scan_max_case_id() -> int:
    """扫描现有 case 文件（扁平目录 + 平台子目录），返回最大数字编号。

    仅用于进程首次调用时播种计数器；之后 get_next_case_id 完全依赖内存计数器，
    不再重复扫描磁盘。
    """
    max_id = 0
    if CASES_DIR.exists():
        for f in CASES_DIR.glob("case-*.md"):
            m = re.search(r'case-(\d+)', f.name)
            if m:
                max_id = max(max_id, int(m.group(1)))
        for sub in CASES_DIR.iterdir():
            if sub.is_dir():
                for f in sub.glob("case-*.md"):
                    m = re.search(r'case-(\d+)', f.name)
                    if m:
                        max_id = max(max_id, int(m.group(1)))
    return max_id


def get_next_case_id() -> str:
    """Get next unique case-XXX id.

    Canonical implementation — other modules should import this function
    rather than maintaining their own copies.

    并发语义（重要）：
      - 仅保证**单进程内多线程**安全：进程级 threading.Lock + 单调内存计数器。
      - 不支持多进程 / 多实例部署下的唯一性：多个进程各自维护独立的内存计数器，
        互不可见，会碰撞。若未来需要多实例并发写 wiki/cases/，必须引入外部协调
        （如文件锁、原子自增、数据库序列），不能依赖本函数。

    性能：
      - 磁盘扫描（_scan_max_case_id）只在进程首次调用时执行一次，
        之后完全靠内存计数器自增，O(1)，不随案例库规模增长。
    """
    global _case_id_reserved
    with _CASE_ID_LOCK:
        if _case_id_reserved is None:
            _case_id_reserved = _scan_max_case_id()
        _case_id_reserved += 1
        return f"case-{_case_id_reserved:03d}"


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


def _generate_boundary_suggestion(
    boundary: dict,
    annotation_result: dict,
    scraped_data: dict,
) -> list[dict]:
    """Generate draft-PR-style suggestions for updating severity-rating-matrix.md.

    Returns a list of suggestion dicts, each describing a proposed edit.
    Empty list if no blind spots found.
    """
    suggestions = []
    severity = annotation_result.get("严重度评级", "")
    action = annotation_result.get("分流建议", "")
    platform = scraped_data.get("来源平台", "未知")
    summary = annotation_result.get("摘要", "")[:60]
    severity_reason = annotation_result.get("严重度理由", "")[:100]

    if boundary.get("p1_uncovered"):
        suggestions.append({
            "target_file": "wiki/concepts/severity-rating-matrix.md",
            "section": "关键边界 → P0 ↔ P1",
            "title": f"新增 P1 边界案例: {summary}",
            "reason": (
                f"当前案例严重度 P1（{severity_reason}），"
                f"平台 {platform}，分流建议 {action}。"
                f"P1 案例在库中稀缺，此案例可丰富 P0↔P1 边界的校准参考。"
            ),
            "current_text": "（在「关联案例」区域末尾追加）",
            "proposed_text": (
                f"- [[cases/case-NNN|NNN-{summary[:20]}]]："
                f"{severity_reason[:60]}×{platform}×{action}=P1，扩展P0↔P1边界校准"
            ),
            "trigger": "p1_uncovered",
        })

    if boundary.get("unusual_combo"):
        combo_reason = f"严重度「{severity}」与分流建议「{action}」的组合"
        suggestions.append({
            "target_file": "wiki/concepts/severity-rating-matrix.md",
            "section": "概述 / 决策逻辑",
            "title": f"标记异常组合: {severity} + {action}",
            "reason": (
                f"{combo_reason}在现有案例库中未出现过。"
                f"建议人工复核：此组合是否合理？若合理则无需修改矩阵；"
                f"若不合理则纠偏修正。"
            ),
            "current_text": "（无需修改矩阵原文；仅标记为待复核异常）",
            "proposed_text": f"[待复核] {combo_reason}出现在案例中，建议检查是否需要调整分流规则。",
            "trigger": "unusual_combo",
        })

    if boundary.get("new_platform"):
        suggestions.append({
            "target_file": "wiki/concepts/platform-adaptation.md",
            "section": "平台列表",
            "title": f"新增平台覆盖: {platform}",
            "reason": (
                f"「{platform}」在当前案例库索引中首次出现。"
                f"建议在 platform-adaptation.md 中添加此平台的特性说明，"
                f"以便 LLM 在标注时考虑该平台的内容形态和用户特征。"
            ),
            "current_text": "（在平台适配表中新增一行）",
            "proposed_text": f"| {platform} | [待补充：内容形态、用户特征、互动模式] |",
            "trigger": "new_platform",
        })

    return suggestions


# ═══════════════════════════════════════════════════════════════════════════════
# Case generation (auto_ingest template)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_auto_case(
    scraped_data: dict,
    annotation_result: dict,
    url: str = "",
    author_file: str = None,
    notes: str = "",
    init_status: str = "待跟进",
    keyword: str = "",
    case_id: str = "",
) -> str:
    """Generate auto-ingest case page. Returns filename (e.g. 'case-008.md')."""
    case_id = case_id or get_next_case_id()
    filename = f"{case_id}.md"

    title_text = annotation_result.get("摘要", scraped_data.get("原文内容", ""))[:60].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace("|", "｜")
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    platform = scraped_data.get("来源平台", "未知")
    today = date.today().isoformat()

    # sentiment：写入 frontmatter，供 query_stats 统计（存量 case 由 curator
    # 从正文 JSON 兜底解析）。情感可能藏在「情感分析.整体情感」或「多维度情感分析」。
    _emo = annotation_result.get("情感分析", {})
    sentiment = ""
    if isinstance(_emo, dict):
        sentiment = _emo.get("整体情感", "") or ""
    if not sentiment:
        _md = annotation_result.get("多维度情感分析", {})
        if isinstance(_md, dict):
            sentiment = _md.get("主体情感", "") or ""

    severity_reason = annotation_result.get("严重度理由", "(无)")
    action_reason = annotation_result.get("分流理由", "(无)")
    authenticity_raw = annotation_result.get("真实性评估", {})
    if isinstance(authenticity_raw, dict):
        authenticity = authenticity_raw.get("判断", "未评估")
    else:
        authenticity = str(authenticity_raw) if authenticity_raw else "未评估"
    tags = annotation_result.get("风险标签", [])

    # Phase 1: controlled vocabulary fields
    narrative_thread = annotation_result.get("叙事分类", "")
    secondary_threads = annotation_result.get("次要叙事", [])
    if isinstance(secondary_threads, str):
        secondary_threads = [s.strip() for s in secondary_threads.split(",") if s.strip()]
    risk_tags_controlled = annotation_result.get("风险标签_受控", tags)[:3]
    risk_tags_candidate = annotation_result.get("风险标签_候选", [])
    target_type = annotation_result.get("目标类型", "我方")

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

    url_line = f"url: {url}" if url else ""
    kw_line = f"source_keyword: {keyword}" if keyword else ""
    cats = annotation_result.get("舆情分类", [])
    cat_line = f"categories: [{', '.join(cats)}]" if cats else ""
    author_line = f"author: \"[[authors/{author_file}]]\"" if author_file else ""
    sent_line = f"sentiment: {sentiment}" if sentiment else ""

    # Phase 1: controlled vocabulary frontmatter fields
    nt_line = f"narrative_thread: {narrative_thread}" if narrative_thread else ""
    st_lines = "\n".join(f"  - {s}" for s in secondary_threads[:2]) if secondary_threads else ""
    sec_line = f"secondary_threads:\n{st_lines}" if st_lines else ""
    rtc_line = f"risk_tags_controlled: [{', '.join(risk_tags_controlled)}]" if risk_tags_controlled else ""
    rtx_line = f"risk_tags_candidate: [{', '.join(risk_tags_candidate)}]" if risk_tags_candidate else ""
    tt_line = f"target_type: {target_type}"
    # 降级标记：LLM 失败降级时写入 frontmatter（degraded=true + 原因），供 UI 标记
    _deg = annotation_result.get("degraded", False)
    deg_line = (f"degraded: true\ndegraded_reason: {annotation_result.get('degraded_reason', '')}"
                if _deg else "")
    # 复核标记：仅 P0/P1 复核过（review_severity 非空）时写 frontmatter，P2/P3 不写
    _rv_sev = annotation_result.get("review_severity", "")
    review_lines = ""
    if _rv_sev:
        _rv_disputed = str(annotation_result.get("review_disputed", "")).lower() == "true"
        review_lines = (
            f"review_severity: {_rv_sev}\n"
            f"review_disputed: {'true' if _rv_disputed else 'false'}\n"
            f"sentinel_reference: {annotation_result.get('sentinel_reference', '')}"
        )

    content = f"""---
title: 案例{case_id.split('-')[1]}: {title_text}
type: case
created: {today}
severity: {severity}
action: {action}
platform: {platform}
source: auto_ingest
status: {init_status}
{url_line}
{kw_line}
{cat_line}
{author_line}
{sent_line}
{nt_line}
{sec_line}
{rtc_line}
{rtx_line}
{tt_line}
{deg_line}
{review_lines}
notes: {notes}
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
- **风险标签（受控）**：{', '.join(risk_tags_controlled) if risk_tags_controlled else '(无)'}
- **风险标签（候选）**：{', '.join(risk_tags_candidate) if risk_tags_candidate else '(无)'}
- **叙事分类**：{narrative_thread or '未分类'}{f' (次要: {", ".join(secondary_threads[:2])})' if secondary_threads else ''}

## 边界讨论

{chr(10).join(boundary_lines)}

## 处置备注

{notes if notes else '（无）'}

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）
"""

    target_dir = _get_case_dir(platform)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Atomic file creation with retry to prevent concurrent ingest race.
    # Step 2 of the pipeline can run up to 3 concurrent ingest() calls;
    # two threads scanning for the same case ID and writing would cause
    # silent data loss. os.O_CREAT|O_EXCL guarantees exactly one winner.
    _retry_count = 0
    _retry_max = 10
    while True:
        filepath = target_dir / filename
        try:
            fd = os.open(str(filepath), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            _retry_count += 1
            if _retry_count >= _retry_max:
                raise RuntimeError(
                    f"Failed to allocate unique case ID after {_retry_max} attempts "
                    f"(last tried: {filename})"
                )
            _delay = 0.05 * _retry_count
            time.sleep(_delay)
            case_id = get_next_case_id()
            filename = f"{case_id}.md"
            continue
        break

    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


# ═══════════════════════════════════════════════════════════════════════════════
# Index update: delegates to engine.index_mgr (shared with correction_handler)
# ═══════════════════════════════════════════════════════════════════════════════

def _update_case_index(new_filename: str, annotation_result: dict, scraped_data: dict = None) -> None:
    """Add new case row to wiki/cases/index.md. Delegates to index_mgr."""
    from engine.index_mgr import update_case_index

    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    platform = (scraped_data or {}).get("来源平台", annotation_result.get("来源平台", "?"))
    title = annotation_result.get("摘要", "auto-ingest").replace("\n", " ").replace("\r", " ").replace("\t", " ").replace("|", "｜")[:40]
    tags = annotation_result.get("风险标签_受控", annotation_result.get("风险标签", []))[:3]
    categories = annotation_result.get("舆情分类", [])
    narrative_thread = annotation_result.get("叙事分类", "")

    update_case_index(
        new_filename=new_filename,
        severity=severity,
        action=action,
        title=title,
        platform=platform,
        tags=tags,
        categories=categories,
        source="auto_ingest",
        narrative_thread=narrative_thread,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Index update: wiki/index.md (global index)
# ═══════════════════════════════════════════════════════════════════════════════

def _update_global_index(new_filename: str, annotation_result: dict) -> None:
    """Append new case row to the global index's case table.

    Creates the initial case table if it doesn't exist yet.
    """
    if not GLOBAL_INDEX_PATH.exists():
        return

    case_id = new_filename.replace(".md", "")
    case_num = case_id.split("-")[1]
    severity = annotation_result.get("严重度评级", "?")
    action = annotation_result.get("分流建议", "?")
    title = annotation_result.get("摘要", "auto-ingest案例").replace("\n", " ").replace("\r", " ").replace("\t", " ").replace("|", "｜")[:40]
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

    # If no case table exists yet, create one at the end of the file
    if last_case_line_idx == -1:
        table_header = "| 案例 | 标题 | 严重度 | 分流建议 | 入库日期 |"
        table_sep = "|------|------|--------|----------|----------|"
        new_lines.extend(["", "## 案例列表", "", table_header, table_sep, new_row])

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

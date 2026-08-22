# -*- coding: utf-8 -*-
"""统一报告对象 FinalReport 与持久化。

这是"单一 Report 源"的核心：报告生成完成后，把结构化 IR + 数据快照 + 渲染产物
一次性缓存到 wiki/reports/{type}/{date}.report.json，报告 Tab 与飞书都从它读取，
不再各自重新 collect / 重新 LLM。

FinalReport 语义：
  - 生成后即锁定（被动）：模板变更只影响下一次生成，不影响已生成的这份。
  - 手动重生成同一天（主动）：新版本以 published 覆盖，旧版本标 superseded 存档。
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = PROJECT_ROOT / "wiki"


def report_dir(report_type: str) -> Path:
    """Reports directory for a report type ("daily" | "monthly")."""
    sub = "daily" if report_type == "daily" else "monthly"
    return WIKI_DIR / "reports" / sub


def make_report_id(report_type: str, report_date: str) -> str:
    """Deterministic report id — the "slot" identity for a given day/month."""
    return f"{report_type}-{report_date}"


@dataclass
class FinalReport:
    """A single finalized report. ir 字段是序列化后的 ReportIR（等价 engine/report_ir.ReportIR）。"""
    report_id: str
    report_type: str            # "daily" | "monthly"
    report_date: str            # 报告归属日/月（当日口径）
    template_id: str            # 生成时绑定的模板
    template_version: int       # 模板版本，历史报告不可漂移
    generated_at: str           # ISO 时间戳
    status: str = "published"   # draft | published | superseded
    data: dict = field(default_factory=dict)          # ReportData 序列化快照
    ir: dict = field(default_factory=dict)            # ReportIR 序列化（chapters 为 dict 列表）
    markdown: str = ""          # 渲染产物（== .md 文件内容）
    html: str = ""              # 渲染产物（== .html 文件内容）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FinalReport":
        return cls(**d)

    def chapters(self) -> list[dict]:
        """便捷访问：结构化章节列表（每个为 anchor/title/data_rows/analysis/chart 的 dict）。"""
        return self.ir.get("chapters", [])


def _archive_existing(report_type: str, report_date: str) -> None:
    """若同名 report.json 已 published，标记为 superseded 并存档为 .v{N}.report.json。"""
    d = report_dir(report_type)
    json_path = d / f"{report_date}.report.json"
    if not json_path.exists():
        return
    try:
        existing = FinalReport.from_dict(json.loads(json_path.read_text(encoding="utf-8")))
    except Exception:
        return
    if existing.status != "published":
        return
    existing.status = "superseded"
    n = 1
    while (d / f"{report_date}.v{n}.report.json").exists():
        n += 1
    (d / f"{report_date}.v{n}.report.json").write_text(
        json.dumps(existing.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_final_report(fr: FinalReport) -> str:
    """Persist FinalReport to .report.json + .md + .html. Returns the .report.json path."""
    d = report_dir(fr.report_type)
    d.mkdir(parents=True, exist_ok=True)
    _archive_existing(fr.report_type, fr.report_date)

    json_path = d / f"{fr.report_date}.report.json"
    json_path.write_text(json.dumps(fr.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    (d / f"{fr.report_date}.md").write_text(fr.markdown, encoding="utf-8")
    if fr.html:
        (d / f"{fr.report_date}.html").write_text(fr.html, encoding="utf-8")
    return str(json_path)


def load_final_report(report_type: str, report_date: str) -> Optional[FinalReport]:
    """Read the current published FinalReport from cache. None if not generated yet."""
    json_path = report_dir(report_type) / f"{report_date}.report.json"
    if not json_path.exists():
        return None
    try:
        fr = FinalReport.from_dict(json.loads(json_path.read_text(encoding="utf-8")))
    except Exception:
        return None
    if fr.status != "published":
        return None
    return fr


# ═══════════════════════════════════════════════════════════════════════════════
# Report Template（报告模板）—— 定义"报告长什么样"，与数据/报告对象解耦
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_DIR = PROJECT_ROOT / "config"
TEMPLATES_DIR = CONFIG_DIR / "report_templates"


@dataclass
class TemplateModule:
    """报告模板中的单个模块（章节）。"""
    anchor: str                        # 唯一锚点，如 "volume-overview"
    title: str                         # 模块标题，如 "一、声量概览"
    order: int                         # 模块顺序
    required: bool = True              # 是否必选
    data_binding: list = field(default_factory=list)   # 绑定的 ReportData 字段（描述性元数据）
    llm_analysis: bool = False         # 该模块是否由 LLM 填分析文字
    render_kind: str = "line"          # line | table | list | custom
    render_template: str = ""          # 渲染串；custom 时填内置 RENDERER_REGISTRY 白名单 key
    chart: dict = None                 # {"type":"pie"|"bar", "labels":[...], "values":[...]}
    max_display: int = None            # 列表展示上限；超限须输出「另有 N 条未展开」
    feishu_verbosity: str = "data_only"  # 飞书卡片该模块是否含分析段（"data_only"|"full"）
    description: str = ""              # 供学习/编辑界面展示


@dataclass
class ReportTemplate:
    """报告模板（日报/月报独立）。version 使历史报告绑定到生成时的模板版本。"""
    template_id: str
    template_type: str                 # "daily" | "monthly"
    version: int
    name: str
    title_format: str                  # "舆情日报 {{date}}"
    intro: dict                        # {"enabled": bool, "prompt_hint": str}
    modules: list = field(default_factory=list)   # list[TemplateModule]
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ReportTemplate":
        modules = [TemplateModule(**m) for m in d.get("modules", [])]
        fields = {k: v for k, v in d.items() if k != "modules"}
        tpl = cls(**fields)
        tpl.modules = modules
        return tpl

    def sorted_modules(self) -> list:
        return sorted(self.modules, key=lambda m: m.order)

    def llm_anchors(self) -> list:
        return [m.anchor for m in self.modules if m.llm_analysis]


# ── 默认模板（由当前 report_ir 硬编码结构导出，保证零行为回归） ───────────

def default_template(report_type: str) -> ReportTemplate:
    """内置默认模板。结构与历史 report_ir.build_ir 完全一致。"""
    if report_type == "monthly":
        modules = [
            TemplateModule(anchor="volume-overview", title="一、月度声量趋势", order=1, required=True,
                           data_binding=["total_new_cases", "avg_prev_7days"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="sentiment", title="二、情感分布", order=2, required=True,
                           data_binding=["sentiment_dist"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="top-issues", title="三、关键议题 TOP5", order=3, required=True,
                           data_binding=["top_issues"], llm_analysis=False, render_kind="list"),
            TemplateModule(anchor="severity", title="四、风险分级月度汇总", order=4, required=True,
                           data_binding=["severity_dist", "p0_p1_list"], llm_analysis=True, render_kind="table"),
            TemplateModule(anchor="platform", title="五、平台分布", order=5, required=True,
                           data_binding=["platform_dist"], llm_analysis=False, render_kind="list"),
            TemplateModule(anchor="disposition", title="六、处置状态统计", order=6, required=True,
                           data_binding=["status_dist"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="efficiency", title="七、处置效率统计", order=7, required=True,
                           data_binding=["status_dist"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="suggestions", title="八、下月监测建议", order=8, required=True,
                           data_binding=["top_issues", "p0_p1_list"], llm_analysis=True, render_kind="line"),
        ]
        name = "默认月报"
    else:
        modules = [
            TemplateModule(anchor="volume-overview", title="一、声量概览", order=1, required=True,
                           data_binding=["total_new_cases", "avg_prev_7days"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="sentiment", title="二、情感分布", order=2, required=True,
                           data_binding=["sentiment_dist"], llm_analysis=True, render_kind="line"),
            TemplateModule(anchor="top-issues", title="三、关键议题 TOP5", order=3, required=True,
                           data_binding=["top_issues"], llm_analysis=False, render_kind="list"),
            TemplateModule(anchor="severity", title="四、风险分级", order=4, required=True,
                           data_binding=["severity_dist", "p0_p1_list"], llm_analysis=False, render_kind="table"),
            TemplateModule(anchor="platform", title="五、平台分布", order=5, required=True,
                           data_binding=["platform_dist"], llm_analysis=False, render_kind="list"),
            TemplateModule(anchor="disposition", title="六、处置状态统计", order=6, required=True,
                           data_binding=["status_dist"], llm_analysis=True, render_kind="line"),
        ]
        name = "默认日报"

    return ReportTemplate(
        template_id=f"default-{report_type}", template_type=report_type, version=1, name=name,
        title_format="舆情月报 {{date}}" if report_type == "monthly" else "舆情日报 {{date}}",
        intro={"enabled": True, "prompt_hint": "一句话导语（日报用今日要点，月报用月度要览）"},
        modules=modules,
    )


# ── 模板持久化（用户自定义模板存 JSON；默认模板常驻代码） ───────────────

def _template_path(report_type: str, template_id: str) -> Path:
    return TEMPLATES_DIR / report_type / f"{template_id}.json"


def save_template(tpl: ReportTemplate) -> str:
    """保存模板为 JSON。返回文件路径。"""
    path = _template_path(tpl.template_type, tpl.template_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tpl.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_template(report_type: str, template_id: str) -> ReportTemplate:
    """加载模板；内置 default 或文件缺失时回退到代码内默认模板。"""
    if template_id in (f"default-{report_type}", "default", ""):
        return default_template(report_type)
    path = _template_path(report_type, template_id)
    if not path.exists():
        return default_template(report_type)
    try:
        return ReportTemplate.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return default_template(report_type)


def list_templates(report_type: str) -> list:
    """列出可用模板：内置默认 + 用户自定义 JSON。返回 [ReportTemplate]。"""
    templates = [default_template(report_type)]
    d = TEMPLATES_DIR / report_type
    if d.exists():
        for p in sorted(d.glob("*.json")):
            try:
                templates.append(ReportTemplate.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except Exception:
                continue
    return templates


def _active_path() -> Path:
    return TEMPLATES_DIR / "_active.json"


def get_active_template(report_type: str) -> ReportTemplate:
    """读取当前激活模板（缺省 default）。"""
    path = _active_path()
    if path.exists():
        try:
            active = json.loads(path.read_text(encoding="utf-8"))
            tid = active.get(report_type, "")
            if tid:
                return load_template(report_type, tid)
        except Exception:
            pass
    return default_template(report_type)


def set_active_template(report_type: str, template_id: str) -> None:
    """设置某报告类型的激活模板。"""
    path = _active_path()
    active = {}
    if path.exists():
        try:
            active = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            active = {}
    active[report_type] = template_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")

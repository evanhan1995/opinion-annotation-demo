# Spec: Report IR — 日报/月报结构化生成升级

## Objective

将日报/月报生成从"LLM 直出 Markdown → 人眼验收"升级为"代码管数据 + LLM 管分析 → 自动校验 → MD/HTML 同步渲染"。用户是舆情运营人员，日报每天看，月报对领导汇报。

**核心指标：**
1. 格式错误率从"偶尔发生"降至零（数据由代码填充，不会错）
2. MD 和 HTML 内容 100% 同步（同一 IR 渲染）
3. LLM 输出校验覆盖率 100%（非空、长度、无占位符残留）

## Tech Stack

- Python 3.12（现有环境）
- DeepSeek API（现有 `agents/shared.py` 的 `get_llm("deepseek")`）
- Plotly（现有，HTML 图表）
- 纯 Python dataclass（无新依赖）
- 无 jsonschema、无 Pydantic（不引入新包）

## Commands

```bash
# 测试
cd D:\Claude code\舆情标注Wiki
python -m pytest tests/ -x -q

# 单独测试 IR 模块
python -m pytest tests/ -x -q -k "report_ir"

# 启动 Streamlit 验证
python app.py
```

## Project Structure

```
D:\Claude code\舆情标注Wiki\
├── engine/
│   └── report_ir.py          # NEW: IR dataclass + build_ir + validate + render_md + render_html (~250行)
├── agents/
│   └── daily_report.py       # MODIFIED: 保留数据收集 + 入口函数，LLM调用改为 fill_analysis()
├── templates/
│   ├── daily_report_template.md   # 保持不变（作为章节结构参考）
│   └── monthly_report_template.md # 保持不变
├── wiki/reports/
│   ├── daily/                # 输出目录不变
│   └── monthly/              # 输出目录不变
└── tests/
    └── test_report_ir.py     # NEW: IR 构建/校验/渲染 单元测试
```

## Code Style

```python
# engine/report_ir.py 示例风格

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Chapter:
    """报告章节。data_rows 由代码填充，analysis 由 LLM 填充。"""
    anchor: str          # e.g. "volume-overview"
    title: str           # e.g. "一、声量概览"
    data_rows: dict      # 代码填：{total_new_cases: 15, avg_prev_7days: 12.3, trend: "下降"}
    analysis: str        # LLM 填："今日新增案例15条，较前7日均值下降18%..."
    chart: dict | None = None  # {type: "pie", labels: [...], values: [...]}

@dataclass
class ReportIR:
    report_type: str     # "daily" | "monthly"
    date: str            # "2026-06-01" | "2026-06"
    intro: str           # LLM 填的导语
    chapters: list[Chapter]
    metadata: dict

def build_ir(data: ReportData, report_type: str) -> ReportIR:
    """从 ReportData 构建 IR 骨架，data_rows 全部由代码填充，analysis 留空。"""

def fill_analysis(ir: ReportIR, retry_hint: list[str] | None = None) -> ReportIR:
    """调 LLM 一次，填充所有 chapter.analysis 和 ir.intro。返回更新后的 IR。"""

def validate_ir(ir: ReportIR) -> tuple[bool, list[str]]:
    """校验 IR：必填字段 + analysis 非空且 ≥20字 + 无 {{}} 残留。"""

def render_md(ir: ReportIR) -> str:
    """IR → Markdown 字符串。"""

def render_html(ir: ReportIR) -> str:
    """IR → 完整 HTML 字符串（含 CSS + Plotly 图表）。"""

def render_metric_cards(ir: ReportIR) -> str:
    """IR → HTML metric cards 片段（供 render_html 调用）。"""

def render_charts(ir: ReportIR) -> str:
    """IR → Plotly 图表 HTML 片段。"""
```

命名约定：
- 文件内私有函数：`_` 前缀（如 `_plot_pie_chart`）
- 对外 API：无前缀（`build_ir`, `validate_ir`, `render_md`, `render_html`）
- dataclass 字段：snake_case
- 类型注解必须（所有函数参数和返回值）

## Data Flow

```
ReportData ──→ build_ir(data, "daily")
                  │
                  ├─ 代码填充每个 Chapter.data_rows（数字、趋势、列表）
                  ├─ 代码填充每个 Chapter.chart（Plotly 所需数据）
                  ├─ analysis 字段全部留空 ""
                  │
                  ↓
              fill_analysis(ir)
                  │
                  ├─ 拼 prompt：模板结构 + data_rows 上下文 + example
                  ├─ 调 DeepSeek 一次
                  ├─ extract_json 解析 → {intro: "...", chapters: {"volume-overview": "...", ...}}
                  ├─ 填入各 Chapter.analysis + ir.intro
                  │
                  ↓
              validate_ir(ir)
                  │
                  ├─ 通过 → render_md(ir) + render_html(ir) → 保存
                  └─ 不通过 → fill_analysis(ir, retry_hint=errors) → validate_ir 再查
                                  → 仍不通过 → _build_daily_template(data) fallback
```

## ReportIR Chapter Definitions

### Daily Report (6 chapters)

| # | anchor | title | data_rows keys | LLM analysis |
|---|--------|-------|-----------------|--------------|
| — | (intro) | — | — | intro_one_sentence |
| 1 | volume-overview | 一、声量概览 | total_new_cases, avg_prev_7days, trend(↑/↓/→) | volume_analysis |
| 2 | sentiment | 二、情感分布 | positive_pct, neutral_pct, negative_pct | sentiment_highlight |
| 3 | top-issues | 三、关键议题 TOP5 | items: [str] | (无 LLM，纯数据) |
| 4 | severity | 四、风险分级 | p0-p3 counts + pcts, p0p1_events: [{title, platform, status}] | (无 LLM，纯数据) |
| 5 | platform | 五、平台分布 | {platform: count} | (无 LLM，纯数据) |
| 6 | disposition | 六、处置状态统计 | 5 status counts | disposition_analysis |

LLM 需填字段：`intro`, `volume_analysis`, `sentiment_highlight`, `disposition_analysis`（4 个文本字段）

### Monthly Report (8 chapters)

同上 1-6，加：

| # | anchor | title | data_rows keys | LLM analysis |
|---|--------|-------|-----------------|--------------|
| 7 | efficiency | 七、处置效率统计 | avg_processing_time, completion_rate, p0_24h_rate, p1_24h_rate | efficiency_analysis |
| 8 | suggestions | 八、下月监测建议 | top_issues, p0p1_list | next_month_suggestions |

LLM 需填字段：`intro(monthly_overview)`, `volume_trend_analysis`, `sentiment_analysis`, `severity_analysis`, `disposition_analysis`, `efficiency_analysis`, `next_month_suggestions`（7 个文本字段）

## Testing Strategy

**框架：** pytest（现有）

**新增测试文件：** `tests/test_report_ir.py`

**测试用例：**

| # | 测试 | 类型 | 覆盖 |
|---|------|------|------|
| 1 | `test_build_ir_daily` | 单元 | 从 ReportData 构建日报 IR，验证 data_rows 值正确 |
| 2 | `test_build_ir_monthly` | 单元 | 同上，月报，含环比数据 |
| 3 | `test_render_md_daily` | 单元 | IR → MD 字符串，验证 6 个章节标题全部出现、关键数字出现 |
| 4 | `test_render_md_monthly` | 单元 | 同上，月报 8 章节 + 环比表格 |
| 5 | `test_render_html_contains_charts` | 单元 | IR → HTML，验证含 plotly div、metric cards、CSS |
| 6 | `test_validate_pass` | 单元 | 合法 IR 校验通过 |
| 7 | `test_validate_fail_empty_analysis` | 单元 | analysis 为空字符串 → 校验失败 |
| 8 | `test_validate_fail_short_analysis` | 单元 | analysis 少于 20 字 → 校验失败 |
| 9 | `test_validate_fail_placeholder` | 单元 | analysis 含 `{{占位符}}` → 校验失败 |
| 10 | `test_md_html_sync` | 集成 | 同一个 IR 渲染 MD 和 HTML，验证关键数字同时出现 |
| 11 | `test_fallback_on_validation_failure` | 单元 | validate_ir 失败 → retry 逻辑触发 |
| 12 | `test_fill_analysis_mock` | 集成 | Mock LLM 返回，验证 analysis 正确填入 IR |

**运行：** `python -m pytest tests/test_report_ir.py -x -q`

**现有测试不受影响:** `daily_report.py` 入口函数签名不变，现有 `test_daily_report.py` 和 `test_daily_report_charts.py` 应继续通过。

## Boundaries

### Always do
- 运行 `python -m pytest tests/ -x -q` 后确认通过再标注完成
- 不改动 `generate_daily()` / `generate_monthly()` 的公开签名
- 保持 UTF-8 编码 + Windows 兼容（`sys.stdout` buffer 包装）
- 遵循 Agent 隔离规则（report_ir.py 不 import 任何 agent 模块）

### Ask first
- 新增 Python 依赖（当前设计不引入，如有需要先问）
- 修改 `ReportData` 字段（当前设计不涉及）
- 修改 templates/ 下的模板文件

### Never do
- 删除 `_build_daily_template()` / `_build_monthly_template()` fallback 函数（保留作为最后兜底）
- 修改 `pipeline.py` 的调用路径
- 直接 import agent 模块到 engine 层

## Success Criteria

1. `build_ir()` 生成的 IR 中，所有 data_rows 值与输入 `ReportData` 完全一致
2. `fill_analysis()` 在 LLM 正常时返回所有 analysis 字段均已填充的 IR
3. `validate_ir()` 能检出：空 analysis、短 analysis（<20字）、含 `{{` 或 `}}` 残留
4. `render_md()` 输出包含所有章节标题 + data_rows 数据 + analysis 文本
5. `render_html()` 输出为合法 HTML 文档（含 `<html>`, `<head>`, `<body>`, Plotly 图表 div）
6. 同一个 IR 的 `render_md()` 和 `render_html()` 中，数字和章节标题完全一致
7. LLM 失败 + 重试失败后，fallback 到旧模板生成（不抛异常，返回合法报告）
8. 12 个新增测试全部通过，现有测试零回归
9. 不改动 `generate_daily()` / `generate_monthly()` 签名，`pipeline.py` 调用无需修改

## Open Questions

- 如果 LLM 返回的 JSON 中部分字段有效、部分字段为空怎么办？→ 当前设计：任何字段失败都触发整体重试。如果重试后仍然部分失败，对失败的字段填入默认文本（如"暂无分析数据"），不丢整份报告。

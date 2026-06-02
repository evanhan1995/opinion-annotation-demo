# Report IR — 日报/月报结构化生成升级

## Problem Statement

**HMW: 让日报/月报从"LLM直出Markdown→人眼验收"升级为"代码管数据+LLM管分析→自动校验→MD/HTML同步渲染"？**

## Recommended Direction

**方案 F：模板驱动 + 结构校验（IR 缝合）**

核心思路：拆分职责。数据填充（数字、表格、图表）由代码做，LLM 只负责每个章节的 2-4 句分析文本。

```
ReportData ──→ 代码填充 ReportIR（chapter.title, chapter.data_context）
                    │
                    ↓
              LLM 逐章生成 analysis_text（只写分析段落，不写结构）
                    │
                    ↓
              validator（检查每章 analysis_text 非空 + 数据完整性）
                    │
                    ↓
              ReportIR ──→ render_markdown()  → .md 文件
                        └─→ render_html()     → .html 文件（含 Plotly 图表）
```

和 BettaFish 的区别：BettaFish 的 IR 是**通用报告引擎**（16 种 block 类型、支持任意模板），我们只需要 1 种固定结构（6-8 个章节），不需要 block 抽象层。数据结构从 ReportData 直接映射到 ReportIR，不做中间 JSON 转换。

## Key Assumptions to Validate

- [ ] LLM 逐章生成短分析文本比生成全文 Markdown 更稳定 — 改 prompt 后跑 3 次日报对比
- [ ] 6-8 章固定结构够用，短期内不需要动态章节 — 检查现有模板确认
- [ ] ReportIR 可以直接承载 Plotly 图表数据（不需要 LLM 参与） — 已确认，现有代码就是这样

## MVP Scope

### In
- `engine/report_ir.py`（~200行）：ReportIR dataclass + Chapter dataclass + `build_ir(data)` + `render_md(ir)` + `render_html(ir)` + `validate_ir(ir)`
- 改 `agents/daily_report.py`：`_build_daily_markdown()` → 先 `build_ir()` → 逐章调 LLM 填 `analysis_text` → `validate_ir()` → render
- 同步改月报路径
- Plotly 图表数据嵌入 IR，HTML 渲染从 IR 取数

### Out
- 不做通用 block 类型系统（heading/paragraph/list 那一套不需要）
- 不做模板动态选择（日报固定 6 章，月报固定 8 章）
- 不做 PDF 渲染（现有 HTML 可打印即可）
- 不做 IR 版本管理（单版本，以后需要再加）

## Not Doing (and Why)

- **通用 IR schema（BettaFish 的 16 种 block）** — 我们的报告结构固定，通用性是过度设计
- **双层 LLM 生成（结构+润色）** — 日报每天跑，双倍 API 调用不划算
- **Markdown 逆解析方案** — 解析歧义问题比"让 LLM 输出更短的内容"更难解决
- **砍掉 Markdown 只出 HTML** — Markdown 是 wiki 知识库的入口格式，不能丢
- **引入 jsonschema 依赖** — 纯 Python 校验够用，不增加依赖

## Open Questions

- 如果 LLM 某章的 analysis_text 连续 2 次校验失败，fallback 是整篇降级到旧模板，还是只那一章用默认文本？
- 月报的"处置效率统计"和"下月建议"两章，数据源不只是 ReportData（需要环比计算），是否需要在 build_ir 阶段加一个月报专用的数据预处理？

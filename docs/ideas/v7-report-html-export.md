# v7.0 专业报告 HTML 导出

## Problem Statement
HMW 将现有 Markdown 日报/月报升级为可交付客户/领导的专业交互式 HTML 报告（浏览器打开、可打印 PDF）？

## Recommended Direction
**方案 B — HTML 增强导出**：在现有 `daily_report.py:generate_daily_html()` 基础上，用纯 CSS + Plotly 打造专业报告：
- 封面页（标题、日期范围、机构名、摘要指标卡片）
- 美化排版（打印友好 CSS、品牌配色、Microsoft YaHei 字体）
- 新增图表：情感趋势折线图、词云（wordcloud 库）
- 离线化：内嵌 Plotly.js，不依赖 CDN
- 一键导出：UI 按钮下载完整 .html 文件

改动范围：`agents/daily_report.py`（HTML 模板重写 + 新图表函数）+ `ui/tab_knowledge.py`（下载按钮）。~120 行新增。

## Key Assumptions to Validate
- [ ] 客户接受 HTML 文件格式 — 先发样本确认
- [ ] `ReportData` 字段覆盖报告需求 — 已有 sentiment/severity/platform 分布
- [ ] wordcloud 库在 Windows 上安装无问题 — `pip install wordcloud` 测试

## MVP Scope
**In:** 日/月报 HTML 美化导出（封面+图表+离线化）、UI 下载按钮
**Out:** PDF 导出、情感模型替换、话题发现、Forum 升级

## Not Doing (and Why)
- WeasyPrint PDF — Windows 安装依赖 GTK，踩坑率高
- IR 中间表示层 — 当前规模不需要内容/表现分离
- 情感模型升级 — 本期焦点是"把已有的数据展示好"
- 话题自动发现 — 依赖新抓取管道，需独立 Phase

## Open Questions
- 报告机构名/Logo 用哪个？（config.json 新增字段？）
- 月报是否需要"月度环比"趋势图？（依赖多天数据查询）

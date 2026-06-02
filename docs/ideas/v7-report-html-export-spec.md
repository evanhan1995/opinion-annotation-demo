# Spec: v7.0 专业报告 HTML 导出

## Objective
将舆情标注Wiki的日报/月报从纯 Markdown 升级为**可交付客户/领导的专业交互式 HTML 报告**：
- 浏览器打开即看，打印即 PDF
- 封面页 + 指标卡片 + Plotly 交互图表
- 完全离线（内嵌 Plotly.js）
- 用户：舆情分析师 → 导出报告 → 发给客户/领导

## Tech Stack
- Python 3.14 + Streamlit（现有）
- Plotly（现有，v6.x+）
- 纯 HTML/CSS，零新依赖（wordcloud/WeasyPrint 均不引入）
- 内嵌 `plotly/package_data/plotly.min.js`（已验证存在）

## Commands
```
Run tests:   python -m pytest tests/test_daily_report_charts.py tests/test_daily_report.py -x -q
Run all:     python -m pytest tests/ -x -q
Dev:         streamlit run app.py
```

## Project Structure (改动范围)
```
agents/daily_report.py     ← 重写 generate_daily_html()     (~80 行改动)
                              新增 generate_monthly_html()   (~40 行)
                              新增 _build_html_shell()        (~50 行)
                              新增 _render_metric_cards()     (~15 行)
ui/tab_knowledge.py        ← 报告查看时加下载按钮              (~15 行)
```

## Code Style
现有 daily_report.py 的风格：模块级私有函数 `_snake_case`，公开函数不带前缀，`# ── Section ──` 分隔符，f-string 模板，`Path.write_text(encoding="utf-8")`。继续沿用。

核心模板骨架示例：
```python
def _build_html_shell(data, charts_html, report_type="daily"):
    """Return complete HTML document as str with inline Plotly.js."""
    plotly_js = _read_plotly_min_js()
    title = "舆情监测日报" if report_type == "daily" else "舆情监测月报"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title} {data.date}</title>
<style>{_CSS}</style>
</head>
<body>...{charts_html}...<script>{plotly_js}</script></body>
</html>"""
```

## Testing Strategy
- 复用现有 `tests/test_daily_report_charts.py`（140-108 行，5 个图表测试 + 2 个 HTML 测试）
- 新增测试：`test_html_offline_no_cdn`（验证无 CDN 引用）、`test_html_has_cover_page`（验证封面元素）、`test_monthly_html_creates_file`（月报 HTML）
- 所有 173 个已有测试必须保持通过
- 不需浏览器测试 — 验证 HTML 字符串包含关键元素即可

## Boundaries
- Always: 不改 Markdown 生成逻辑、不改 ReportData 结构、不改 curator、测试通过后才能标完成
- Ask first: 加新依赖、改 UI 布局（非报告相关）
- Never: 删现有测试、改 Markdown 报告路径、引入 WeasyPrint

## Success Criteria
- [ ] `generate_daily_html(data)` 生成无 CDN 引用的独立 HTML 文件
- [ ] HTML 包含：封面标题、4 个指标卡片、3 张 Plotly 图表、内嵌 Plotly.js
- [ ] 浏览器打开 HTML 可正常显示图表（离线环境）
- [ ] `generate_monthly_html(data)` 生成月报 HTML（封面标题区分日报/月报）
- [ ] 知识库 Tab 查看报告时显示"📥 下载 HTML 报告"按钮
- [ ] 点击按钮触发浏览器下载 .html 文件
- [ ] 打印预览（Ctrl+P）图表和卡片排版正常（@media print CSS）
- [ ] `python -m pytest tests/test_daily_report_charts.py -x -q` 全部通过
- [ ] `python -m pytest tests/ -x -q` 全部 173+ 通过

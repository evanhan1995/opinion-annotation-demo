# 舆情标注Wiki — AI 原生舆情指挥系统

基于 **6-Agent 协作架构** 的舆情监测与标注系统，覆盖从数据抓取、AI 研判、案例处置到日报生成的全链路。

## 核心架构

```
Monitor → Scraper → Analyst → Handler → Curator → Daily Report
  ↑                                                    |
  └────────────── Orchestrator (唯一跨Agent调度) ←────────┘
```

| Agent | 职责 | 引擎 |
|-------|------|------|
| Monitor | 关键词定时巡检、去重、Excel 存档 | 纯代码 |
| Scraper | 多平台内容抓取 + 评论采集 | 纯代码 |
| Analyst | 严重度/情感/标签 LLM 标注 | DeepSeek |
| Handler | 5 状态机处置跟进 + 方案生成 | DeepSeek |
| Curator | 知识库入库、索引同步、问答 | DeepSeek |
| Daily Report | 日报/月报自动生成 | DeepSeek |

## 覆盖平台

小红书 · 抖音 · YouTube · B站 · 微博 · 微信公众号 · X/Twitter · Reddit · 论坛

## 功能亮点

- **P0/P1 即时熔断** — 高危舆情 ≤1 分钟告警（桌面弹窗 + Webhook）
- **案例驱动的知识库** — 每新增案例自动检查标注规范边界，持续迭代标注精度
- **结构化标注输出** — LLM 出 JSON，代码层校验，失败自动重试 + fallback
- **HTML + Markdown 双格式报告** — Plotly 图表，专业排版
- **8-Tab Streamlit 工作台** — 手工录入 / URL 抓取 / Monitor 仪表板 / 案例处置 / 报告查看
- **定时调度器** — 巡检每 6h，日报 21:00，月报 1 日 09:00
- **人工喂料降级通道** — Scraper 失败时无缝切换人工输入

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web UI
streamlit run app.py --server.port 8501

# 启动调度器（守护进程）
python scheduler.py

# 运行全部测试
python -m pytest tests/ -x -q
```

## 项目结构

```
├── agents/         6-Agent 实现（orchestrator/monitor/analyst/handler/curator/daily_report）
├── engine/         核心引擎（scraper/annotate/ingestor/fetchers）
├── ui/             Streamlit 前端（8 Tab）
├── prompts/        Agent System Prompt
├── templates/      日报/月报模板
├── wiki/           知识编译输出层（AI 全权维护）
├── raw/            原始资料（只读）
├── outputs/        标注结果 + Excel + SEO 快照
├── docs/           设计文档 & 规格
├── scheduler.py    定时调度器
├── pipeline.py     5 步自动化管线
└── tests/          测试套件
```

## 技术栈

- **UI**: Streamlit
- **LLM**: DeepSeek (deepseek-chat)
- **数据抓取**: Playwright / yt-dlp / xhshow / bilibili-api / crawl4weibo
- **图表**: Plotly
- **知识库**: 文件系统 Markdown + YAML Frontmatter（Git 可追踪）
- **调度**: 自研 Python 守护调度器

## 运行环境

- Windows 11 + Python 3.14
- UTF-8 编码

## License

MIT

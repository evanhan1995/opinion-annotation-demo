# 舆情标注Wiki — 6-Agent 舆情指挥系统

## 命令

```bash
streamlit run app.py --server.port 8501   # Web UI
python scheduler.py                        # 定时调度器
python -m pytest tests/ -x -q             # 310 tests, 309 pass (1 预存失败)
```

## 架构

```
Monitor → Scraper → Analyst → Handler → Curator → Daily Report
  ↑                                                    |
  └────────────── Orchestrator ←───────────────────────┘
```

Agent 矩阵: monitor / scraper / analyst / handler / curator / daily_report / sentinel / forum / orchestrator

## 技术栈

Streamlit + DeepSeek (deepseek-chat) + Playwright + Plotly
知识库: 文件系统 Markdown + YAML Frontmatter (Git 可追踪)
Windows 11 + Python 3.14

## 关键陷阱

### Streamlit Deferred Pattern（违反必出 bug）
- **绝对不要在 `st.button()` handler 内调 `st.rerun()`**
- 正确做法: 按钮只做 清空 + 设 flag + rerun → 下次运行 Tab 块内执行实际工作
- 最终 rerun 用脚本末 `_needs_rerun` gate

### Settings 模块缓存
- 修改 `ui/tab_settings.py` 后 Streamlit 不自动重载已 import 的模块
- 需要 `importlib.reload(ui.tab_settings)` 或完全重启进程
- 已在 `app.py` line 584 加入 reload

### Ingestor 表格逻辑脆弱
- `_split_table_cells()` + `_upsert_dimension_row()` 维护 Markdown 表格
- 修改 index.md 表格逻辑时必须测 split→modify→rebuild 全周期

### yt-dlp 评论上限
- `max_comments=["50"]` 已配置在 scraper.py 中，不可删除

### JSON 配置文件 schema 容错
- `notification_config.json` webhooks 可能是字符串而非字典，需 isinstance 守卫
- `json.dumps(ensure_ascii=False)` 否则中文变 `\uXXXX`

### 测试先跑
- 代码修改后必须 `python -m pytest tests/ -x -q`
- 测试失败修代码，不修测试（除非测试预期本身错误）
- 1 个预存失败: `test_sentiment_ml.py::TestModelTraining`（与业务逻辑无关）

## 文件地图

| 目录 | 用途 |
|------|------|
| `app.py` | Streamlit 入口, 8 Tab |
| `agents/` | 10 个 Agent 模块 |
| `engine/` | 核心引擎 (scraper/annotate/ingestor/index_mgr) |
| `ui/` | Streamlit UI 组件 (12 .py) |
| `tests/` | 21 测试文件, 310 cases |
| `config/` | 运行时配置 (auth, scheduler, tracking) |
| `prompts/` | System prompt 模板 |
| `wiki/` | 知识库输出层 (AI 全权维护) |
| `raw/` | 爬虫原始数据 (只读) |
| `outputs/` | 标注结果 + Excel + SEO 快照 |

## 配置

- `engine/config.json` — API key + 密码 (gitignored)
- `.env` — 环境变量备选
- Streamlit Cloud Secrets — 部署用
- `engine/config.example.json` — 安全模板

## Git

Remote: `git@github.com:evanhan1995/opinion-annotation-demo.git`

## 深度文档

以下内容不适合放 CLAUDE.md（太长），需要时手动读取：
- `docs/CONTINUITY.md` — 完整关键路径 + 遗留注意事项
- `docs/WAKEUP.md` — 架构规则 + 错误反模式
- `docs/DESIGN.md` — 代码规模 + 路线图
- `docs/PRD.md` — 产品需求

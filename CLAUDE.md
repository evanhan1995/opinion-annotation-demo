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

### 微信公众号必须「会话内即时抓取」（不可回退为解析永久链接）
- 微信文章永久链接 = `__biz + mid + idx + sn` 四参数签名；搜狗跳转后 `sn` 不暴露在页面（`window.sn` 为空、HTML 无 `sn` 值），缺 `sn` 即「参数错误」。
- 旧的 `_extract_permanent_url`（解析永久链接）方向本身不可行，已删除。不要重新实现「拼 __biz 永久链接」的路子。
- 正确链路：`monitor` 的 wechat 分支在搜狗→微信跳转会话内，用 `_extract_wechat_page()` 当场提取正文四要素，写入 `engine/wechat_fetcher._ARTICLE_CACHE`；下游 `engine/scraper._scrape_wechat` 走 `get_cached_article()` 优先命中缓存。
- 缓存是**进程内内存**，进程退出即失效——「monitor 搜完立刻走 pipeline」可用；「存 Excel 下次进程再手动提交 URL」会回退到 Playwright 兜底（对过期临时链接仍失败）。这是微信反爬硬约束，非 bug。
- 公众号平台打破了「monitor 只搜链接、scraper 抓详情」的职责隔离——微信不允许延迟抓取，属刻意例外。

### JSON 配置文件 schema 容错
- `notification_config.json` webhooks 可能是字符串而非字典，需 isinstance 守卫
- `json.dumps(ensure_ascii=False)` 否则中文变 `\uXXXX`

### 飞书「立即处理」告警 — 两条独立路径
- 「分流建议 = 立即处理」需触发红色 error 级飞书告警（`shared/notify.send_urgent_disposal_card`），不是蓝色 info。
- **A 场景（新 URL 首次入库）**：`engine/ingestor.py` 的 ingest 通知段按 `annotation_result["分流建议"]` 分流——`立即处理` → urgent 红色告警；其他 → `send_new_pending_case_card` 蓝色卡片。
- **B 场景（已入库案例纠偏改成立即处理）**：`engine/correction_handler.py` 的 `handle_correction` 在 `"分流建议" in diffs` 且改后值为「立即处理」时触发 `_notify_urgent_disposal`。
- 两条路径独立、互不覆盖：ingest 有 dedup 早退（已存在 URL 走不到通知段），纠偏路径不经过 ingest。改其中一条时不要假设另一条会自动跟随。
- 防重复：B 场景仅在「分流建议」字段确实变更时触发，AI 本就判立即处理时不会重复告警。

### 日报飞书推送 — 单一来源 + 当日口径 + 情感字段
- 日报飞书推送的**唯一来源**是 `agents/orchestrator.py::_push_daily_report_feishu`，由 `run_daily_report()` 调用。scheduler 不得再单独推（会双推）。
- 卡片内容由 `agents/daily_report.py::build_daily_feishu_summary()` 从**当日** `ReportData`（`_collect_report_data(date_str)`）构造，数字必须与日报本体一致——不要用裸 `query_stats()`（那是全库累计口径）。
- **sentiment 字段**：case frontmatter 需写 `sentiment:`（`engine/ingestor.py::_generate_auto_case` 负责）；存量老 case 由 `agents/curator.py::_parse_case_frontmatter` 从正文「情感分析.整体情感」正则兜底解析。`query_stats` 的 `sentiment_dist` 必须含「混合」键，否则漏算。
- 推送失败只记 `_log.warning`（`_log = logging.getLogger("yuqing")`），不阻断日报生成。

### 测试先跑
- 代码修改后必须 `python -m pytest tests/ -x -q`
- 测试失败修代码，不修测试（除非测试预期本身错误）
- 1 个预存失败: `test_sentiment_ml.py::TestModelTraining`（与业务逻辑无关）
- **测试后清理（用户要求）**：全局 `pytest`（尤其 orchestrator/monitor 联网用例）会触发真实搜索/入库，污染真实知识库。跑完必须清理测试痕迹：删运行时残留（`config/model_degradation.json`、`config/scraper_degradation.json`、`outputs/monitor_*.xlsx`、`outputs/monitor_stats_*.json`），恢复被测试改写的 `wiki/index.md`/`wiki/embeddings/case_embeddings.json`/`wiki/taxonomy/candidate_tags.json`，删测试新建的 `wiki/cases/` 文件。⚠️ `raw/`、`outputs/keyword_feedback.jsonl` 是历史真实数据（5-6 月），勿整目录删除。

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

# 舆情标注系统 —— 深化设计方案

> 版本: v2.1.0 | 日期: 2026-08-19 | 状态: 6-Agent 舆情指挥系统 + 6 搜索平台 + 飞书告警/日报推送完成

---

## 1. 当前状态

### 1.1 已完成

**新架构 (agents/)** — 6-Agent 舆情指挥系统：
```
Orchestrator 编排 4 条流:
  流A: URL → Scraper → Analyst → [P0/P1熔断] → Handler → Curator ✅
  流B: Monitor(定时巡检×6平台) → for each → 流A + P0/P1熔断 ✅
  流C: Curator.query → Daily Report(日报/月报) → 飞书推送 ✅
  流D: KB Q&A(扫地僧) ✅

Agent 矩阵:
  Monitor   — 关键词×6平台搜索(douyin/youtube/xhs/bilibili/weibo/wechat) + Excel + SEO快照 ✅
  Scraper   — 10平台抓取 + 人工喂料降级 ✅
  Analyst   — DeepSeek标注 + 相关性判定 + 流式输出 ✅
  Handler   — 5状态机 + 处置方案 + 时间线记录 ✅
  Curator   — KB入库/索引/状态同步/问答/sentiment兜底 ✅
  Daily Rpt — LLM日报/月报 + 模板fallback + 飞书摘要 ✅
  Sentinel  — 预筛选（spam/ad 拦截，v6.0） ✅
  Forum     — 跨校验（contradiction 检测） ✅

Scheduler: 日报21:07 / 月报1日09:03 / 巡检每6h ✅
Notifications: P0/P1弹窗+音效+飞书卡片（熔断/立即处理A+B/日报） ✅
Streamlit: 8 Tab + 人工喂料UI ✅
```

**平台覆盖**：
- 搜索 6 平台：douyin / youtube / xiaohongshu / bilibili / weibo / wechat
- 抓取 10 平台：YouTube / 小红书 / 抖音 / B站 / 微博 / 微信公众号 / Reddit / X / Instagram / TikTok（后 4 预留）

**微信公众号会话内即时抓取**（2026-08 修复「参数错误」）：
- 永久链接 `__biz + mid + idx + sn` 四参数签名，`sn` 不暴露 → 缺 `sn` 即「参数错误」
- 方案：monitor 搜狗→微信跳转会话内用 `_extract_wechat_page` 即时抓正文 → `_ARTICLE_CACHE` → 下游 `_scrape_wechat` 优先读缓存

**飞书通知体系**（2026-08 完善）：
- P0/P1 熔断告警（`send_severity_card`）
- 「立即处理」A 场景（`ingestor` 新 URL 入库）+ B 场景（`correction_handler` 纠偏）
- 日报推送（`orchestrator` 单一来源，当日口径 + 情感分布）

### 1.2 代码规模

- ~24,000 行 Python（10 agent 模块 + 25 engine 模块）
- 22 测试文件，318 测试（1 预存失败 `test_sentiment_ml`，与业务无关）
- 110 Wiki 案例 + 72 作者页 + 词表/向量/日报月报

### 1.3 知识库资产

| 目录 | 数量 | 说明 |
|------|------|------|
| `wiki/cases/` | 110 个案例 | P0×1, P1×16, P2×2, P3×91，按平台分 5 子目录 |
| `wiki/authors/` | 72 个作者 | 跨平台作者聚合页 |
| `wiki/taxonomy/` | 4 文件 | 叙事分类/风险标签/处置动作/候选标签 |
| `wiki/reports/` | daily + monthly | 日报/月报 |
| `wiki/embeddings/` | 1 文件 | 语义检索向量（59 条） |

### 1.4 最近一轮工作（2026-08）

| # | 内容 |
|---|------|
| 1 | 微信公众号「参数错误」→ 会话内即时抓取 + 缓存 |
| 2 | 飞书「立即处置」A 场景（ingest）+ B 场景（纠偏）告警 |
| 3 | 日报飞书推送（手动/定时/CLI 全覆盖 + 当日口径 + 情感字段修复） |
| 4 | sentiment 统计修复（frontmatter 写入 + 存量兜底 + 「混合」键） |
| 5 | 死代码清理（fetch_wechat_article / _error） |
| 6 | case 数据核查（110 条自洽，无残留） |

---

## 2. 路线图

### ✅ 已完成 (Phase 1-10a)

| Phase | 内容 |
|-------|------|
| 1-6 | 核心管线（抓取→标注→Ingest→Agent→纠偏→Web UI） |
| 7 | 架构清理（index_mgr + 21 测试 + correction_handler 修复） |
| 8 | 体验优化（流式标注 + Dashboard + 引用可点击 + Demo 引导） |
| 9 | 可观测性（纠偏率监控 + Cookie 告警 + GitHub Push） |
| 10a | 跨条目关联（linker.py：bigram 加权评分 + synthesis 自动生成） |
| 10a-opt | 性能优化（yt-dlp 限评论 50、wait_for_selector、deferred annotation 模式、prompt 缓存、_needs_rerun gate） |
| 10b | 扫地僧关联查询（AGENT_SYSTEM_PROMPT 跨平台引导 + build_agent_context synthesis 展开 + 表格化输出） |
| 10c | 边界检查 → Draft PR 建议（`_generate_boundary_suggestion` 三触发 + UI diff 呈现） |
| 10d | ingestor 表格结构化（`_parse_row_to_dict`/`_dict_to_row` + overview row dict 构建，dimension 保留 `_upsert_dimension_row`） |
| 11a | 批量导入（多 URL text_area + 进度条 + 摘要表，deferred pattern 复用） |
| 11b | 标注历史回溯（find_annotation_history + diff_annotations + 时间线 expander） |
| 11c | 巡检监控（monitored_urls.json 配置 + 侧边栏巡检按钮 + 批量检查 + P0/P1 计数） |
| 11d | P0/P1 醒目告警（标注结果页红色/黄色横幅 + severity/action/summary 三要素） |
| 17a | app.py 拆分（302行入口 + ui/shared.py + sidebar.py + tab1/2/5，纯移动零变更） |
| 17b | 测试补盲（27 集成测试：deferred flow + tab 隔离 + 文件 I/O + ingest 错误处理） |
| 17c | XHS Cookie 攻坚（GET 签名统一走 xhshow 标准 API，补 x-xray-traceid，5 回归测试） |
| 18 | Scraper 架构升级（XHS: XHS-Downloader cookie-free 元数据 + xhshow 评论；抖音: TikTokDownloader 新接入；69 测试零回归） |

### 🔵 6-Agent 舆情指挥系统 (PRD Phases 1-5) — ✅ 全部完成

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | Agent 骨架：7模块 + shared + orchestrator + dataclass | ✅ |
| Phase 2 | engine/ → agents/ 迁移 (Facade) + 34 case KB 迁移 | ✅ |
| Phase 3 | 三平台搜索 + Excel + P0/P1告警 + SEO快照 + LLM日报 + 状态机同步 | ✅ |
| Phase 4 | 调度器 + 通知 + MiniMax验证 | ✅ |
| Phase 5 | UI: Monitor仪表板 + 案例处置 + 报告查看 + 人工喂料 | ✅ |

### 🟡 增量提质

| # | 任务 | 说明 | 预估 |
|---|------|------|------|
| 18a | 纠偏率可观测 | URL 级一致率统计，驱动 prompt 调优 | 2h |
| 18b | 案例质量巡检 | 扫描 case frontmatter 必填字段完整性 | 1h |
| 18c | Demo 数据外部化 | DEMO dict → demo_data.json，非开发人员可编辑 | 1h |

### 🟣 远期 (依赖前置)

| # | 任务 | 说明 |
|---|------|------|
| 19 | 小红书图片OCR+视频ASR | PaddleOCR + Whisper |
| 20 | 向量检索 | 案例 >200 时引入 embedding + vector search |
| 21 | 多语言 + A/B | 非中文舆情翻译；不同 prompt 版本准确率对比 |
| — | 微博/微信/新闻站点 | PRD §1.3 平台扩展路线图 Phase 6-7 |

---

## 3. 架构原则

1. **raw/ 永不修改** —— 原始数据只追加，不覆盖
2. **wiki/ 由 AI 全权维护** —— 人类通过投放案例和纠偏间接影响
3. **每次操作有日志** —— wiki/log.md append-only
4. **规则来自案例** —— 不凭空调整标注规范
5. **Demo 优先** —— 改动不能破坏 Web UI 基本可用性
6. **信息闭环** —— 任何自动生成的信息必须能被未来的系统消费
7. **共享逻辑不复写** —— 同一函数出现两次立即提取到共享模块
8. **安全纵深** —— 敏感数据（API Key、知识库内容、Cookie）分层保护，密码不在源码中

---

## 4. 关键设计决策

| 决策 | 原因 | 日期 |
|------|------|------|
| 不引入向量数据库 | wiki < 50 页，关键词+frontmatter 搜索足够 | 2026-05-12 |
| PROMPT_LAYERS 动态化 | 新案例不回灌=反馈回路断裂 | 2026-05-12 |
| 扫地僧用关键词搜索 | 中文 bigram 分词已覆盖查询需求 | 2026-05-12 |
| Ingest 自动触发 | Demo 需要"系统感" | 2026-05-12 |
| 纠偏与自动Ingest并存 | 两种案例模板不同 | 2026-05-12 |
| Phase 7 架构清理先于功能 | 双轨 index 逻辑=定时炸弹 | 2026-05-13 |
| Linker 仅比较原文内容 | 标注模板共享 boilerplate 导致 97% 噪声 | 2026-05-13 |
| 知识库密码三级源 | st.secrets(Cloud) → env(CI) → config.json(local)，源码零密码 | 2026-05-13 |
| yt-dlp 限制评论 50 条 | 7,626 评论视频抓取 171s，不限量=不可用 | 2026-05-14 |
| Wait-for-selector 替代固定等待 | Playwright `wait_for_timeout` 无条件空等 2-3s | 2026-05-14 |
| Deferred annotation 模式 | 按钮先清空旧结果再委托下次运行，避免新旧内容混淆 | 2026-05-14 |
| Streamlit rerun gate 在脚本末 | `st.rerun()` 在 button handler 内会引发双层重跑竞态 | 2026-05-14 |
| XHS 杂交方案而非全量替换 | XHS-Downloader 不支持评论抓取，元数据+评论双信道独立 | 2026-05-16 |
| `_pending_tab` 延迟切换 | Streamlit widget 实例化后不可修改其 session_state key，需在 radio 前注入 | 2026-05-16 |
| TikTokDownloader 程序化调用 | 不走 TUI，直接 import Detail/Comment 接口 + `asyncio.run()` 包装 | 2026-05-16 |

---

*随项目推进持续更新。每次 Phase 完成后更新第 1 节和第 2 节。*

# 舆情标注系统 —— 深化设计方案

> 版本: v2.0.0 | 日期: 2026-05-23 | 状态: PRD Phases 1-5 全部完成（6-Agent 舆情指挥系统）

---

## 1. 当前状态 (v1.2.0)

### 1.1 已完成

**旧管线 (engine/)**：
```
用户输入 URL 或手动粘贴
  → scraper.py（5平台 + 通用回退）✅
  → raw/cases/ 落盘 ✅
  → annotate.py（LLM 标注 + 流式输出 + 动态案例回灌）✅
  → outputs/ 落盘 ✅
  → ingestor.py（Wiki 案例生成 + 三维索引 + 归档 + 跨条目关联）✅
  → raw/archive/ 归档 ✅
  → correction_handler.py（人工纠偏 → 校准案例）✅
  → agent.py（扫地僧：知识库问答）✅
  → linker.py（跨平台关联检测）✅
  → Web UI（5 Tab：手工录入 / URL抓取 / 知识库🔒 / 扫地僧 / 操作演示）✅
```

**新架构 (agents/)** — PRD v1.2 6-Agent 舆情指挥系统：
```
Orchestrator 编排 4 条流:
  流A: URL → Scraper → Analyst → [P0/P1熔断] → Handler → Curator ✅
  流B: Monitor(定时巡检) → for each → 流A ✅
  流C: Curator.query → Daily Report(日报/月报) ✅
  流D: KB Q&A(扫地僧) ✅

Agent 矩阵:
  Monitor   — 关键词双维度搜索(YouTube/抖音/XHS) + Excel导出 + SEO快照 ✅
  Scraper   — 三平台抓取 + 人工喂料降级 ✅
  Analyst   — DeepSeek标注 + 相关性判定 + 流式输出 ✅
  Handler   — 5状态机 + DeepSeek处置方案 + 时间线记录 ✅
  Curator   — KB入库/索引/状态同步/问答 ✅
  Daily Rpt — LLM日报/月报 + 模板fallback ✅
  
Scheduler: 日报21:07 / 月报1日09:03 / 巡检每6h ✅
Notifications: P0/P1 PowerShell弹窗 + 系统音效 + Webhook ✅
Streamlit: 8 Tab (新增 Monitor / 案例处置 / 报告) + 人工喂料UI ✅
```

### 1.2 代码规模

**engine/ (旧管线 — 被 agents/ 包裹)**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `engine/annotate.py` | 844 | LLM 标注引擎 |
| `engine/xhs_fetcher.py` | 590 | 小红书双通道抓取 |
| `engine/scraper.py` | 505 | 多平台抓取调度 |
| `engine/ingestor.py` | 520 | 自动 Ingest 管线 |
| `engine/agent.py` | 331 | 扫地僧问答引擎 |
| `engine/tt_fetcher.py` | 313 | 抖音抓取器 |
| `engine/linker.py` | 312 | 跨平台关联检测 |
| `engine/correction_handler.py` | 266 | 人工纠偏处理器 |
| `engine/index_mgr.py` | 265 | 共享索引管理器 |
| `engine/debug_xhs.py` | — | Cookie 诊断脚本 |

**agents/ (新架构 — 6-Agent 舆情指挥系统)**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `agents/orchestrator.py` | ~370 | 4条流编排 + P0/P1熔断 + 状态同步 |
| `agents/monitor.py` | ~500 | 三平台搜索 + Excel + SEO快照 |
| `agents/analyst.py` | ~140 | DeepSeek标注 + 相关性判定 |
| `agents/curator.py` | ~260 | KB入库/索引/状态同步/问答 |
| `agents/handler.py` | ~120 | 5状态机 + DeepSeek处置方案 |
| `agents/daily_report.py` | ~270 | LLM日报/月报 + 模板fallback |
| `agents/scraper.py` | ~130 | 三平台抓取门面 + 人工喂料 |
| `agents/shared.py` | 178 | 模型工厂 + dataclass + JSON工具 |

**ui/ (Streamlit)**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | ~370 | 8 Tab入口 + 人工喂料UI |
| `ui/shared.py` | 596 | 共享渲染函数 |
| `ui/sidebar.py` | 158 | 侧边栏 |
| `ui/tab2_url.py` | 180 | URL 抓取 |
| `ui/tab1_manual.py` | 117 | 手工录入 |
| `ui/tab3_monitor.py` | ~65 | **新增** — Monitor 仪表板 |
| `ui/tab4_disposition.py` | ~90 | **新增** — 案例处置 |
| `ui/tab6_reports.py` | ~60 | **新增** — 报告查看 |
| `ui/tab5_demo.py` | 124 | 操作演示 |

**基础设施**：

| 文件 | 职责 |
|------|------|
| `scheduler.py` | **新增** — 定时调度器 (日报21:07/月报09:03/巡检每6h) |
| `monitor_keywords.json` | 关键词+品牌词配置 |
| `notification_config.json` | P0/P1 Webhook 配置 |
| `prompts/` (4文件) | Agent System Prompt 独立存放 |

**测试：8 文件 111 测试全通过**

### 1.3 知识库资产

| 目录 | 数量 | 说明 |
|------|------|------|
| `wiki/cases/` | 18 个案例 | P0×1, P1×4, P2×9, P3×4 — 含抖音+小红书新增 |
| `wiki/authors/` | 5 个作者 | 跨平台作者聚合页 |
| `wiki/concepts/` | 5 篇 | 严重度/情感/分流/真实性/平台 |
| `wiki/entities/` | 2 篇 | Meltwater / 新浪舆情通 |
| `wiki/sources/` | 2 篇 | Evan 的 TEMU + DJI 复盘 |
| `wiki/syntheses/` | 1 篇 | 标注规范活文档 |
| `raw/cases/` | 7 个文件 | 待处理原始抓取 |
| `raw/archive/` | 7 个文件 | 已处理归档 |
| `outputs/` | 7 个文件 | 标注结果存档 |

### 1.4 Phase 18 变更

| # | 问题 | 修复 |
|---|------|------|
| 1 | index.md Wiki 链接格式损坏 | `_split_table_cells()` protect-split-restore |
| 2 | P1 严重度盲区 | case-010 + 用户自建 case-012 |
| 3 | 去重全文件扫描 | frontmatter `url:` 字段匹配 |
| 4 | 标注结果残留在扫地僧 Tab | `_render_annotation_result()` 移入 Tab1/Tab2 |
| 5 | Tab1/Tab2 widget key 重复 | 13 个组件 `key_prefix` 前缀 |
| 6 | 分流建议维度从不更新 | `_update_case_index()` 新增 action 维度 |
| 7 | 平台字段总是 `?` | 从 scraped_data 取而非 annotation_result |
| 8 | correction_handler 独立 index 逻辑 | 统一到 `index_mgr.py` |
| 9 | session_state 初始化顺序 | 先 init 再用，demo_guide_shown 纳入统一初始化 |
| 10 | 知识库密码保护缺失 | 三级密码源：st.secrets → os.getenv → config.json |

### 1.5 性能优化轮次 (2026-05-14)

| # | 问题 | 修复 |
|---|------|------|
| 11 | yt-dlp 抓取 7,626 评论视频耗时 171s | `max_comments=["50"]` 限制评论数，降至 3s |
| 12 | Playwright 无条件 `wait_for_timeout(2-3s)` | 改为 `wait_for_selector` 按内容就绪触发 |
| 13 | 连续标注第二个 URL 页面残留旧结果 | deferred annotation 模式：按钮先清空再委托下次运行 |
| 14 | `build_system_prompt()` 每次标注重读 21 文件 | 缓存在 `st.session_state.cached_system_prompt` |
| 15 | `st.rerun()` 在 button handler 内部双层重跑竞态 | 回退延迟 ingest，改为脚本末 `_needs_rerun` 单次 gate |
| 16 | 扫地僧不支持跨平台查询 | AGENT_SYSTEM_PROMPT 新增跨平台引导 + `build_agent_context` synthesis 自动展开关联案例 |
| 17 | 边界盲区仅显示 flag 无行动建议 | `_generate_boundary_suggestion()` 生成 Draft PR 式修改建议，UI 以 diff 格式呈现 |
| 18 | overview 行用 f-string 硬拼接 | `_parse_row_to_dict()`/`_dict_to_row()` 结构化构建，header 已知常量 |
| 19 | 只能逐条标注，无批量入口 | Tab2 新增批量模式（checkbox + text_area + 进度条 + 摘要表） |
| 20 | 无标注历史，无法对比变化 | `find_annotation_history` + `diff_annotations` + 时间线 expander |
| 21 | 无监控/巡检能力 | `monitored_urls.json` + 侧边栏巡检按钮 + P0/P1 计数 |
| 22 | P0/P1 案例无醒目提示 | 标注结果顶部 error(红)/warning(黄) 横幅 + 三要素 |

### 1.6 架构债务

| # | 问题 | 严重度 | 计划 |
|---|------|--------|------|
| 1 | ingestor 字符串拼接维护 Markdown 表格 | 中 | 案例 >50 时结构化（当前 13 无需） |
| 2 | ~~app.py 近千行单文件~~ | ~~低~~ | ✅ Phase 17a 完成：302 行入口 + 5 个 ui/ 模块 |

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

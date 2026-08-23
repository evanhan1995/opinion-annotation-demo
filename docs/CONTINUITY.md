# 项目持续性 Prompt

> 在新对话中粘贴此 Prompt，让 Claude Code 快速理解项目全貌并继续开发。

---

## 唤醒 Prompt（复制到新对话）

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态（6-Agent 舆情指挥系统）和路线图，再读 WAKEUP.md 了解架构规则和陷阱。
确认理解后告诉我：
1) 项目目前做到什么地步
2) 下一步是什么
3) 上次会话遗留的注意事项
```

---

## 项目是什么

一个基于 LLM + Wiki 知识库的舆情智能标注系统。用户输入舆情链接（小红书/抖音/YouTube/B站/微博/微信公众号/Reddit/X），系统自动抓取内容 + 评论区 → AI 标注（严重度 P0-P3、分流建议、情感分析、风险标签、评论区红绿灯） → 自动存入知识库 → 知识库驱动 AI 标注越来越准。另有 Monitor 关键词巡检 + 飞书告警 + 日报推送。

**最终用户**：HR（Demo 展示用）+ Evan 自己（实际舆情工作用）。

**Web Demo**：https://opinion-annotation.streamlit.app（Streamlit Cloud）

**GitHub**：https://github.com/evanhan1995/opinion-annotation-demo

---

## 当前版本

**6-Agent 舆情指挥系统**（持续迭代中，代码注释含 sentinel v6.0 / report_ir v7.1 模块级标记）。
- ~24,000 行 Python，10 agent 模块 + 25 engine 模块 + 35 测试文件（452 例收集，441 passed）
- 344 个案例文件（分平台子目录：wechat/douyin/bilibili/weibo/xiaohongshu/youtube）+ 72 作者页 + 词表/向量/日报月报
- 搜索 6 平台（douyin/youtube/xiaohongshu/bilibili/weibo/wechat），抓取 10 平台（含 Reddit/X/Instagram/TikTok 预留）
- 飞书通知：P0/P1 熔断 + 「立即处理」A/B 双场景 + 日报推送（当日口径 + 情感分布）
- 微信公众号会话内即时抓取（解决「参数错误」，不可回退为解析永久链接）
- 情感统计修复（frontmatter 写入 + 存量兜底解析 + 「混合」键）

---

## 一句话架构

```
URL → scraper(10平台) → raw/cases/ → annotate(LLM+动态案例回灌+流式) → outputs/
                                            ↘ ingestor(→index_mgr) → wiki/cases/ (+ index, log, archive)
                                            ↘ linker -> syntheses/ (跨平台关联)
                                            ↘ agent (扫地僧问答, 含syntheses检索)
                                            ↘ correction_handler(→index_mgr) (人工纠偏)
                                            ↘ 飞书告警（ingest A场景 + correction B场景）
Monitor(关键词×6平台) → [for each] → 流A + P0/P1熔断 + 飞书
Daily Report → 日报/月报 → 飞书推送（orchestrator 单一来源）
```

---

## 文件地图

| 文件 | 行数 | 一句话 |
|------|------|--------|
| `app.py` | ~1000 | Streamlit 8 Tab UI。Deferred annotation 模式：按钮清空→委托下次运行→`_needs_rerun` gate |
| `agents/orchestrator.py` | ~440 | 4条流编排 + P0/P1熔断 + 状态同步 + 日报飞书推送单一来源 |
| `agents/monitor.py` | ~1100 | 关键词×6平台搜索 + Excel导出 + 去重归档 + 日期模式 |
| `agents/curator.py` | ~400 | KB入库/索引/状态同步/问答 + sentiment 兜底解析 + query_stats |
| `agents/daily_report.py` | ~400 | LLM日报/月报 + build_daily_feishu_summary（当日口径） |
| `engine/scraper.py` | ~1050 | 10平台抓取调度 + _scrape_wechat（优先读会话缓存） |
| `engine/wechat_fetcher.py` | ~340 | 搜狗搜索 + 会话内即时抓取（_extract_wechat_page + _ARTICLE_CACHE） |
| `engine/ingestor.py` | ~700 | 自动 Ingest + sentiment 写入 + 飞书「立即处理」A场景告警 |
| `engine/correction_handler.py` | ~290 | 纠偏处理 + 飞书「立即处理」B场景告警 |
| `engine/annotate.py` | 844 | LLM 标注引擎。动态 PROMPT_LAYERS + 流式生成器 |
| `engine/xhs_fetcher.py` | 590 | 小红书双通道抓取 + Cookie 管理 |
| `engine/linker.py` | 312 | 跨平台关联检测 |
| `engine/index_mgr.py` | 265 | 共享 index 更新 |
| `shared/notify.py` | ~200 | 飞书卡片（urgent/severity/pending/daily 四类） |
| `scheduler.py` | ~420 | 定时调度器（日报/月报/巡检），日报推送已收敛到 orchestrator |
| `tests/` | 35 文件 | 441 passed（约 11 skip，452 例收集） |

---

## 关键路径

```
app.py 标注按钮点击
  → st.session_state 清空旧结果 + _annotate_url flag + st.rerun()
  → 下次运行：deferred annotation block (Tab 内)
  → scraper.scrape(url)           # 抓取 + 写 raw/cases/
  → annotate.format_user_message() # 格式化
  → annotate.annotate_one_stream() # 流式 LLM 调用
  → app._save_annotation_output()  # 写 outputs/
  → app._do_ingest()               # → ingestor.ingest()
      → _find_existing_case_by_url()  # 去重
      → _generate_auto_case()          # 写 wiki/cases/case-XXX.md
      → index_mgr.update_case_index()  # 更新 index.md
      → _update_global_index()         # 更新 wiki/index.md
      → _append_ingest_log()           # 写 wiki/log.md
      → _archive_raw_file()            # 移动 raw/cases/ → raw/archive/
      → linker.auto_link()             # 跨平台关联检测
  → _needs_rerun gate (脚本末) → st.rerun()  # 最终刷新
```

---

## 配置和密钥

| 位置 | 字段 | 说明 |
|------|------|------|
| `engine/config.json` | `api_key` | DeepSeek API Key（gitignored） |
| `engine/config.json` | `kb_password` | 知识库密码（gitignored） |
| `engine/.xhs_cookies.json` | — | 小红书 Cookie（gitignored） |
| 环境变量 | `DEEPSEEK_API_KEY` | API Key 备选 |
| 环境变量 | `KB_PASSWORD` | 知识库密码备选 |
| Streamlit Cloud Secrets | `KB_PASSWORD` | Cloud 部署用 |
| `engine/config.example.json` | — | 模板文件（可提交） |

---

## 上次会话遗留注意事项

1. **测试先跑**：`python -m pytest tests/ -x -q`，441 passed（约 11 skip，联网/cookie 依赖用例）。
2. **ingestor 脆弱**：`_split_table_cells()` 和 `_upsert_dimension_row()` 维护 Markdown 表格。修改时务必测 split→modify→rebuild 全周期。
3. **Streamlit 共享函数必须 key_prefix**：多 Tab 调用同一函数时所有 stateful 组件需要前缀。
4. **linker 阈值**：SIMILARITY_THRESHOLD=0.25, MIN_BIGRAM_OVERLAP=3。只比较原文内容（排除模板）。
5. **知识库密码**：三级源 `st.secrets → env → config.json`，无密码时向后兼容。
6. **案例数量**：344 个案例文件（分平台子目录）。新增后检查 index.md 三维索引完整性。
7. **st.rerun() 反模式**：绝对不要在 button handler 内调用 `st.rerun()`。使用 deferred pattern：按钮只做清空+设 flag+rerun，实际工作在下次运行的 tab 块内完成。最终 rerun 用脚本末 `_needs_rerun` gate。
8. **yt-dlp 评论上限**：`max_comments=["50"]` 已配置在 scraper.py 中，不要删除此限制。
9. **系统 prompt 按需构建**：已移除 `cached_system_prompt`。每次标注调用 `build_system_prompt(content)[0]`，按内容相关性选 top-5 案例。
10. **微信公众号会话内抓取**：永久链接 `sn` 签名拿不到，只能 monitor 搜狗→微信跳转会话内即时抓正文并缓存（`_ARTICLE_CACHE`），下游 `_scrape_wechat` 优先读缓存。不要回退为「拼 __biz 永久链接」。
11. **飞书「立即处理」双路径**：A 场景在 `ingestor`（新 URL 入库），B 场景在 `correction_handler`（纠偏改立即处理）。两条独立，改一条别假设另一条跟随。
12. **日报飞书推送单一来源**：只在 `orchestrator._push_daily_report_feishu`，scheduler 不得再推（会双推）；内容用当日 `ReportData`，别用裸 `query_stats()`。
13. **sentiment 字段**：新 case 由 ingestor 写 frontmatter `sentiment:`；存量 case 由 curator `_parse_case_frontmatter` 从正文 JSON 兜底；`query_stats` 的 `sentiment_dist` 须含「混合」键。

## 项目当前状态

6-Agent 舆情指挥系统完整可用。当前 344 案例文件、441 测试、6 搜索平台 + 10 抓取平台。最近一轮工作（2026-08）：
- 微信公众号「参数错误」根因修复（会话内抓取）
- 飞书「立即处置」A/B 场景告警
- 日报飞书推送（手动/定时/CLI 全覆盖 + 当日口径 + 情感字段修复）
- 死代码清理（fetch_wechat_article）

下一步候选（见 DESIGN.md 路线图）：微博/微信/新闻站点平台扩展、向量检索（案例 >200）、小红书 OCR/ASR。

---

## 2026-08-21~22 会话记录（最近）

### 已完成并提交（本次会话 ~14 个提交，已 push origin/master）
- `b29e858` case_id 统一（get_next_case_id 线程安全 + ActionPlan 对齐）
- `e7b37be` 静默吞错修复（scraper/monitor 31 处 except:pass → 日志 + error SearchResult 区分失败/空）
- `4d51384` 爬虫降级追踪持久化（_SCRAPER_FAILURES → config/scraper_degradation.json，3 失败/2 成功滞后）
- `0916ab0` MonitorStats 持久化 + daily_report 真实监测概况（outputs/monitor_stats_{date}.json，无数据→「无监测数据」）
- `ec9d87f`/`bb6db6a` XHS/抖音 live 测试反爬 skip 容错
- `ab8a44d` 报告系统骨架（FinalReport 统一缓存 + ReportTemplate 模板驱动 build_ir + render_feishu + 模板学习 UI）
- `43be2cc` daily_report 完整接入（FinalReport 流程 + 监测概况章节）
- `9b2938b` notify 重构收尾（通知绑定录入研判提交、巡检抑制飞书、删 send_new_pending_case_card 死代码）
- `92a350b` 报告模板管理 Tab 正式接入（auth 权限 + app 路由 + 测试）
- `d878516` LLM 降级链（见下）
- `3b1982a` Monitor 关键词配置防误清空（_save_keywords_config 保护）

### 本次会话追加提交（08-22 晚 ~ 08-23，3 提交）
- `26edbd8` RAG 检索元数据加权（查询命中平台/严重度时对同类案例温和加权）——`tests/test_metadata_weighting.py`
- `b364180` P0/P1 双 Agent 复核（独立 Agent 复核 severity，分歧不压制告警但标记存疑）——`tests/test_reviewer.py`
- `2da4ce3` case_id 撞号复发修复（见下专节）

#### case_id 撞号：根因 + 修复 + 数据迁移（2da4ce3 完整来龙去脉）

**现象**：tab4 对 case085 抛 `StreamlitDuplicateElementKey`（`st.selectbox(key=f"status_sel_{case_id}")` 撞 key），排查发现 399 个 case 文件里约 130 个 stem（`case-XXX`）重复，`query_cases` 返回重复 `case_id`。

**根因**：两套写入路径各用各的编号——`engine/ingestor` 写平台子目录（新格式）、`agents/curator.ingest` 兜底写扁平目录（旧格式），且计数器 `get_next_case_id` 跨进程重播种，同一编号被不同平台复用。

**关键不变量（下次改动务必遵守）**：`case_id`（文件名 stem）必须**全局唯一**（跨所有平台子目录），因为 `update_case_status` / `handle_status_transition` / `append_timeline` 都按裸 `case_id` 定位文件。

**数据迁移**（`temp/migrate_case_ids.py`，dry-run 默认、`--apply` 执行，已跑）：399 → 344 文件——删 55 扁平重复、迁 18 唯一扁平到平台子目录、gap-fill 重编号（唯一号保留、撞号重排到 max+1）→ 从文件重建 index.md。备份 `temp/cases_backup_20260823/`、映射 `temp/case_id_mapping.json`。⚠️ `wiki/cases/` 被 `.gitignore` 排除，git 无法备份，迁移前必须文件复制。

**修复 4 处复发源头**（commit 2da4ce3，5 文件 +64/-16）：
1. `engine/index_mgr.py` — `case_ref` 支持 `platform_subdir`，`_is_table_row` 正则兼容 `[[cases/<平台>/case-NNN]]`
2. `engine/ingestor.py` — `_update_case_index` 传 `platform_subdir`
3. `engine/correction_handler.py` — 纠偏索引收真实 `platform`（不再硬编码「—」）并传 subdir
4. `agents/curator.py` — 兜底写平台子目录；移除 `update_case_status` 里参数错位的 `update_case_index` 调用（索引脏行 `| [[cases/case-016|016]] | ...` 的来源）
5. `tests/test_core.py` — 新增 subdir 链接 / `_is_table_row` 3 项测试

### LLM 降级链（d878516，核心新功能）
- **Analyst**：`engine/annotate.py::annotate_with_fallback`（deepseek → minimax[需配 key] → Sentinel 规则预标注）；失败/JSON 解析失败同走链；`agents/analyst.py::annotate` 接入，Annotation 增 `degraded`/`degraded_reason`
- **Curator**：`engine/agent.py::answer_from_search_only`（bigram 检索直接拼接，回答带「⚠️ 模型暂不可用」提示）；`ask_agent` except 分支降级
- **DailyReport**：`engine/report_ir.py::fill_analysis` 补 call_with_timeout，失败→模板回退
- **degraded 落盘**：annotation_to_engine_dict 透传 → `_generate_auto_case` frontmatter（`degraded: true` + reason）→ `_parse_case_frontmatter` 读取 → tab4 案例列表「⚠️ [降级标注]」
- **持久化**：`engine/model_degradation.py`（按组件 analyst/curator/daily_report，进入 2 失败/解除 2 成功对称，config/model_degradation.json gitignored）
- 测试：`tests/test_model_degradation.py`（5）+ `tests/test_llm_fallback.py`（7）

### 测试基线（更新）
`python -m pytest tests/ -q` → **441 passed, 约 11 skipped（未逐一核实精确数字）, 0 failed**（collect-only 452 例；skip = 小红书/抖音/XHS 联网 live 反爬 + TikTok/XHS-Downloader 未装 + sentiment_ml 样本不足；原「384 passed, 4 skipped」已更新）。

### ⚠️ 当前未完成待办（下次会话优先）
1. **`ui/tab4_disposition.py` 公众号链接弱化**：diff 已贴、无回归，**待用户确认后提交**（message: `fix: 案例处置页弱化公众号临时链接展示`）。改动：platform=="微信公众号" 时不再展示完整 url，改 `st.caption("🔗 微信临时链接（会话外不可打开，原文需 Monitor 会话内抓取）")`。
2. ~~**`AGENTS.md`**~~ ✅ 已提交（`be282a0`）。
3. **wiki 数据文件**：`wiki/embeddings/case_embeddings.json`、`wiki/index.md`、`wiki/taxonomy/candidate_tags.json` 有未提交改动（历史遗留数据变化），待确认处理。
4. ~~**`monitor_keywords.json` 反复被清空**~~ ✅ 已澄清：当前未提交 diff 是**关键词重配**（`字节避雷`→`豆包`，仅 wechat→4 平台，5→15 条，default→date），**非清空**。防误清空保护（3b1982a）仍保留，但本次非清空触发。
5. **Sentinel 兜底分支不可达**：`engine/annotate.py::annotate_with_fallback` 的「全部 LLM 失败→Sentinel 规则预标注」分支（line 554-556）实际不可达——orchestrator 在 `fast_track` 时走 `annotate(use_llm=False)`（line 310-311，在 analyst 内早退，不进 fallback）；非 fast_track 时 `annotate()` 不传 `sentinel_result`（orchestrator line 313），故 fallback 内 `sentinel_result is None` 恒真，永远落到 `return {"error": True, ...}`（line 557）。需决定：在 line 313 补传 sentinel_result 让兜底生效，或删死分支。
6. **scraper 平台映射表漂移**：三张独立映射表覆盖不一致——`engine/scraper.py::_detect_platform`（URL→中文，11 标签，含 X/Reddit/Instagram/TikTok/通用网页）、`agents/scraper.py::_PLATFORM_LABEL_TO_KEY`（中文→短键，12 项）、`engine/ingestor.py::PLATFORM_SUBDIR`（中文/短键→子目录，仅 6 平台）。`PLATFORM_SUBDIR` 缺 X/Reddit/Instagram/TikTok → 这些平台落扁平目录（`_get_case_dir` 返回 CASES_DIR），未来接入后可能重蹈 case_id 撞号。另 `_detect_platform` 的 instagram/tiktok 分支重复（line 135-138 vs 147-150，后者死代码）。
7. **联网测试污染真实 wiki/cases/**：`test_orchestrator.py` 的 `run_active_monitor` 在全量 pytest 时会真实写入生产 `wiki/cases/` 目录，且 curator 兜底路径的 `get_next_case_id` 会复用低编号导致撞号覆盖真实 case。本次（2026-08-23）已发生一次真实数据覆盖事故（5 个真实 case 被覆盖），已用备份 `temp/cases_backup_20260823/` 完整恢复。**根因未修**：这些联网测试应该像 `test_case_id.py`/`test_core.py` 一样 monkeypatch 隔离 `CASES_DIR` 等路径，而不是直接操作真实目录。**优先级：高**（已有真实事故记录，不是理论风险）。
8. **待验证：非微信平台（抖音/小红书等）搜索结果 URL 是否也存在轮换 token（同类稳定性风险）**：本次修复只验证并修复了微信平台（搜狗跳转链接 token 轮换导致去重失效），其余平台假设 URL 稳定，未做同等抽样验证。验证方法可复用本次的抽样脚本思路：同一 keyword_id 跨天归档，按 URL 分组 vs 按 title+author 分组对比，看是否有「URL 分组数明显多于 title+author 分组数」的失效迹象。

### 新注意事项（追加到上文旧注意事项）
- **微信公众号链接 = 搜狗临时跳转凭据**：会话外/过期后不可打开（sn 签名不暴露，缺 sn 即「参数错误」）。存库的公众号 url 无法作为长期可访问入口——展示层需弱化（tab4 已做，见待办 1），不要试图「修复」链接本身（微信反爬硬约束，见旧注意事项 10）。
- **monitor_keywords.json 易被误清空**：反复出现 keywords=[]；勿在测试/脚本中写它；改它前先确认是真实配置变更。
- **LLM 降级链现状**：Analyst/Curator/DailyReport 失败均有降级兜底 + degraded 标记 + config/model_degradation.json 持久化（gitignored，pytest 会产生该文件，跑完可删）。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

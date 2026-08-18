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
- ~24,000 行 Python，10 agent 模块 + 25 engine 模块 + 22 测试文件（318 测试）
- 110 个 Wiki 案例（P0×1, P1×16, P2×2, P3×91）+ 72 作者页 + 词表/向量/日报月报
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
| `tests/` | 22 文件 | 318 测试（1 预存失败 test_sentiment_ml） |

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

1. **测试先跑**：`python -m pytest tests/ -x -q`，318 测试（1 预存失败 `test_sentiment_ml.py::TestModelTraining`，与业务无关）。
2. **ingestor 脆弱**：`_split_table_cells()` 和 `_upsert_dimension_row()` 维护 Markdown 表格。修改时务必测 split→modify→rebuild 全周期。
3. **Streamlit 共享函数必须 key_prefix**：多 Tab 调用同一函数时所有 stateful 组件需要前缀。
4. **linker 阈值**：SIMILARITY_THRESHOLD=0.25, MIN_BIGRAM_OVERLAP=3。只比较原文内容（排除模板）。
5. **知识库密码**：三级源 `st.secrets → env → config.json`，无密码时向后兼容。
6. **案例数量**：110 个。新增后检查 index.md 三维索引完整性。
7. **st.rerun() 反模式**：绝对不要在 button handler 内调用 `st.rerun()`。使用 deferred pattern：按钮只做清空+设 flag+rerun，实际工作在下次运行的 tab 块内完成。最终 rerun 用脚本末 `_needs_rerun` gate。
8. **yt-dlp 评论上限**：`max_comments=["50"]` 已配置在 scraper.py 中，不要删除此限制。
9. **系统 prompt 按需构建**：已移除 `cached_system_prompt`。每次标注调用 `build_system_prompt(content)[0]`，按内容相关性选 top-5 案例。
10. **微信公众号会话内抓取**：永久链接 `sn` 签名拿不到，只能 monitor 搜狗→微信跳转会话内即时抓正文并缓存（`_ARTICLE_CACHE`），下游 `_scrape_wechat` 优先读缓存。不要回退为「拼 __biz 永久链接」。
11. **飞书「立即处理」双路径**：A 场景在 `ingestor`（新 URL 入库），B 场景在 `correction_handler`（纠偏改立即处理）。两条独立，改一条别假设另一条跟随。
12. **日报飞书推送单一来源**：只在 `orchestrator._push_daily_report_feishu`，scheduler 不得再推（会双推）；内容用当日 `ReportData`，别用裸 `query_stats()`。
13. **sentiment 字段**：新 case 由 ingestor 写 frontmatter `sentiment:`；存量 case 由 curator `_parse_case_frontmatter` 从正文 JSON 兜底；`query_stats` 的 `sentiment_dist` 须含「混合」键。

## 项目当前状态

6-Agent 舆情指挥系统完整可用。当前 110 案例、318 测试、6 搜索平台 + 10 抓取平台。最近一轮工作（2026-08）：
- 微信公众号「参数错误」根因修复（会话内抓取）
- 飞书「立即处置」A/B 场景告警
- 日报飞书推送（手动/定时/CLI 全覆盖 + 当日口径 + 情感字段修复）
- 死代码清理（fetch_wechat_article）

下一步候选（见 DESIGN.md 路线图）：微博/微信/新闻站点平台扩展、向量检索（案例 >200）、小红书 OCR/ASR。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

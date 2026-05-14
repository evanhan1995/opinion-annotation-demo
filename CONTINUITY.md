# 项目持续性 Prompt

> 在新对话中粘贴此 Prompt，让 Claude Code 快速理解项目全貌并继续开发。

---

## 唤醒 Prompt（复制到新对话）

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态（v0.5.1）和路线图，然后阅读 CONTINUITY.md
了解项目架构。确认你理解后，告诉我：
1) 项目目前做到了什么地步
2) 下一个 Phase 是什么，你准备从哪里开始
3) 上次会话遗留的任何注意事项
```

---

## 项目是什么

一个基于 LLM + Wiki 知识库的舆情智能标注系统。用户输入舆情链接（小红书/YouTube/Reddit/X），系统自动抓取内容 + 评论区 → AI 标注（严重度 P0-P3、分流建议、情感分析、风险标签、评论区红绿灯） → 自动存入知识库 → 知识库驱动 AI 标注越来越准。

**最终用户**：HR（Demo 展示用）+ Evan 自己（实际舆情工作用）。

**Web Demo**：https://opinion-annotation.streamlit.app（Streamlit Cloud）

**GitHub**：https://github.com/evanhan1995/opinion-annotation-demo

---

## 当前版本

**v1.0.0** — Phase 11a-d 全部交付。中期里程碑完成。
- ~4,200 行 Python，10 个源文件 + 382 行测试（21 个全通过）
- 13 个 Wiki 案例（P0×1, P1×2, P2×6, P3×4），全严重度覆盖
- 流式标注 + 侧边栏 Dashboard + 扫地僧引用可点击 + Demo 引导
- 知识库密码保护（`st.secrets.KB_PASSWORD` → `KB_PASSWORD` env → `config.json` kb_password）
- 跨条目关联检测（linker.py：bigram 加权评分，自动 synthesis 生成）
- 反馈回路闭合（新案例 → PROMPT_LAYERS → 下次标注可用）
- yt-dlp 评论限制 50 条（7,626 评论视频 171s → 3s）
- Deferred annotation 模式（新 URL 提交立即清空旧结果）
- 系统 prompt 缓存 + wait_for_selector 替代固定等待

---

## 一句话架构

```
URL → scraper(4平台) → raw/cases/ → annotate(LLM+动态案例回灌+流式) → outputs/
                                            ↘ ingestor(→index_mgr) → wiki/cases/ (+ index, log, archive)
                                            ↘ linker -> syntheses/ (跨平台关联)
                                            ↘ agent (扫地僧问答, 含syntheses检索)
                                            ↘ correction_handler(→index_mgr) (人工纠偏)
```

---

## 文件地图

| 文件 | 行数 | 一句话 |
|------|------|--------|
| `app.py` | ~1000 | Streamlit 4 Tab UI。Deferred annotation 模式：按钮清空→委托下次运行→`_needs_rerun` gate |
| `engine/annotate.py` | 657 | LLM 标注引擎。动态 PROMPT_LAYERS + `annotate_one_stream()` 流式生成器 |
| `engine/xhs_fetcher.py` | 471 | 小红书 API。Cookie 管理（缓存→弹窗→手动按钮三级兜底） |
| `engine/scraper.py` | ~415 | 抓取调度。yt-dlp max_comments=50 + wait_for_selector 替代固定等待 |
| `engine/ingestor.py` | 326 | 自动 Ingest。URL 去重（只扫 frontmatter url: 字段）→ 案例生成 → index_mgr 更新 → linker 关联 |
| `engine/agent.py` | 282 | 扫地僧。中文 bigram 搜索 wiki（含 syntheses/）→ LLM 综合 → 带引用回答 |
| `engine/correction_handler.py` | 283 | 纠偏处理。index 更新委托 index_mgr；url: 已写入 frontmatter |
| `engine/linker.py` | 236 | 跨条目关联。bigram Jaccard 加权评分，正文 60% + 标题 40% + 标签加成 |
| `engine/index_mgr.py` | 136 | 共享 index 更新。`_split_table_cells()` + `_upsert_dimension_row()` + `update_case_index()` |
| `tests/test_core.py` | 382 | 21 个核心测试（index×8, dedup×4, correction×4, split×5） |

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

1. **测试先跑**：`python -m pytest tests/test_core.py -v`，21 个应全通过。
2. **ingestor 脆弱**：`_split_table_cells()` 和 `_upsert_dimension_row()` 维护 Markdown 表格。修改时务必测 split→modify→rebuild 全周期。
3. **Streamlit 共享函数必须 key_prefix**：多 Tab 调用同一函数时所有 stateful 组件需要前缀。
4. **linker 阈值**：SIMILARITY_THRESHOLD=0.25, MIN_BIGRAM_OVERLAP=3。只比较原文内容（排除模板）。
5. **知识库密码**：三级源 `st.secrets → env → config.json`，无密码时向后兼容。
6. **案例数量**：13 个。新增后检查 index.md 三维索引完整性。
7. **st.rerun() 反模式**：绝对不要在 button handler 内调用 `st.rerun()`。使用 deferred pattern：按钮只做清空+设 flag+rerun，实际工作在下次运行的 tab 块内完成。最终 rerun 用脚本末 `_needs_rerun` gate。
8. **yt-dlp 评论上限**：`max_comments=["50"]` 已配置在 scraper.py 中，不要删除此限制。
9. **系统 prompt 缓存**：`st.session_state.cached_system_prompt` 在侧边栏加载时写入，button handler 用 `.get()` 带 fallback。

## 项目当前状态 (v1.0.0)

中期里程碑 Phase 11a-d 全部完成：
- **11a**: 批量导入 (checkbox + text_area + 进度条)
- **11b**: 标注历史回溯 (find_annotation_history + diff + timeline)
- **11c**: 巡检监控 (monitored_urls.json + 侧边栏按钮)
- **11d**: P0/P1 醒目告警 (error/warning 横幅)

远期路线（1-3月）：向量检索、L4多人协作(飞书)、多语言+A/B对比。

详见 `DESIGN.md` 第 2 节路线图。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

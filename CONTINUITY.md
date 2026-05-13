# 项目持续性 Prompt

> 在新对话中粘贴此 Prompt，让 Claude Code 快速理解项目全貌并继续开发。

---

## 唤醒 Prompt（复制到新对话）

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态（v0.5）和路线图，然后阅读 CONTINUITY.md
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

**v0.5** — Phase 10a 已交付。
- 4,147 行 Python，10 个源文件 + 382 行测试（21 个全通过）
- 13 个 Wiki 案例（P0×1, P1×2, P2×6, P3×4），全严重度覆盖
- 流式标注 + 侧边栏 Dashboard + 扫地僧引用可点击 + Demo 引导
- 知识库密码保护（`st.secrets.KB_PASSWORD` → `KB_PASSWORD` env → `config.json` kb_password）
- 跨条目关联检测（linker.py：bigram 加权评分，自动 synthesis 生成）
- 反馈回路闭合（新案例 → PROMPT_LAYERS → 下次标注可用）

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
| `app.py` | 962 | Streamlit 4 Tab UI。`_render_annotation_result(key_prefix)` 只渲染在 Tab1/Tab2；Tab3 密码保护 |
| `engine/annotate.py` | 657 | LLM 标注引擎。动态 PROMPT_LAYERS + `annotate_one_stream()` 流式生成器 |
| `engine/xhs_fetcher.py` | 471 | 小红书 API。Cookie 管理（缓存→弹窗→手动按钮三级兜底） |
| `engine/scraper.py` | 412 | 抓取调度。`scrape(url)` 自动检测平台→抓取→写 raw/cases/ JSON |
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
  → scraper.scrape(url)           # 抓取 + 写 raw/cases/
  → annotate.format_user_message() # 格式化
  → annotate.annotate_one_stream() # 流式 LLM 调用
  → app._save_annotation_output()  # 写 outputs/
  → app._do_ingest()               # → ingestor.ingest()
      → _find_existing_case_by_url()  # 去重（只扫 frontmatter url: 字段）
      → _generate_auto_case()          # 写 wiki/cases/case-XXX.md（含 url: frontmatter）
      → index_mgr.update_case_index()  # 更新 index.md（三维索引 + overview）
      → _update_global_index()         # 更新 wiki/index.md
      → _append_ingest_log()           # 写 wiki/log.md
      → _archive_raw_file()            # 移动 raw/cases/ → raw/archive/
      → linker.auto_link()             # 跨平台关联检测 → synthesis + related_cases
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

1. **GitHub push**：最后一次 push 到 `e4ea725`。如有新 commit 未 push，运行 `git push`。
2. **测试先跑**：`python -m pytest tests/test_core.py -v`，21 个应全通过。如有失败，优先修测试再继续。
3. **ingestor 脆弱**：`_split_table_cells()` 和 `_upsert_dimension_row()` 维护 Markdown 表格。修改时务必测 split→modify→rebuild 全周期（`feedback_modify_rebuild_test_cycle.md`）。
4. **Streamlit 共享函数**：如果在多个 Tab 调用同一函数，所有 stateful 组件需要 `key_prefix`（`feedback_streamlit_tab_duplicate_keys.md`）。
5. **linker 阈值**：当前 SIMILARITY_THRESHOLD=0.25，MIN_BIGRAM_OVERLAP=3。只比较原文内容（排除模板）。修改阈值后跑 `find_related()` 验证。
6. **知识库密码**：`st.secrets.KB_PASSWORD` → `os.getenv("KB_PASSWORD")` → `config.json.kb_password`。无密码配置时行为不变（向后兼容）。
7. **案例数量**：13 个。如有新增案例，检查 index.md 三维索引是否完整更新。

---

## 本地运行

```bash
cd "D:\Claude code\舆情标注Wiki"
streamlit run app.py --server.port 8501 --server.headless true
# 或双击 start.bat
```

## 下一 Phase (10b: 扫地僧关联查询)

Linker 已就绪，syntheses/ 条目已被 agent 搜索覆盖。10b 主要是：
1. 在 agent 的 AGENT_SYSTEM_PROMPT 中添加关联查询引导
2. 当搜索结果命中 synthesis 条目时，展开关联案例列表
3. 测试查询："DJI Neo 2 电池问题在哪些平台有讨论？"

详见 `DESIGN.md` 第 2 节路线图。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

# 项目持续性 Prompt

> 在新对话中粘贴此 Prompt，让 Claude Code 快速理解项目全貌并继续开发。

---

## 唤醒 Prompt（复制到新对话）

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态（v1.3.0）和路线图，再读 WAKEUP.md 了解架构规则和陷阱。
确认理解后告诉我：
1) 项目目前做到什么地步
2) 下一步是什么
3) 上次会话遗留的注意事项
```

---

## 项目是什么

一个基于 LLM + Wiki 知识库的舆情智能标注系统。用户输入舆情链接（小红书/YouTube/Reddit/X），系统自动抓取内容 + 评论区 → AI 标注（严重度 P0-P3、分流建议、情感分析、风险标签、评论区红绿灯） → 自动存入知识库 → 知识库驱动 AI 标注越来越准。

**最终用户**：HR（Demo 展示用）+ Evan 自己（实际舆情工作用）。

**Web Demo**：https://opinion-annotation.streamlit.app（Streamlit Cloud）

**GitHub**：https://github.com/evanhan1995/opinion-annotation-demo

---

## 当前版本

**v1.3.0** — 所有短期 Phase 交付，项目完整可用。
- 5,283 行 Python，11 源文件 + 21/21 测试全通过
- 27 个 Wiki 案例 + 5 作者页 + 5 概念页 + 1 规范 + 16 outputs
- YouTube: 标题+描述(2000字)+时长+评论+社媒数据+按需字幕+AI深度分析
- 小红书: xhshow API + Cookie三级兜底(缓存→弹窗→按钮) + 播放量估算
- 舆情分类(6类多选) + 近似舆情匹配(top 3 tag命中)
- 批量导入 + 标注历史 diff + 巡检监控 + P0/P1告警 + URL校验
- 知识库密码三级保护 + Deferred annotation + 相关性案例筛选(42K→10K tokens)

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
9. **系统 prompt 按需构建**：已移除 `cached_system_prompt`。每次标注调用 `build_system_prompt(content)[0]`，按内容相关性选 top-5 案例（10ms 构建，9.8K tokens）。

## 项目当前状态 (v1.3.0)

所有短期 Phase 完成，项目完整可用。下一阶段：
- **17a**: app.py 拆分 (半天)
- **17b**: 测试补盲 (半天)
- **17c**: XHS Cookie 攻坚 (一天)

详见 `DESIGN.md` 第 2 节路线图和 `WAKEUP.md`。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

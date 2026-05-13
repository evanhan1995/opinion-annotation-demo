# 项目持续性 Prompt

> 在新对话中粘贴此 Prompt，让 Claude Code 快速理解项目全貌并继续开发。

---

## 使用方式

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。
请先阅读 DESIGN.md 了解当前状态和路线图，然后阅读 CONTINUITY.md 了解项目架构。
确认你理解后，告诉我：1) 项目目前做到了什么地步 2) 下一个 Phase 是什么 3) 你准备从哪里开始。
```

---

## 项目是什么

一个基于 LLM + Wiki 知识库的舆情智能标注系统。用户输入舆情链接（小红书/YouTube/Reddit/X），系统自动抓取内容 + 评论区 → AI 标注（严重度 P0-P3、分流建议、情感分析、风险标签、评论区红绿灯） → 自动存入知识库 → 知识库驱动 AI 标注越来越准。

**最终用户**：HR（Demo 展示用）+ Evan 自己（实际舆情工作用）。

**Web Demo**：https://opinion-annotation.streamlit.app（Streamlit Cloud 部署）

**GitHub**：https://github.com/evanhan1995/opinion-annotation-demo

---

## 当前版本

**v0.3-pre** — Phase 6 已完成，进入 Phase 7 架构清理阶段。
- 3,233 行 Python，7 个文件，4 个 Streamlit Tab
- 13 个 Wiki 案例（P0×1, P1×2, P2×6, P3×4），全严重度覆盖
- 反馈回路已闭合（新案例 → PROMPT_LAYERS → 下次标注可用）
- 去重升级完成（URL → frontmatter，只扫 YAML）
- UI 状态泄漏和 widget key 冲突已修复

---

## 一句话架构

```
URL → scraper(4平台) → raw/cases/ → annotate(LLM+动态案例回灌) → outputs/
                                            ↘ ingestor → wiki/cases/ (+ index, log, archive)
                                            ↘ agent (扫地僧问答)
                                            ↘ correction_handler (人工纠偏)
```

---

## 文件地图

| 文件 | 行数 | 一句话 |
|------|------|--------|
| `app.py` | 783 | Streamlit 4 Tab UI。`_render_annotation_result(key_prefix)` 只渲染在 Tab1/Tab2 |
| `engine/annotate.py` | 584 | LLM 标注引擎。动态 PROMPT_LAYERS（`_get_case_layers()` 扫描最新 15 个案例） |
| `engine/xhs_fetcher.py` | 471 | 小红书 API。Cookie 管理（缓存→弹窗→手动按钮三级兜底） |
| `engine/ingestor.py` | 428 | 自动 Ingest。`_split_table_cells()` 保护 `[[...]]` 边界，三维索引更新 |
| `engine/scraper.py` | 412 | 抓取调度。`scrape(url)` 自动检测平台→抓取→写 raw/cases/ JSON |
| `engine/agent.py` | 282 | 扫地僧。中文 bigram 搜索 wiki→LLM 综合→带引用回答 |
| `engine/correction_handler.py` | 273 | 纠偏差异处理。⚠️ 有自己独立的 index 更新逻辑（Phase 7 将统一） |

---

## 关键路径（模块间怎么连的）

```
app.py 标注按钮点击
  → scraper.scrape(url)           # 抓取 + 写 raw/cases/
  → annotate.format_user_message() # 格式化
  → annotate.annotate_one()        # LLM 调用（prompt 从 build_system_prompt() 组装）
  → app._save_annotation_output()  # 写 outputs/
  → app._do_ingest()               # → ingestor.ingest()
      → _find_existing_case_by_url()  # 去重（只扫 frontmatter url: 字段）
      → _generate_auto_case()          # 写 wiki/cases/case-XXX.md
      → _update_case_index()           # 更新 wiki/cases/index.md（三维索引）
      → _update_global_index()         # 更新 wiki/index.md
      → _append_ingest_log()           # 写 wiki/log.md
      → _archive_raw_file()            # 移动 raw/cases/ → raw/archive/
```

---

## 配置和密钥

- `engine/config.json` — API Key（DeepSeek，`.gitignore` 已排除）
- `engine/config.example.json` — 模板文件
- `engine/.xhs_cookies.json` — 小红书 Cookie 缓存（7天有效，`.gitignore` 已排除）
- 环境变量支持：`DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`
- Streamlit Cloud Secrets：需手动配置 `DEEPSEEK_API_KEY`

---

## 架构债务（新对话启动时优先检查）

1. **correction_handler 有自己独立的 index 更新逻辑**（`correction_handler.update_case_index()` vs `ingestor._update_case_index()`）——两套实现，纠偏案例硬编码插入位置 case-006，不更新维度索引。Phase 7 第一优先级统一。
2. **ingestor 用字符串拼接维护 Markdown 表格**——改用数据结构（parse→modify→serialize）更安全。
3. **0 个自动化测试**——如已写测试，先跑 `python -m pytest tests/`。
4. **app.py 783 行**——新增 UI 功能时优先拆到独立模块。

---

## 技术栈和约定

- Python 3.x，Streamlit 1.57+
- 路径模式：`Path(__file__).resolve().parent` 每个模块自行推导
- 错误处理：返回 dict(error=True, message=...)，不抛异常
- 文件 I/O：`open(path, "w", encoding="utf-8")`，JSON 用 `ensure_ascii=False`
- 前端：Streamlit session_state 管理状态，**共享函数用 key_prefix 区分 Tab**
- 中文：所有用户界面和错误消息用中文，代码注释用中文
- 禁用 emoji（Windows 兼容）
- **共享逻辑不复写**：同一函数出现两次立即提取到共享模块

---

## 本地运行

```bash
cd "D:\Claude code\舆情标注Wiki"
streamlit run app.py --server.port 8501 --server.headless true
# 或双击 start.bat
```

---

## 下一 Phase (Phase 7: 架构清理)

按优先级：
1. 统一 index 更新逻辑 → `engine/index_mgr.py`（ingestor + correction_handler 共用）
2. 写 3 个核心测试（index_update / dedup / correction_diff）
3. 修复 correction_handler 硬编码日期和插入位置

详见 `DESIGN.md` 第 2 节路线图。

---

*本文件是项目"记忆外骨骼"——让未来的 Claude Code 新对话能在 2 分钟内理解项目全貌。随项目推进同步更新。*

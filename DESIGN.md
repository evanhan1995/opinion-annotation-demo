# 舆情标注系统 —— 深化设计方案

> 版本: v0.4 | 日期: 2026-05-13 | 状态: Phase 8 已交付，进入 Phase 9 可观测性+部署阶段

---

## 1. 当前状态 (v0.3-pre)

### 1.1 已完成

```
用户输入 URL 或手动粘贴
  → scraper.py（4平台 + 通用回退）✅
  → raw/cases/ 落盘 ✅
  → annotate.py（LLM 标注，动态案例回灌）✅
  → outputs/ 落盘 ✅
  → ingestor.py（自动 Wiki 案例生成 + 三维索引 + 归档）✅
  → raw/archive/ 归档 ✅
  → correction_handler.py（人工纠偏 → 校准案例）✅
  → agent.py（扫地僧：自然语言问答知识库）✅
  → Web UI（4 Tab：手动输入 / URL抓取 / 知识库 / 扫地僧）✅
```

### 1.2 代码规模

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 874 | Streamlit Web 界面（Dashboard + 流式标注 + 引用可点击） |
| `engine/annotate.py` | 657 | LLM 标注引擎（含流式 `annotate_one_stream`） |
| `engine/xhs_fetcher.py` | 471 | 小红书 API 客户端 |
| `engine/ingestor.py` | 319 | 自动 Ingest 管线（index 更新委托 index_mgr） |
| `engine/scraper.py` | 412 | 多平台抓取调度 |
| `engine/agent.py` | 282 | 扫地僧问答引擎 |
| `engine/correction_handler.py` | 281 | 纠偏差异处理（index 更新委托 index_mgr） |
| `engine/index_mgr.py` | 136 | 共享 index 更新逻辑 |
| `tests/test_core.py` | 382 | 21 个核心测试 |
| **总计** | **3,650** | |

### 1.3 知识库资产

| 目录 | 数量 | 说明 |
|------|------|------|
| `wiki/cases/` | 13 个案例 | P0×1, P1×2, P2×6, P3×4 — 全严重度覆盖 |
| `wiki/concepts/` | 5 篇 | 严重度/情感/分流/真实性/平台 |
| `wiki/entities/` | 2 篇 | Meltwater / 新浪舆情通 |
| `wiki/sources/` | 2 篇 | Evan 的 TEMU + DJI 复盘 |
| `wiki/syntheses/` | 1 篇 | 标注规范活文档 |
| `raw/cases/` | 4 个文件 | 待处理原始抓取 |
| `raw/archive/` | 4 个文件 | 已处理归档 |
| `outputs/` | 4 个文件 | 标注结果存档 |

### 1.4 已修复问题（本次会话）

| # | 问题 | 修复 |
|---|------|------|
| 1 | `wiki/cases/index.md` P2 维度 Wiki 链接格式损坏 | `_split_table_cells()` protect-split-restore + 空格保留 |
| 2 | P1 严重度盲区（9个案例中0个P1） | case-010（数据隐私合规）+ 用户自建 case-012 |
| 3 | 案例去重全文件扫 URL 字符串 | 改为 frontmatter `url:` 字段匹配，存量回填 |
| 4 | 标注结果残留在扫地僧 Tab | `_render_annotation_result()` 移入 Tab1/Tab2 内部 |
| 5 | Tab1/Tab2 widget key 重复 | 13 个交互组件加 `key_prefix` 前缀 |
| 6 | Ingestor 分流建议维度从不更新 | `_update_case_index()` 新增 action 维度逻辑 |
| 7 | 平台字段从 annotation_result 取（总是 `?`） | 改为从 scraped_data 取 |
| 8 | 端到端真数据测试缺失 | 小红书 → 标注 → Ingest → 扫地僧检索全链路通过 |

### 1.5 架构债务（本次会话发现）

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | ~~**correction_handler 有自己独立的 index 更新逻辑**~~ | ✅ 已修复 | Phase 7：统一到 `engine/index_mgr.py`，两者共用。硬编码 case-006 已消除 |
| 2 | **ingestor 用字符串操作维护 Markdown 表格** | 中 | `_update_case_index()` 靠 regex + split + string concat 维护表格。case 超过 50 时维护成本非线性增长。Phase 10d 计划结构化 |
| 3 | ~~**无自动化测试**~~ | ✅ 已修复 | Phase 7b：21 个测试覆盖 index 更新/去重/纠偏差异/表格 split |
| 4 | **app.py 783 行单文件** | 低 | 混入 Wiki 浏览器、标注展示、纠偏表单、抓取逻辑。后续功能叠加会加速熵增 |

---

## 2. 路线图（重新规划）

### 🔴 Phase 7: 架构清理 (5/14 上午)

> **为什么这是最高优先级**：correction_handler 的独立 index 更新逻辑每次纠偏都可能损坏 index.md。不修这个，后续所有 Phase 都建立在脆弱地基上。

| # | 任务 | 验证标准 | 预估 |
|---|------|---------|------|
| 7a | **统一 index 更新逻辑** | 提取 `_update_case_index()` 到共享模块（如 `engine/index_mgr.py`），ingestor 和 correction_handler 都调用同一函数。correction_handler 不再硬编码插入位置 | 1h |
| 7b | **写 3 个核心测试** | `test_index_update`（三维度 + 空格保留）、`test_dedup`（frontmatter URL 匹配/不匹配）、`test_correction_diff`（差异等级判定） | 45min |
| 7c | **correction_handler 其他修复** | 纠偏案例生成时写入 `url:` frontmatter；更新日期不再硬编码 `2026-05-11` | 15min |

### 🟡 Phase 8: 体验优化 (5/14 下午 - 5/15)

| # | 任务 | 验证标准 |
|---|------|---------|
| 8a | **流式标注输出** | 标注结果逐字出现，用户不用等 3-5 秒空白。DeepSeek API 支持 `stream=True` |
| 8b | **知识库 Dashboard** | 侧边栏或新 Tab：案例总数、严重度分布柱状图、平台分布饼图、最近 5 次操作 |
| 8c | **扫地僧引用可点击** | 回答中的 `[[cases/case-XXX]]` 渲染为可点击链接，跳转到知识库对应页面 |
| 8d | **Demo 引导优化** | 首次打开页面自动弹出引导提示（st.toast 或 info box）：「点击加载 Demo → 点标注 → 切到知识库查看」 |

### 🟢 Phase 9: 可观测性 + 部署 (5/16)

| # | 任务 | 验证标准 |
|---|------|---------|
| 9a | **自动纠偏率监控** | 侧边栏展示「AI 标注准确率」（纠偏次数/总标注次数），基于 log.md 自动计算 |
| 9b | **XHS Cookie 过期告警** | 侧边栏显示 Cookie 剩余有效天数，<1 天标红警告 |
| 9c | **Push 到 GitHub** | `git push`，确认 Streamlit Cloud 上的 Demo 可访问且 API Key 配置正确 |

### 🔵 Phase 10: 智能升级 (5/17-20)

| # | 任务 | 说明 |
|---|------|------|
| 10a | **跨条目关联检测** | 新增 `engine/linker.py`：标题/正文 bigram 相似度 → 同一事件不同平台碎片自动聚合并生成 `syntheses/` 条目 |
| 10b | **扫地僧支持关联查询** | "这个事件在哪些平台上有讨论？" → 自动检索关联 case |
| 10c | **边界检查 → 自动更新 concepts** | `_check_boundaries()` 发现 P1 盲区时，自动建议更新 `severity-rating-matrix.md` |
| 10d | **ingestor Markdown 表格结构化** | 把 index.md 表格解析为 dict → 修改 → 序列化，替代当前的字符串拼接 |

### 🟣 Phase 11: 批量 + 自动化 (2-4 周)

| # | 任务 | 说明 |
|---|------|------|
| 11a | **批量导入** | 支持粘贴多个 URL（每行一个），批量抓取+标注 |
| 11b | **标注历史回溯** | 同一 URL 多次标注的差异对比 |
| 11c | **定时自动巡检** | 接入 RSS/API，定时抓取+标注+异常告警 |
| 11d | **飞书/钉钉通知** | P0/P1 案例自动推送 |
| 11e | **向量检索** | 案例 >500 时引入 embedding + vector search（当前 13 个案例无需） |

### ⬜ Phase 12: 远期 (1-3 个月)

| # | 任务 | 说明 |
|---|------|------|
| 12a | **L4 多人协作** | 飞书文档/多维表格替代本地 Markdown |
| 12b | **多语言支持** | 非中文舆情的自动翻译+标注 |
| 12c | **标注质量 A/B 测试** | 对比不同 prompt 版本的标注准确率 |

---

## 3. 架构原则（不变）

1. **raw/ 永不修改** —— 原始数据只追加，不覆盖
2. **wiki/ 由 AI 全权维护** —— 人类通过投放案例和纠偏间接影响
3. **每次操作有日志** —— wiki/log.md append-only
4. **规则来自案例** —— 不凭空调整标注规范
5. **Demo 优先** —— 改动不能破坏 Web UI 基本可用性
6. **信息闭环** —— 任何自动生成的信息必须能被未来的系统消费
7. **共享逻辑不复写** —— 同一函数出现两次立即提取到共享模块

---

## 4. 关键设计决策记录

| 决策 | 原因 | 日期 |
|------|------|------|
| 不引入向量数据库 | wiki < 50 页，关键词+frontmatter 搜索足够 | 2026-05-12 |
| PROMPT_LAYERS 动态化而非静态列表 | 新案例不回灌=反馈回路断裂 | 2026-05-12 |
| 扫地僧用关键词搜索而非 embedding | 中文 bigram 分词已覆盖查询需求 | 2026-05-12 |
| Ingest 自动触发而非手动按钮 | Demo 需要"系统感" | 2026-05-12 |
| 纠偏与自动Ingest并存 | 两种案例模板不同（source: auto_ingest vs human_correction） | 2026-05-12 |
| Phase 7 架构清理先于功能开发 | correction_handler 独立 index 逻辑 = 定时炸弹，且共享模块原则要求不复写 | 2026-05-13 |

---

*本文件随项目推进持续更新。每次 Phase 完成后更新第 1 节和第 2 节。*

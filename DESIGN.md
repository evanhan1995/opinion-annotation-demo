# 舆情标注系统 —— 深化设计方案

> 版本: v0.5 | 日期: 2026-05-13 | 状态: Phase 10a 已交付，知识库密码保护已上线

---

## 1. 当前状态 (v0.5)

### 1.1 已完成

```
用户输入 URL 或手动粘贴
  → scraper.py（4平台 + 通用回退）✅
  → raw/cases/ 落盘 ✅
  → annotate.py（LLM 标注 + 流式输出 + 动态案例回灌）✅
  → outputs/ 落盘 ✅
  → ingestor.py（Wiki 案例生成 + 三维索引 + 归档 + 跨条目关联）✅
  → raw/archive/ 归档 ✅
  → correction_handler.py（人工纠偏 → 校准案例，index 委托 index_mgr）✅
  → agent.py（扫地僧：自然语言问答知识库）✅
  → linker.py（跨平台事件碎片自动聚合）✅
  → Web UI（4 Tab：手动输入 / URL抓取 / 知识库🔒 / 扫地僧）✅
  → 知识库密码保护（st.secrets → env → config.json 三级）✅
```

### 1.2 代码规模

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 962 | Streamlit Web UI（Dashboard + 流式标注 + 引用可点击 + 密码保护） |
| `engine/annotate.py` | 657 | LLM 标注引擎（含流式 `annotate_one_stream`） |
| `engine/xhs_fetcher.py` | 471 | 小红书 API 客户端 |
| `engine/scraper.py` | 412 | 多平台抓取调度 |
| `engine/ingestor.py` | 326 | 自动 Ingest 管线 + linker 挂钩 |
| `engine/agent.py` | 282 | 扫地僧问答引擎 |
| `engine/correction_handler.py` | 283 | 纠偏差异处理 |
| `engine/linker.py` | 236 | 跨条目关联检测（bigram 加权评分） |
| `engine/index_mgr.py` | 136 | 共享 index 更新逻辑 |
| `tests/test_core.py` | 382 | 21 个核心测试 |
| **总计** | **4,147** | |

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

### 1.4 本次会话修复

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

### 1.5 架构债务

| # | 问题 | 严重度 | 计划 |
|---|------|--------|------|
| 1 | ingestor 字符串拼接维护 Markdown 表格 | 中 | 案例 >50 时结构化（当前 13 无需） |
| 2 | app.py 近千行单文件 | 低 | 后续按模块拆分 |

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

### 🔵 下一步 (5/14 开始)

| # | 任务 | 说明 | 预估 |
|---|------|------|------|
| 10b | **扫地僧关联查询** | 优化 agent 查询模板，显式支持"这个事件在哪些平台有讨论？"跨平台查询。linker 的 synthesis 条目已自动纳入 agent 搜索范围，只需添加查询引导 | 30min |
| 10c | **边界检查 → 自动更新 concepts** | `_check_boundaries()` 发现盲区时自动建议更新 `severity-rating-matrix.md`。生成 draft PR 式的修改建议而非直接改写 | 1h |
| 10d | **ingestor 表格结构化** | index.md 表格 parse → dict → modify → serialize。必须在案例 >50 前完成，当前 13 案例可暂缓 | 1.5h |

### 🟣 中期 (2-4 周)

| # | 任务 | 说明 |
|---|------|------|
| 11a | **批量导入** | 粘贴多个 URL（每行一个），批量抓取+标注 |
| 11b | **标注历史回溯** | 同一 URL 多次标注的差异对比时间线 |
| 11c | **定时自动巡检** | 接入 RSS/API，定时抓取+标注+异常告警 |
| 11d | **飞书/钉钉通知** | P0/P1 案例自动推送 |

### ⬜ 远期 (1-3 月)

| # | 任务 | 说明 |
|---|------|------|
| 12a | 向量检索 | 案例 >500 时引入 embedding + vector search |
| 12b | L4 多人协作 | 飞书文档/多维表格替代本地 Markdown |
| 12c | 多语言 + A/B | 非中文舆情自动翻译；不同 prompt 版本准确率对比 |

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

---

*随项目推进持续更新。每次 Phase 完成后更新第 1 节和第 2 节。*

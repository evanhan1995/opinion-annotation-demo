# 舆情标注 Wiki — 操作手册

> 本文件是 AI Agent 的操作手册，基于 Andrej Karpathy 的 LLM Wiki 方法论。
> 知识库定位：舆情智能打标与分流判断。用案例驱动的迭代机制持续提升标注精度。

---

## 📌 知识库定位

基于 Evan 在 TEMU 舆情指挥部和 DJI 口碑系统的双重工作经验，构建一套**随案例增长的、AI 可执行的舆情标注操作规范**。

核心创新：**案例库是迭代引擎**——每新增一个标注案例，AI 自动检查标注规范的决策边界是否需要调整。

---

## 📂 目录结构

```
舆情标注Wiki/
│
├── agents/             6-Agent 舆情指挥系统 (PRD v1.2, 2026-05-23)
│   ├── orchestrator.py  编排器 — 唯一跨Agent调度者，4条流 + P0/P1熔断
│   ├── monitor.py       监测员 — 关键词搜索(YouTube/抖音/XHS) + Excel + SEO
│   ├── scraper.py       采集员 — 三平台抓取 + 人工喂料降级
│   ├── analyst.py       分析员 — DeepSeek标注 + 相关性判定
│   ├── handler.py       处置跟进 — 5状态机 + DeepSeek处置方案
│   ├── curator.py       保管员 — KB入库/索引/状态同步/问答
│   ├── daily_report.py  日报组 — LLM日报/月报 + MiniMax/DeepSeek
│   └── shared.py        共享 — 模型工厂 + dataclass + JSON工具
│
├── engine/             核心引擎实现层 (被 agents/ 包裹，保持向后兼容)
│   ├── annotate.py     LLM 标注引擎 (844行)
│   ├── scraper.py      多平台抓取调度 (505行)
│   ├── xhs_fetcher.py  小红书双通道 (590行)
│   ├── tt_fetcher.py   抖音抓取器 (313行)
│   ├── ingestor.py     自动 Ingest 管线 (520行)
│   ├── agent.py        扫地僧问答引擎 (331行)
│   ├── linker.py       跨平台关联检测 (312行)
│   ├── correction_handler.py  纠偏处理器 (266行)
│   └── index_mgr.py    索引管理器 (265行)
│
├── ui/                 Streamlit 前端 (8 Tab)
│   ├── tab1_manual.py   📝 手工录入
│   ├── tab2_url.py      🔗 URL 抓取 + 人工喂料
│   ├── tab3_monitor.py  📡 Monitor 仪表板 (NEW)
│   ├── tab4_disposition.py 📋 案例处置 (NEW)
│   ├── tab6_reports.py  📊 报告查看 (NEW)
│   ├── tab5_demo.py     🎬 操作演示
│   ├── shared.py        共享渲染函数
│   └── sidebar.py       侧边栏
│
├── prompts/            Agent System Prompt 独立存放
│   ├── analyst_system.txt
│   ├── handler_system.txt
│   ├── curator_system.txt
│   └── daily_report_system.txt
│
├── scheduler.py        定时调度器 (日报21:07/月报09:03/巡检每6h)
│
├── raw/                原始资料收件箱 —— 只读，永不修改
│   ├── cases/          待处理的舆情案例原文
│   ├── archive/        ingest 后的归档区
│   └── monitor/        监测结果存档
│
├── wiki/               知识编译输出层 —— AI 全权维护
│   ├── index.md        全局索引
│   ├── log.md          操作日志（append-only）
│   ├── concepts/       标注概念（5篇）
│   ├── entities/       实体（2篇）
│   ├── sources/        来源摘要（2篇）
│   ├── syntheses/      综合文档（4篇）
│   ├── cases/          标注案例库（34个，含 status 字段）
│   ├── authors/        作者库（12个）
│   └── reports/        日报/月报
│
├── outputs/            标注结果 + Monitor Excel + SEO 快照
│
└── tests/              8 测试文件，111 测试全通过
```

---

## 📝 Wiki 页面规范

### 1. YAML Frontmatter

```yaml
---
title: 页面标题
type: concept | entity | source | synthesis | case
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: high | medium | low
sources:
  - "[[sources/xxx]]"
related:
  - "[[concepts/xxx]]"
tags: [tag1, tag2]
---
```

### 2. 页面类型说明

| 类型 | 位置 | 内容 |
|------|------|------|
| `concept` | `wiki/concepts/` | 标注概念：严重度矩阵、情感维度、分流逻辑等 |
| `entity` | `wiki/entities/` | 工具/平台实体 |
| `source` | `wiki/sources/` | raw 文件的摘要提炼 |
| `synthesis` | `wiki/syntheses/` | 标注规范（活文档） |
| `case` | `wiki/cases/` | 标注案例，含判据链和边界讨论 |

### 3. 链接规范

- 内部引用使用 `[[wikilink]]` 格式
- 引用 wiki 内其他页面：`[[concepts/severity-rating-matrix]]`
- 外部链接使用标准 markdown：`[text](url)`

---

## 🔄 核心操作

### 📥 Ingest（案例摄入）

当 `raw/cases/` 中有新案例时执行：

1. 读取案例原始内容
2. 按当前 [[syntheses/opinion-annotation-spec|标注规范]] 对案例进行完整标注
3. 在 `wiki/cases/` 下创建 case 页面（含判据链+边界讨论）
4. **关键步骤**：判断该案例是否触及现有规则的模糊地带
   - 未覆盖的边界 → 更新对应 concept 页面 + 标注规范
   - 被现有规则正确覆盖 → 仅在 case 页面记录
5. 更新 `wiki/cases/index.md` 的案例总览、维度索引、覆盖度分析
6. 更新 `syntheses/opinion-annotation-spec.md` 的案例先例章节
7. 在 `wiki/log.md` 中记录本次操作
8. 将原始文件移入 `raw/archive/`

**触发指令**：`请 ingest raw/cases/ 中的新案例`

### ❓ Query（查询）

基于知识库回答标注相关问题。

**触发指令**：`请基于知识库对这个舆情内容做标注`

### 🧹 Lint（知识体检）

1. 检查案例覆盖度盲区（哪些严重度/平台/内容类型缺乏案例）
2. 检查断裂链接
3. 检查标注规范中的规则是否被后续案例挑战
4. 在 `wiki/log.md` 中记录

**触发指令**：`请做一次知识库 lint 检查`

---

## ⚠️ 重要规则

1. **永不修改 `raw/` 中的文件**（除非移入 archive）。
2. **wiki/ 由 AI 全权维护**，人类通过投放案例和 query 来间接影响。
3. **每次操作必须在 `wiki/log.md` 中记录**。
4. **规则来自案例，案例校准规则**——不凭空调整标注规范。
5. **置信度要诚实**——对不确定的内容标注 `confidence: low`。
6. **活文档原则**：每次修改标注规范必须注明触发案例。

---

## 🏷️ 标签体系

```
#yq                  # 舆情工作
#severity            # 严重度评级
#sentiment           # 情感分析
#triaging            # 分流决策
#authenticity        # 真实性评估
#platform            # 平台特性
#case                # 标注案例
#P0 #P1 #P2 #P3      # 严重度等级
```

---

## 📐 案例页面格式

```yaml
---
title: 案例XXX：一句话标题
type: case
created: YYYY-MM-DD
severity: P0 | P1 | P2 | P3
action: 立即处理 | 持续观察 | 可忽略 | 正面可利用
platform: YouTube | Instagram | TikTok | X | Reddit | 新闻媒体 | 论坛 | 其他
tags: [标签]
related_concepts:
  - "[[concepts/xxx]]"
related_cases:
  - "[[cases/case-xxx]]"
---

## 原始输入
（标准输入格式）

## 标注输出
（完整 JSON）

## 判据链
（逐步推理：为什么给这个评级/建议）

## 边界讨论
（这个案例靠近什么边界？有什么替代判断？）

## 对标注规范的影响
（新增此案例后，是否需要调整任何决策规则？）
```

---

## 📐 质量标准

- **概念页面**：定义 + 核心原理 + 决策规则 + 关联案例
- **实体页面**：背景 + 在舆情体系中的位置 + 关联资源
- **来源摘要**：忠于原文 + 核心论点 + 个人评注
- **案例分析**：输入→输出→判据链→边界讨论→对规范的影响（五段完整）
- **标注规范**：作为活文档，始终保持与案例库的一致性

---

## 🖥️ Streamlit 开发规则

- **Tab 导航**：始终用 `st.radio(key='active_tab')` + session_state，禁止在 widget 实例化后修改 active_tab（会触发 StreamlitAPIException），用 deferred-switch 模式
- **Widget key 唯一性**：所有交互组件必须有唯一 `key=`，跨文件重构后检查 key 碰撞
- **调试前置**：`lsof -i :8501` 杀残留进程，避免旧代码干扰
- **for 循环变量覆盖**：for 循环解包变量名不要与外层对象同名（如 `for publisher in...` 覆盖外层 publisher 对象），pytest 不可见仅浏览器暴露

## 🤖 6-Agent 舆情指挥系统

### 架构总览

```
┌─────────────── Orchestrator ───────────────┐
│ 流A: URL → Scraper → Analyst → Handler → Curator │
│ 流B: Monitor → [for each new item] → 流A          │
│ 流C: Curator.query → DailyReport → .md            │
│ 流D: KB Q&A (扫地僧)                              │
│ P0/P1 熔断: Analyst → emergency_dispatch() → 弹窗+Webhook │
└─────────────────────────────────────────────┘
```

### Agent 权限矩阵

| 操作 | Monitor | Scraper | Analyst | Handler | Curator | Daily Rpt | Orchestrator |
|------|---------|---------|---------|---------|---------|-----------|--------------|
| 关键词搜索 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 内容抓取 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| LLM 标注 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 处置方案 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| KB 写入 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 日报/月报 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 跨Agent传递 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅(唯一) |

### 模型分配

| Agent | 模型 | 原因 |
|-------|------|------|
| Monitor | 无 (纯代码) | 搜索/去重/Excel |
| Scraper | 无 (纯代码) | 抓取/解析 |
| Analyst | DeepSeek (deepseek-chat) | 复杂推理+严格JSON |
| Handler | DeepSeek (deepseek-chat) | 逻辑一致性 |
| Curator | DeepSeek (Q&A) + 模板 | 低需求/低成本 |
| Daily Report | DeepSeek (MiniMax备选) | 中文长文生成 |

### 关键命令

```bash
# Web UI
streamlit run app.py --server.port 8501

# 调度器
python scheduler.py            # 启动守护进程
python scheduler.py --once     # 测试：运行全部任务一次
python scheduler.py --daily    # 仅生成日报
python scheduler.py --monitor  # 仅执行 Monitor 巡检

# Cookie 管理 (XHS 搜索需要)
python -c "import sys; sys.path.insert(0,'engine'); from xhs_fetcher import bootstrap_cookies; bootstrap_cookies(force=True)"

# 测试
python -m pytest tests/ -x -q
```

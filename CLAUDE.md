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
├── raw/                原始资料收件箱 —— 只读，永不修改
│   ├── cases/          待处理的舆情案例原文
│   └── archive/        ingest 后的归档区
│
├── wiki/               知识编译输出层 —— AI 全权维护
│   ├── index.md        全局索引（所有 wiki 页面的摘要目录）
│   ├── log.md          操作日志（append-only，记录每次变更）
│   ├── concepts/       标注概念（严重度评级、情感分析、分流判断等）
│   ├── entities/       实体（工具、平台）
│   ├── sources/        来源摘要（工作复盘文档提炼）
│   ├── syntheses/      综合文档（标注规范活文档）
│   └── cases/          标注案例库（迭代引擎）
│
├── outputs/            对外输出
│
└── CLAUDE.md           本文件 —— AI Agent 操作手册
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

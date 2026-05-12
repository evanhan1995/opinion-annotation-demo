# 舆情标注系统 —— 深化设计方案

> 版本: v0.1-draft | 日期: 2026-05-12 | 状态: 方案评估阶段，暂不执行

---

## 1. 当前状态诊断

### 1.1 已完成（Phase 1-4）

```
用户输入 URL
  → scraper.py（平台检测 + 抓取调度）
    ├── YouTube → yt-dlp（视频元数据 + 评论区）✅
    ├── 小红书  → xhshow API（笔记详情 + 评论区）✅
    ├── Reddit  → Playwright ✅
    └── X       → Playwright ✅
  → annotate.py（LLM 标注：严重度/分流/情感/风险标签/评论区红绿灯）✅
  → Web UI（Streamlit，含纠偏功能）✅
```

### 1.2 存在但空的目录（原始设计预留，未接入）

| 目录 | 设计意图 | 当前状态 |
|------|---------|---------|
| `raw/` | 原始资料收件箱 | 空——每次抓取的内容从未落盘 |
| `raw/cases/` | 待处理的舆情案例原文 | 不存在，目录未创建 |
| `raw/archive/` | 处理后归档 | 不存在 |
| `outputs/` | 对外输出 | 空——标注结果从未落盘 |

### 1.3 已有的 Wiki 资产

| 目录 | 内容 | 数量 |
|------|------|------|
| `wiki/concepts/` | 标注概念定义 | 5 页 |
| `wiki/entities/` | 工具/平台实体 | 2 页 |
| `wiki/sources/` | Evan 的工作复盘提炼 | 2 页 |
| `wiki/syntheses/` | 标注规范活文档 | 1 页 |
| `wiki/cases/` | 标注案例（含判据链） | 7 页 |
| `wiki/index.md` | 全局索引 | 91 行 |
| `wiki/log.md` | 操作日志 | 64 行 |

### 1.4 核心缺口：数据流断在内存里

```
当前实际流程：
  URL → 抓取 → 内存(dict) → Streamlit展示 → 用户关闭页面 → 💀数据消失
                                                  ↘ 纠偏 → wiki/cases/ ✅（唯一落盘路径）

设计目标流程（CLAUE.md 定义）：
  URL → 抓取 → raw/cases/ → AI Ingest → wiki/cases/ + concepts更新 + syntheses更新
                     ↘ outputs/（标注结果存档）
```

**结论**：抓取和标注两条核心链路已通。但整个"知识库自动积累"的闭环是**完全断开的**——`raw/` 和 `outputs/` 是空壳，Ingest 操作从未被触发过。

---

## 2. 用户愿景拆解

用户描述了四个层次的目标：

| 层次 | 目标 | 当前状态 |
|------|------|---------|
| L1 | 每次输入链接，内容自动记录到知识库 | ❌ 未实现 |
| L2 | 知识库积累 → AI 标注越来越聪明 | 框架就绪，缺少自动 Ingest |
| L3 | 智能体（扫地僧）打理知识库，可交互参谋 | ❌ 未实现 |
| L4 | 多人协作（飞书替代 Obsidian） | 远期，架构需预留 |

**当前最紧迫的 L1 约束**：用户需要把 Demo 放到简历中，让 HR 在线直观感受。

---

## 3. 可行性研判

### 3.1 技术可行性：高

所有核心技术组件已单独验证：

| 组件 | 技术栈 | 验证状态 |
|------|--------|---------|
| XHS 抓取 | xhshow + httpx | ✅ 已验证，2-3s 完成 |
| YouTube 抓取 | yt-dlp | ✅ 已验证，3-5s 完成 |
| Reddit/X 抓取 | Playwright | ✅ 已验证 |
| LLM 标注 | DeepSeek/Claude/OpenAI | ✅ 已验证 |
| Wiki 页面生成 | Python 字符串模板 | ✅ correction_handler 已实现 |
| Streamlit Web UI | streamlit | ✅ 已运行 |

### 3.2 风险点

| 风险 | 等级 | 缓解 |
|------|------|------|
| XHS Cookie 过期 | 中 | 已在 xhs_fetcher 中自动检测+提示重登 |
| LLM API 费用 | 低 | 用户使用自己的 API Key，按量付费 |
| 案例质量依赖 LLM 输出 | 中 | 纠偏机制已就绪，人工审核兜底 |
| Streamlit 单用户限制 | 低 | Demo 阶段无需多用户；L4 才需要 |

### 3.3 研判结论

**完全可行**。当前缺的不是技术能力，而是把已验证的零件组装成闭环管线的工程工作。L1-L2 在一个迭代内可完成。L3 需要额外设计 Agent 交互层。L4 涉及到架构迁移，不应在 Demo 阶段处理。

---

## 4. 分阶段路线图

### Phase 5：自动化 Ingest 管线（Demo 就绪）★ 首要任务

**目标**：让 HR 看到一个"活的系统"——输入链接 → 自动抓取 → 自动标注 → 自动存入知识库 → 知识库页面可浏览。

**具体改动**：

```
A. 抓取落盘（scraper 增强）
   scrape(url) → 同时写入 raw/YYYY-MM-DD_platform_noteid.json
   每次抓取自动留痕，raw/ 不再为空

B. 自动 Ingest（新增 engine/ingestor.py）
   抓取完成 → 自动触发 Ingest：
     1. LLM 标注（复用 annotate.py）
     2. 生成 wiki/cases/case-XXX.md（含判据链+边界讨论，复用 correction_handler 模板）
     3. 检查是否触及规则边界 → 必要时更新 concepts/ 和 syntheses/
     4. 更新 wiki/cases/index.md
     5. 写入 wiki/log.md
     6. 原始文件移入 raw/archive/

C. 标注落盘（outputs 激活）
   标注结果 → 同时写入 outputs/YYYY-MM-DD_platform_noteid_annotation.json

D. Wiki 浏览页（Streamlit 新增 tab）
   在 Web UI 中新增"知识库"tab，可浏览 wiki/ 中的页面
   （概念、案例、实体、标注规范等）
```

**Demo 效果**：HR 打开链接 → 看到 Web UI → 粘贴一条 XHS/YouTube 链接 → 3 秒后看到标注结果 → 切换到"知识库"tab → 看到案例库中新增了一条，wiki 页面自动更新。

**预计工作量**：~200 行新代码，1-2 个新文件，主要改动在 scraper.py 和新增 ingestor.py。

---

### Phase 6：扫地僧 Agent（知识库交互层）

**目标**：用户可以用自然语言与知识库对话——"最近一周小红书上有多少 P0 案例？""这个季度负面舆情的趋势是什么？"

**技术方案**：

```
用户提问
  → Agent（Claude API / DeepSeek）
    → 检索 wiki/ 知识库（RAG 或直接读取相关页面）
    → 综合回答 + 引用来源
  → Streamlit 对话界面
```

**关键设计决策**：不需要向量数据库。wiki/ 本身就是结构化的 Markdown 知识库，总页面数在几十到几百量级，Agent 直接读取相关页面 + 拼接上下文即可。这与 Karpathy Wiki 的思路一致——知识库本身就是 Agent 的 working memory。

**预计工作量**：~300 行新代码，1 个新文件（agent.py），Streamlit 新增对话 tab。

---

### Phase 7：飞书/多人协作适配（远期）

**目标**：知识库从本地 Markdown 迁移到飞书文档/多维表格，支持团队协作。

**不做详细设计**——这个阶段的选型取决于：
- 团队实际使用的协作平台（飞书/Notion/Confluence）
- 知识库规模（如果 <200 页，Markdown + Git 足够）
- 权限管理需求

---

## 5. Resume Demo 优先级矩阵

以"HR 在线感受"为唯一成功标准，对所有功能排序：

| 优先级 | 功能 | HR 感知 | 实现难度 |
|--------|------|---------|---------|
| P0 | 输入链接 → 自动标注 → 结果展示 | ★★★★★ 核心体验 | 已完成 |
| P0 | 标注结果自动存入知识库 | ★★★★ 系统感 | 低（1-2天） |
| P0 | 知识库页面可在线浏览 | ★★★★ 专业感 | 低（1天） |
| P1 | 纠偏功能（已有） | ★★★ 体现迭代设计 | 已完成 |
| P1 | 评论区红绿灯（已有） | ★★★ 可视化亮点 | 已完成 |
| P2 | 扫地僧对话 Agent | ★★★★★ 惊艳 | 中（3-5天） |
| P2 | 知识库 Dashboard（统计图表） | ★★★★ 专业 | 中（2-3天） |
| P3 | 多平台支持展示（已有 4 平台） | ★★ | 已完成 |

**建议**：Phase 5（自动 Ingest + Wiki 浏览）是让 Demo 从"能用的工具"升级为"有积累的系统"的最低成本路径。Phase 6（扫地僧 Agent）如果时间允许，是最大的加分项。

---

## 6. Phase 5 技术设计（详细）

### 6.1 新增模块：`engine/ingestor.py`

```
ingestor.py 职责：
  - 接收 scraped_data + annotation_result
  - 生成 wiki/cases/case-XXX.md
  - 判断是否更新 concepts/ 或 syntheses/
  - 更新 index.md 和 log.md
  - 归档 raw 文件
```

### 6.2 数据流

```
app.py（Streamlit）
  │
  ├── [抓取] scraper.scrape(url)
  │   ├── 返回 dict
  │   └── 写入 raw/YYYY-MM-DD_platform_id.json  ★ 新增
  │
  ├── [标注] annotate_one(content, system_prompt, config)
  │   ├── 返回标注结果
  │   └── 写入 outputs/YYYY-MM-DD_platform_id_annotation.json  ★ 新增
  │
  └── [Ingest] ingestor.ingest(scraped_data, annotation_result)  ★ 新增
      ├── 生成 wiki/cases/case-XXX.md
      ├── 边界检查 → 可能更新 concepts/ 或 syntheses/
      ├── 更新 wiki/cases/index.md
      ├── 写入 wiki/log.md
      └── 归档 raw/ → raw/archive/
```

### 6.3 Wiki 浏览页

Streamlit 新增 tab "知识库"：
- 左侧：目录树（按 type 分组：concept/entity/case/synthesis/source）
- 右侧：选中页面的 Markdown 渲染
- 底部：最近操作日志（最近 10 条 log）

### 6.4 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `engine/ingestor.py` | 自动 Ingest 管线 |
| 修改 | `engine/scraper.py` | scrape() 增加 raw/ 落盘 |
| 修改 | `app.py` | 新增知识库浏览 tab；标注后触发 Ingest |
| 新增 | `raw/cases/` 目录 | 待处理案例 |
| 新增 | `raw/archive/` 目录 | 已处理归档 |

---

## 7. 扫地僧 Agent 设计预览（Phase 6）

### 7.1 交互模式

```
用户: "最近一周小红书上有多少 P0 级舆情？"
Agent: [读取 wiki/cases/index.md + wiki/log.md]
       → "过去 7 天共有 3 个 P0 案例：
          1. case-005: 产品安全问题投诉激增
          2. case-007: KOL 负面评测扩散
          3. case-009: ...
          建议关注 case-007，该案例评论区仍在发酵。"

用户: "对比一下 TEMU 和 DJI 的舆情模式有什么不同？"
Agent: [读取 wiki/sources/ 中的两篇复盘 + wiki/cases/ 中的相关案例]
       → 综合分析 + 引用来源
```

### 7.2 技术架构

```
agent.py
  ├── 检索层：基于 wiki/index.md + frontmatter 的关键词/语义匹配
  ├── 推理层：Claude API / DeepSeek，拼接检索结果 + 用户问题
  └── 输出层：Streamlit 对话组件 + 来源引用
```

**不需要向量数据库的理由**：
- wiki/ 当前 ~20 个页面，Phase 5 后估计 ~50 页
- Markdown frontmatter 已包含 tags、type、severity 等元数据
- 关键词 + frontmatter 过滤 + 全文搜索足够覆盖
- 当知识库 >500 页时再考虑引入 embedding + vector search

---

## 8. 架构原则（贯穿所有 Phase）

1. **raw/ 永不修改**——原始数据只追加，不覆盖。这是 Karpathy Wiki 的核心原则。
2. **wiki/ 由 AI 全权维护**——人类通过投放案例和纠偏间接影响，不直接编辑 wiki。
3. **每次操作有日志**——wiki/log.md append-only，可审计。
4. **规则来自案例**——不凭空调整标注规范，每次修改必须注明触发案例。
5. **Demo 优先**——所有 Phase 5-6 的改动不能破坏现有 Web UI 的基本可用性。

---

## 9. 建议执行顺序

```
现在 → Phase 5（1-2 次对话）→ Demo 就绪
     → 用户测试 → 修 bug
     → Phase 6（可选，2-3 次对话）→ 扫地僧 Agent
     → 简历投递 🚀
     → Phase 7（远期，视需求启动）
```

---

*本文件位于 `D:\Claude code\舆情标注Wiki\DESIGN.md`，作为后续开发的参考基线。随项目推进持续更新。*

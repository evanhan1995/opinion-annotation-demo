# 知识库升级：从案例流水账到情报决策系统

## Problem Statement

当前知识库是"自动生成的案例流水账"——每条案例独立存储，标签由LLM自由生成，搜索靠中文字符bigram重叠。公关团队无法回答四个核心问题：这个案例以前见过吗？现在整体态势如何？类似情况我们怎么处理的？如何向领导汇报？

## Recommended Direction

**总体规划 + 4 Phase分批实施**，在不改动现有爬取→标注→处置流水线的前提下，逐步升级知识库的存储、检索、分析和输出能力。

每个Phase独立可验证、独立可上线。

### Phase 架构

```
Phase 1: 知识结构化 (Foundation)
├── 受控词表定义 (叙事分类/风险标签/情感维度/处置策略)
├── Ingestor改造: LLM从词表选择而非自由生成
├── 案例frontmatter字段标准化 (新增 narrative_thread, target_type 等)
└── 索引管理器升级 (按词表维度重建索引)

Phase 2: 智能检索+经验复用 (Intelligence Core)
├── 语义检索: DeepSeek Embedding + 向量相似度替代bigram
├── 策略库: 处置策略的结构化存储和检索
├── 复盘模板: P0/P1结案强制结构化复盘
└── "相似案例"自动匹配: 新案例入库时找历史Top-3

Phase 3: 态势感知 (Situational Awareness)
├── 叙事追踪: 案例归属于叙事线程，线程有时序和趋势
├── 叙事仪表盘: 取代纯数据报表为叙事简报
├── 竞品雷达: Monitor关键词扩展+竞品维度切片
└── 预警升级: 多平台话题热度同时上升→预警信号

Phase 4: 工程加固 (Engineering Hardening)
├── SQLite迁移: 元数据查询走SQL+FTS5，文件仍保留
├── Office适配器: 飞书文档/多维表格导出
├── 通用.docx导出: 不依赖平台的兜底方案
└── 性能优化: 1000+案例的查询性能保障
```

### 不碰的东西

- Agent隔离架构 (Orchestrator唯一路由)
- 爬取→标注→处置核心流水线
- Markdown+YAML文件存储（保留为source of truth）
- Streamlit 8-Tab结构（Tab内升级，不增加Tab数量）

## Key Assumptions to Validate

- [ ] **LLM能在受控词表约束下准确选择标签** — 取50条已有案例，对比自由生成vs词表选择的准确率，目标≥85%
- [ ] **语义Embedding对中文舆情文本有实用区分度** — 取20对案例做人工相关性评分，对比Embedding余弦相似度的排序一致性
- [ ] **叙事可以靠标签+语义+时间窗口自动聚合** — 人工标注10个叙事的案例归属，对比自动分组结果
- [ ] **复盘模板会被实际填写** — Phase 2上线后观察2周内的复盘填写率

## MVP Scope (Phase 1)

**目标：统一知识库的"语言"——让所有案例用同一套标签说话。**

具体交付：
1. `wiki/taxonomy/` 目录，含3个词表文件：
   - `narrative_categories.md` — 叙事分类层级（3层，~30个叶子节点）
   - `risk_tags.md` — 风险标签树（~20个标签，含定义和示例）
   - `disposition_actions.md` — 处置策略枚举（~10种）
2. 修改 `engine/ingestor.py` 的 `_generate_auto_case()` — frontmatter新增 `narrative_thread`、`target_type` 字段
3. 修改 `engine/annotate.py` 的prompt — LLM标注时传入词表，要求从中选择
4. 修改 `engine/index_mgr.py` — 索引表增加"叙事分类"维度列
5. 修改 `engine/agent.py` 的 `search_wiki()` — 搜索时利用词表做查询扩展
6. **不做**：语义检索、叙事追踪、策略库、SQLite

## Not Doing (and Why)

- **SQLite → 所有案例存数据库** — Phase 1不需要，文件系统在500案例内完全够用。等案例数上去再迁移，且文件保留为source of truth
- **叙事仪表盘新Tab** — Phase 1只做词表和标签标准化，叙事追踪是Phase 3的事
- **飞书文档导出** — Phase 4的Office适配器统一做，现在做会分散精力
- **新增Agent** — 知识库的改造全部在Curator+Ingestor+扫地僧现有Agent边界内完成，不引入新Agent
- **多用户/协作功能** — 当前单人使用，等有团队需求再加
- **复盘强制机制** — Phase 2做，Phase 1只定义复盘模板结构
- **UI大改** — Tab内组件升级，不改变8-Tab结构

## Open Questions

- 叙事分类的层级深度：3层是否足够？还是2层更实用？
- 风险标签是否需要支持多选（一个案例打多个标签）？当前已支持，词表化后是否限制最多3个？
- 竞品列表是否硬编码在配置文件中，还是从词表动态读取？
- Phase 1 完成后是否需要回填历史案例的标签？

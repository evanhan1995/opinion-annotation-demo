# Spec: 知识库 Phase 1 — 知识结构化（受控词表 + 标签标准化）

## Objective

统一知识库的"语言"——让所有案例用同一套标签体系说话，为后续语义检索、叙事追踪、策略库打下数据基础。

**目标用户**: 分析师（更好的搜索和案例对比）+ 管理者（可按维度聚合查看态势）

**核心交付**: 受控词表文件 + 词表管理UI + Annotate/Ingest/Index改造

## Design Decisions (grill 已决议)

| # | 决策 | 结论 |
|---|---|---|
| 1 | 词表来源 | 统计已有标注高频标签 + AI补全行业框架 |
| 2 | LLM选标签模式 | 宽松模式：优先从词表选，找不到时可建议候选标签（标记 `[候选]`） |
| 3 | 案例与叙事映射 | 一主多从：`narrative_thread`（主）+ `secondary_threads`（从） |
| 4 | 叙事层级深度 | 2层起步，后期支持在UI分裂出L3 |
| 5 | 词表管理 | UI上可增删改分类节点、调整层级、手动改案例归属、上传/删除案例 |
| 6 | 风险标签上限 | 每个案例最多3个 |
| 7 | 语义检索 | Phase 2，入库时生成Embedding存本地JSON（不做向量库） |
| 8 | 策略库冷启动 | LLM即时生成 + 处置人确认 → 入库 |
| 9 | 复盘流程 | 软标记"待复盘"，指标可见，预留团队协作字段 |
| 10 | 竞品列表 | `config/competitors.json` + Settings UI管理，Phase 3实现 |

## Tech Stack

- Python 3.14, Streamlit, DeepSeek API (标注), MiniMax (报告)
- 现有架构：Agents (Orchestrator/Curator/Analyst) + Engine (ingestor/annotate/index_mgr) + UI (Streamlit 8-Tab)
- 存储：Markdown + YAML frontmatter（不引入新数据库）

## Commands

```bash
# 开发
streamlit run app.py --server.port 8501

# 测试
python -m pytest tests/ -x -q

# 单独测试 Phase 1 相关
python -m pytest tests/test_core.py -v -k "index"
python -m pytest tests/test_ingestor.py -v  # 新建
python -m pytest tests/test_taxonomy.py -v   # 新建
```

## Project Structure (改动文件)

```
新增:
├── wiki/taxonomy/                    # 受控词表目录
│   ├── narrative_categories.md       # 叙事分类层级 (2层 ~12类)
│   ├── risk_tags.md                  # 风险标签树 (~20个)
│   └── disposition_actions.md        # 处置策略枚举 (~10种)
├── engine/taxonomy_mgr.py            # 词表加载/校验/候选管理
├── tests/test_taxonomy.py            # 词表测试
└── tests/test_ingestor.py            # Ingestor测试 (从test_core.py拆出)

修改:
├── engine/annotate.py                # prompt传入词表，LLM从词表选标签
├── engine/ingestor.py                # frontmatter新增字段 + 词表校验
├── engine/index_mgr.py               # 索引增加"叙事分类"维度列
├── engine/agent.py                   # search_wiki利用词表做查询扩展
├── ui/tab_knowledge.py               # 新增词表管理界面
├── ui/tab_settings.py                # 知识库设置（候选标签审核入口）
├── agents/curator.py                 # query_cases增加叙事维度筛选
├── prompts/analyst_system.txt        # 标注prompt同步更新
└── tests/test_core.py                # 补充词表相关测试

不改:
├── agents/orchestrator.py            # 不改路由逻辑
├── agents/monitor.py                 # 不改监测逻辑
├── agents/scraper.py                 # 不改抓取逻辑
├── agents/handler.py                 # 不改处置逻辑（Phase 2才联动策略库）
├── agents/sentinel.py                # 不改预过滤
├── pipeline.py                       # 不改流水线
└── scheduler.py                      # 不改调度
```

## Data Model

### 词表文件格式

所有词表文件使用 Markdown + YAML frontmatter，保持与现有Wiki格式一致。

**narrative_categories.md**:
```markdown
---
title: 叙事分类词表
type: taxonomy
taxonomy_type: narrative_category
version: 1
created: 2026-06-02
updated: 2026-06-02
---

# 叙事分类

## 产品质量
- **定义**: 涉及产品功能、安全、质量的舆情事件
- **子类**:
  - 食品安全 (异物投诉、添加剂争议、过期变质)
  - 产品安全 (用户受伤、火灾爆炸隐患、化学品超标)
  - 功能缺陷 (性能不达标、设计缺陷、兼容性问题)

## 企业行为
- **定义**: 涉及企业经营管理行为的舆情事件
- **子类**:
  - 劳工争议 (裁员纠纷、欠薪福利争议、工作环境)
  - 合规问题 (监管处罚、税务争议、数据合规)
  - 高管言行 (失言风波、丑闻、离职)

## 市场营销
- **定义**: 涉及营销活动、广告宣传的舆情事件
- **子类**:
  - 广告争议 (虚假宣传、不当创意、代言人风波)
  - 价格争议 (涨价、杀熟、定价歧视)
  - 竞品攻击 (对比广告、黑稿、水军)

## 突发事件
- **定义**: 不可预见的紧急事件
- **子类**:
  - 自然灾害关联
  - 公共安全事件
  - 供应链中断
```

**risk_tags.md**:
```markdown
---
title: 风险标签词表
type: taxonomy
taxonomy_type: risk_tag
version: 1
created: 2026-06-02
---

# 风险标签

## 传播风险
- 病毒式传播 (快速扩散，跨平台蔓延)
- 大V/KOL介入 (有影响力的账号参与讨论)
- 媒体跟进 (传统媒体或垂直媒体报道)

## 品牌风险
- 品牌声誉受损 (直接攻击品牌形象)
- 用户信任危机 (质疑诚信、数据安全)
- 竞品对比 (被与竞品进行不利对比)

## 法律风险
- 监管违规 (涉嫌违反法规)
- 用户索赔 (用户要求赔偿或集体诉讼)
- 知识产权 (侵权指控)

## 运营风险
- 客服投诉 (对客服处理不满)
- 产品召回 (需要或可能召回)
- 供应链问题 (产能、物流问题)

## 情绪风险
- 群体愤怒 (评论区情绪极化)
- 二次伤害 (回应不当引发更大危机)
- 长尾效应 (事件反复被提起)
```

**disposition_actions.md**:
```markdown
---
title: 处置策略词表
type: taxonomy
taxonomy_type: disposition_action
version: 1
created: 2026-06-02
---

# 处置策略

## 立即响应
- 公开发声明 (官方渠道发布声明)
- 产品下架/召回
- 法律行动 (律师函、起诉)

## 持续管理
- 舆情引导 (正面内容对冲)
- 媒体沟通 (主动联系媒体)
- KOL合作 (与关键意见领袖沟通)
- 客服介入 (逐一回复用户)

## 监控观察
- 持续监测 (观察发展态势)
- 暂不回应 (研判后认为回应反而扩大影响)

## 正面利用
- 借势营销 (利用热点正面传播)
- 案例宣传 (将事件转化为正面案例)
```

### 案例 frontmatter 新增字段

现有 frontmatter（`engine/ingestor.py` `_generate_auto_case()` 产出）:
```yaml
title: ...
type: case
created: 2026-06-02
severity: P2
action: 持续观察
platform: 小红书
source: auto_ingest
status: 待跟进
url: ...
categories: [...]
author: ...
notes: ...
tags: [auto_ingest, P2]
```

**Phase 1 新增字段**:
```yaml
narrative_thread: 产品质量/食品安全    # 主叙事（L1/L2格式，必选，LLM从词表选）
secondary_threads:                    # 次要叙事（可选，最多2个）
  - 企业行为/合规问题
risk_tags_controlled:                 # 受控风险标签（最多3个，从词表选）
  - 品牌声誉受损
  - 病毒式传播
risk_tags_candidate: []               # LLM建议的新标签（不在词表中的候选）
target_type: 我方                      # 我方/竞品A/竞品B/行业通用 (Phase 3启用)
```

`tags` 字段保留（向后兼容），内容从自由文本改为 `[auto_ingest, {severity}, {narrative_L1}, {narrative_L2}]`

### 候选标签管理

`wiki/taxonomy/candidate_tags.json`:
```json
{
  "pending": [
    {
      "label": "AI换脸诈骗",
      "category": "risk_tag",
      "suggested_by": "case-015",
      "suggested_at": "2026-06-02",
      "context": "涉及使用AI换脸技术进行诈骗的内容"
    }
  ],
  "approved": [],
  "rejected": []
}
```

## Code Style

遵循项目现有约定：
- UTF-8编码适配（所有新文件头部或函数级 `sys.stdout.reconfigure(encoding="utf-8")`）
- Type hints 用于公共API
- `Path` 而非 `os.path`
- 中英双语注释不强制，关键逻辑可加
- 复用 `agents/shared.py` 的 `call_with_timeout`、`extract_json`、路径常量

关键模式示例（来自 engine/index_mgr.py）:
```python
"""模块docstring —— 一句话职责说明。"""
import re
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ENGINE_DIR.parent

def public_api(param: str) -> dict:
    """Public function with type hints."""
    ...
```

## Testing Strategy

- **框架**: pytest（现有）
- **测试位置**: `tests/test_taxonomy.py`（新建）、`tests/test_ingestor.py`（新建）、`tests/test_core.py`（扩展）
- **覆盖要求**: 词表加载/校验100%覆盖，frontmatter解析覆盖新增字段
- **测试模式**: 使用 `tmp_path` fixture 创建临时词表文件，参考 `test_core.py` 现有模式

新增测试用例：
1. `test_load_taxonomy_valid` — 合法词表文件加载
2. `test_load_taxonomy_missing_file` — 词表文件不存在时回退到旧行为
3. `test_validate_tags_controlled` — 标签在词表内 → 通过
4. `test_validate_tags_candidate` — 标签不在词表内 → 标记为候选
5. `test_frontmatter_roundtrip` — 新增字段写入→读取一致
6. `test_index_update_with_narrative` — 索引表包含叙事列
7. `test_max_three_risk_tags` — 超过3个标签时截断/报错

## Success Criteria

- [ ] 三个词表文件存在且格式合法（YAML frontmatter + Markdown body）
- [ ] `engine/taxonomy_mgr.py` 可加载词表并返回结构化数据
- [ ] `engine/annotate.py` prompt 包含词表，LLM输出的 `risk_tags_controlled` 字段90%以上在词表内
- [ ] `engine/ingestor.py` 生成的案例 frontmatter 包含所有新增字段
- [ ] 词表管理UI可增删改分类节点
- [ ] 知识库UI可手动修改案例的叙事归属
- [ ] 候选标签审核入口可见
- [ ] `python -m pytest tests/ -x -q` 全部通过（包括新增和已有测试）
- [ ] 原有流程不受影响：爬取→标注→处置→入库仍可完整走通

## Boundaries

### Always
- 词表文件为 Markdown + YAML frontmatter，与现有Wiki格式一致
- 所有路径使用 `pathlib.Path`
- 修改后跑 `python -m pytest tests/ -x -q`
- 保持 Agent 隔离架构：Orchestrator 是唯一跨Agent路由
- 新代码遵循现有编码风格（UTF-8适配、type hints、docstring）

### Ask First
- 新增 Python 依赖包
- 修改 Agent 职责边界
- 删除或重命名已有公开API函数
- 修改 Streamlit session_state 键名（可能破坏现有状态管理）

### Never
- 修改 Agent 间直接调用（破坏隔离）
- 删除现有案例文件或索引
- 在 annotate.py prompt 中移除已有标注维度
- 修改 `agents/shared.py` 的 dataclass 字段含义（只新增，不改含义）

## Open Questions

- [ ] 叙事分类L1/L2的具体命名和数量——先AI生成初稿，再人工审阅
- [ ] 现有历史案例是否需要回填词表标签？建议：不需要，Phase 1 上线后新入库的案例自动用词表，老案例保持原样
- [ ] 词表版本管理——暂不做，词表文件手动Git管理即可

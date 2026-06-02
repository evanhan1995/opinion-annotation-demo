# Spec: v6.0 混合智能引擎

## Objective

将舆情标注Wiki从"纯LLM串行流水线"升级为"本地模型+LLM仲裁+跨平台交叉验证"的混合智能架构。核心目标三个：

- **降本**：BERT本地预标注替代60%+的LLM调用
- **提质**：Forum跨平台交叉验证将纠偏率从67%提升至85%+
- **自动化**：话题自动发现替代手动关键词配置

用户故事：
1. 系统每天自动从热搜发现话题 → 无需人工配置关键词
2. 80%的内容由本地BERT直接标注 → API成本大幅下降
3. 同一事件在不同平台的标注结果自动交叉验证 → 发现矛盾标记人工复核
4. 日报包含趋势图表 → 可以拿给领导看

## Tech Stack

| 层级 | 当前 | v6.0新增 |
|---|---|---|
| 标注模型 | DeepSeek API (100%) | DeepSeek API (~30%) + BERT本地 (~70%) |
| 交叉验证 | 无 | LLM Host (DeepSeek, 按需调用) |
| 话题发现 | 手动配置 | 热搜API + LLM关键词提取 |
| 规则过滤 | 无 | 关键词/正则规则引擎 |
| 报告 | Markdown | Markdown + Plotly图表 |
| 推理框架 | 无 | PyTorch + HuggingFace Transformers |
| 分词 | 无 | jieba (规则引擎用) |

新增依赖：
```
torch>=2.0.0
transformers>=4.30.0
plotly>=5.15.0
jieba>=0.42.1
kaleido>=0.2.1  (Plotly静态图片导出)
```

## Commands

```bash
# 测试 (每Phase后必须全绿)
python -m pytest tests/ -x -q

# 单独测试某个模块
python -m pytest tests/test_core.py -x -q -k "test_sentinel"

# 运行完整系统
cd D:\Claude code\舆情标注Wiki
streamlit run app.py

# Lint (可选)
ruff check agents/ engine/ --quiet

# 首次安装新依赖
pip install torch transformers plotly jieba kaleido
```

## Project Structure

```
舆情标注Wiki/
├── agents/
│   ├── sentinel.py        NEW — 哨兵Agent (规则引擎+BERT预标注+话题发现)
│   ├── forum.py           NEW — 论坛Agent (跨平台交叉验证)
│   ├── analyst.py         MODIFY — 加LLM仲裁分支 (use_llm参数)
│   ├── orchestrator.py    MODIFY — Flow B加forum步骤
│   ├── handler.py         NO CHANGE
│   ├── curator.py         NO CHANGE
│   ├── monitor.py         MODIFY — 加话题自动发现入口
│   ├── daily_report.py    MODIFY — Plotly图表
│   ├── scraper.py         NO CHANGE
│   └── shared.py          MODIFY — 加SentinelResult/ForumResult dataclass
│
├── engine/
│   ├── linker.py          NO CHANGE — Forum基础 (已有跨平台匹配)
│   ├── browser_pool.py    NO CHANGE
│   ├── _compat.py         NO CHANGE
│   └── ...
│
├── models/                NEW — 本地模型存储
│   └── bert-sentiment/    BERT情感分类模型 (~400MB, gitignore)
│
├── tests/
│   ├── test_sentinel.py   NEW — 规则引擎+BERT预标注测试
│   ├── test_forum.py      NEW — 交叉验证测试
│   └── ...                EXISTING — 138条测试保持不变
│
├── docs/
│   └── ideas/
│       └── v6-hybrid-intelligence.md  THIS FILE
│
└── prompts/
    └── forum_host.txt     NEW — Forum主持人LLM的system prompt
```

## Code Style

遵循现有项目约定。关键模式：

```python
# -*- coding: utf-8 -*-
"""Sentinel Agent — 哨兵：规则过滤 + BERT预标注 + 话题发现。

Responsibility (PRD v6.0):
  1. Rule engine: 垃圾广告/无关内容过滤 (关键词+正则)
  2. BERT pre-annotation: 本地推理情感+严重度初筛
  3. Topic discovery: 热搜→关键词→Monitor触发

Isolation constraints:
  - MUST NOT modify KB (Curator's job)
  - MUST NOT generate action plans (Handler's job)
  - MUST route ALL uncertain cases to Analyst for LLM arbitration
"""

import engine._compat

from agents.shared import (
    PROJECT_ROOT,
    RawData, Annotation, SentinelResult,
)
```

约定：
- 文件头 `# -*- coding: utf-8 -*-` 必须
- 第一行 `import engine._compat` (UTF-8适配，不重复内联代码)
- 类/函数 docstring 用中文
- dataclass 定义在 `agents/shared.py` 统一管理
- 模型调用统一走 `agents/shared.py` 的 `get_llm()`
- 禁止emoji（Windows兼容）

## Testing Strategy

- 框架：pytest（已有）
- 位置：`tests/` 目录
- 覆盖要求：每个新模块≥5条测试
- 测试等级：
  - **单元测试**：规则引擎规则匹配、BERT推理结果格式、Forum prompt构建
  - **集成测试**：Sentinel→Analyst数据流、Forum基于linker结果触发验证
- 模型相关测试使用mock（避免下载400MB模型到CI）
- 每Phase改完立即跑 `python -m pytest tests/ -x -q`

测试命名约定（与现有保持一致）：
```python
class TestSentinelRuleEngine:
    def test_filter_spam_by_keyword(self): ...
    def test_filter_irrelevant_by_regex(self): ...
    def test_pass_normal_content(self): ...

class TestSentinelBERT:
    def test_predict_sentiment_positive(self): ...
    def test_predict_sentiment_negative(self): ...
    def test_low_confidence_routes_to_llm(self): ...
```

## Boundaries

### Always do
- 每Phase后跑 `python -m pytest tests/ -x -q` 全绿再标记完成
- 新Agent模块遵循现有隔离约束（不跨Agent直接调用）
- 外部API调用前做单次测试验证响应格式
- 代码中用 `import engine._compat` 而非内联UTF-8适配
- dataclass定义放在 `agents/shared.py`

### Ask first
- 数据库schema变更（如新增表存BERT缓存结果）
- 安装需要编译的依赖（如PyTorch CUDA版本）
- 修改 `pipeline.py` 或 `app.py` 的顶层入口逻辑
- Docker化或CI/CD配置变更

### Never do
- 在Sentinel/Forum中直接调用Curator写KB
- 绕过Orchestrator做Agent间数据传递
- 在非Windows环境测试前假设编码行为
- 删除或修改现有138条测试的预期结果
- 引入需要GPU的依赖（默认用CPU推理）

## Success Criteria

| # | 标准 | 验证方式 | Phase |
|---|---|---|---|
| 1 | 规则引擎过滤垃圾准确率>95%，误杀率<2% | 跑1000条历史案例统计 | P1 |
| 2 | BERT情感三分类(正面/中性/负面)准确率>80% | 与LLM标注结果对比50条 | P2 |
| 3 | BERT高置信度(>0.9)案例占比>40% | 跑一周数据统计分布 | P2 |
| 4 | API调用次数降幅>50% | 对比P2上线前后一周数据 | P2 |
| 5 | Forum能发现跨平台标注矛盾 | linker召回率验证+抽样对比 | P3 |
| 6 | 话题自动发现每日产出10-20个关键词 | 跑一周观察Monitor结果 | P4 |
| 7 | 日报含至少2种图表（趋势图+分布图） | 生成一份日报查看 | P5 |
| 8 | 138条现有测试+27条新测试全部通过 | `pytest tests/ -x -q` | P6 |

## Open Questions

1. **BERT模型选择**：用BettaFish同款 `wsqstar/GISchat-weibo-100k-fine-tuned-bert` 还是 `bert-base-chinese` 在我们的数据上微调？→ P2前做benchmark决定
2. **热搜API选择**：微博热搜(免费但可能不稳定) vs 百度热搜 vs 头条热榜？→ P4前测试可用性
3. **Forum主持人LLM**：用DeepSeek还是MiniMax？→ P3时根据prompt长度和成本决定
4. **BERT模型缓存策略**：每次重启加载模型 vs 常驻内存进程？→ P2 prototype时对比启动时间

## Implementation Phases

| Phase | 模块 | 改动文件 | 预计行数 | 新增测试 | 依赖 |
|---|---|---|---|---|---|
| P1 | 规则引擎 | `agents/sentinel.py` (NEW), `agents/shared.py` | ~100 | 5 | jieba |
| P2 | BERT预标注 | `agents/sentinel.py`, `agents/analyst.py`, `agents/orchestrator.py` | ~200 | 8 | torch, transformers |
| P3 | Forum交叉验证 | `agents/forum.py` (NEW), `agents/orchestrator.py`, `prompts/forum_host.txt` | ~250 | 6 | 无(基于linker.py) |
| P4 | 话题自动发现 | `agents/sentinel.py`, `agents/monitor.py` | ~150 | 4 | requests |
| P5 | ReportEngine图表 | `agents/daily_report.py` | ~200 | 4 | plotly, kaleido |
| P6 | 整合联调 | 多文件清理+文档 | ~100 | 全量回归 | 无 |

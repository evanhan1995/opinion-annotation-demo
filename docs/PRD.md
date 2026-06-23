# 舆情指挥系统 PRD (Product Requirements Document)

> 版本: v1.2 | 日期: 2026-05-23 | 状态: Updated (多模型方案 + 工作流定性)

---

## 1. 产品概述

### 1.1 产品定位

将现有"舆情标注Wiki"从**个人标注工具**升级为**6-Agent协作舆情指挥系统**，模拟真实舆情团队的组织结构，实现对舆情监测、分析、处置、报告全链路的覆盖。

### 1.2 核心指标

| 指标 | 当前 | 目标 |
|------|------|------|
| JD职责覆盖度 | ~15% | ≥70% |
| 监测模式 | 被动（人喂URL） | 主动（关键词定时搜索）+ 被动双模式 |
| 预警时效 | 无 | **P0/P1即时熔断告警（≤1min），P2/P3入日报** |
| 知识库结构 | 扁平wiki | 四体系（foundation/cases/reports/authors） |
| 处置闭环 | 无 | 标注→处置→状态同步→KB更新 |
| 报告产出 | 无 | 日报（21:00）+ 月报（1日09:00）+ P0即时告警 |
| 抓取容错 | 无降级 | Scraper失败3次→人工喂料通道 |

### 1.3 平台范围

**Phase 1-3仅支持三平台**：小红书、抖音、YouTube。

**已知局限**：微博、微信、新闻站点、论坛是国内舆情主阵地（占比>60%），当前未覆盖。这是PRD最显著的职能缺口。

**扩展路线图**：
| 优先级 | 平台 | 前置条件 | 预计Phase |
|--------|------|---------|-----------|
| P0 | 微博 | 需微博API或Playwright方案 | Phase 6 |
| P0 | 百度搜索 | 品牌词SEO追踪 | Phase 4 |
| P0 | Google搜索 | 品牌词SEO追踪 | Phase 4 |
| P1 | 微信 | 需公众号API或搜狗微信搜索 | Phase 7 |
| P2 | 新闻站点 | RSS聚合 | Phase 7 |
| P2 | Reddit/X | 已有Playwright基础，恢复即可 | Phase 6 |

### 1.4 系统定性：AI原生自动化工作流 (v1.2 新增)

**本系统本质上是一个自动化工作流（Automated Workflow），而非传统的CRUD应用或仪表盘。**

#### 定性依据

| 工作流特征 | 本系统表现 |
|-----------|-----------|
| **任务自动路由** | URL/内容自动流经 Monitor→Scraper→Analyst→Handler→Curator→Daily Report，无需人工推动 |
| **条件分支** | P0/P1 → 即时熔断告警；P2/P3 → 正常流水线；无关内容 → 反馈Monitor |
| **状态机驱动** | Handler 5状态流转（待跟进→处理中→已处理/已放弃/忽略），状态变更触发Curator同步 |
| **定时触发** | Monitor每6h巡检、日报21:00、月报1日09:00 |
| **人机协作节点** | 人工纠偏（Analyst标注后）、人工喂料（Scraper失败后）、状态更新（Handler处置后） |
| **阶段隔离** | 每个Agent只操作自己的数据域，Orchestrator是唯一跨阶段调度者 |

#### 与传统工作流的本质区别

```
传统工作流 (Zapier/n8n/Temporal):
  触发器 → 规则引擎 → 固定转换 → 下一节点
  例: "收到邮件 → 提取附件 → 存Google Drive → Slack通知"
  每个节点的行为是确定性的代码

AI原生工作流 (本系统):
  触发器 → AI推理 → 生成式输出 → 下一节点
  例: "搜索到新帖子 → LLM判断严重度+情感+标签 → LLM生成处置方案 → KB入库"
  每个节点的行为是AI推理+生成，输出具有创造性
```

**关键差异**：我们的"工作流节点"不是`if-else`或`transform()`，而是LLM Agent在执行专业判断。这使得系统能处理**非结构化输入**（任意社交媒体帖子）并产出**结构化洞察**（标注+处置方案+日报），这是传统工作流引擎做不到的。

#### 为什么不直接用n8n/Temporal？

| 维度 | n8n/Temporal | 本系统Orchestrator |
|------|-------------|-------------------|
| 节点类型 | HTTP调用/代码块/API | LLM Agent（Prompt+推理+生成） |
| 数据格式 | JSON/结构化 | 非结构化文本→结构化标注 |
| 分支逻辑 | 固定规则 | AI判断（严重度/相关性） |
| 错误处理 | 重试/降级 | 降级+人工喂料 |
| 状态持久化 | 数据库 | wiki/文件系统（Git可追踪） |

**结论**：系统的"自动化工作流骨架"可以用n8n实现，但每个节点的"智能"必须由LLM Agent提供。考虑到我们已有的Streamlit UI、Wiki KB、Agent隔离设计，自建Orchestrator比强行适配n8n更轻量。

---

## 2. 用户角色

| 角色 | 职责 | 交互方式 |
|------|------|---------|
| **舆情总监** | 查看Dashboard/日报/月报，做战略决策 | Streamlit Dashboard |
| **舆情分析师** | 提交URL分析，复核AI标注，人工纠偏 | Streamlit Tab1-2 |
| **处置负责人** | 查看P0/P1工单，更新处置状态，写处置记录 | Streamlit 处置面板 |
| **系统管理员** | 编辑关键词配置，管理Cookie，维护SOP文档 | 配置文件 + Streamlit |

---

## 3. Agent架构与风险隔离

### 3.1 隔离原则

> **核心原则：各Agent各司其职，严禁越级操作。Agent之间的数据传递必须通过Orchestrator，任何Agent不得直接调用另一个Agent的函数或访问其数据存储。**

### 3.2 权限矩阵

| 操作 | Monitor | Scraper | Analyst | Handler | Curator | Daily Report | Orchestrator |
|------|---------|---------|---------|---------|---------|-------------|--------------|
| 关键词搜索 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| URL内容抓取 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 内容标注/评分 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 相关性判定 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 生成处置方案 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 更新处置状态 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| KB条目写入 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| KB条目查询 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| 更新Case frontmatter | ❌ | ❌ | ❌ | ❌ | ✅(仅Handler触发) | ❌ | ❌ |
| 生成日报/月报 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 关键词优化建议 | ✅(建议) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 跨Agent数据传递 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅(唯一) |

### 3.3 数据隔离机制

**三层隔离**：

```
Layer 1: 代码隔离
  - 每个Agent是独立Python模块
  - 禁止跨Agent import（agents/monitor.py 不能 import agents.analyst）
  - 共享能力通过 agents/shared.py 提供（仅工具函数，无业务逻辑）

Layer 2: 数据隔离
  - Agent间通过dataclass传递数据
  - Orchestrator在传递前裁剪字段（每个Agent只收自己需要的）
  - 禁止Agent读取其他Agent的输出文件

Layer 3: Prompt隔离
  - 每个Agent的System Prompt明确声明权限边界
  - 禁止执行本角色范围外的操作
  - 例：Analyst的Prompt包含"你只负责标注，不得建议处置方案或修改知识库"
```

### 3.4 数据裁剪规则

Orchestrator在调用每个Agent前，仅传递该Agent需要的最小字段集：

```python
# 调用Analyst时，只传raw_data，不传处置状态或KB数据
analyst_input = AnalystInput(
    url=raw_data.url,
    platform=raw_data.platform,
    title=raw_data.title,
    content=raw_data.content,
    comments=raw_data.comments,
    keyword_context=keyword_info  # 仅当来自Monitor时
)
# 注意：不传 handler_state, kb_history, monitor_stats 等
```

### 3.5 唯一允许的跨Agent通信通道

只有以下通道是合法的：

```
1. Orchestrator → 任意Agent（函数调用+传参）
2. Handler → Curator（仅限 update_case_status()，由Orchestrator代理调用）
3. Analyst → Monitor（仅限 record_feedback()，由Orchestrator代理调用）
4. Curator → Analyst（仅限案例选择，通过Orchestrator在构建prompt时注入）
5. Orchestrator → Notification（P0/P1熔断时，紧急推送webhook/桌面弹窗） ← v1.1新增
```

任何Agent不得绕过Orchestrator直接通信。

**P0/P1熔断时Orchestrator的特殊权限**（v1.1新增）：
当Analyst返回P0/P1时，Orchestrator可以跳过正常流水线等待，直接调用Notification模块。这是唯一允许的"跳过Agent"的场景，因为公关黄金1小时不能等待。

---

### 3.6 P0/P1 即时熔断告警流（v1.1 新增）

> **审计修正**：原PRD P0/P1告警需等到21:00日报，违背公关黄金1小时原则。新增即时熔断分支。

```
Analyst返回标注结果
  │
  ├── severity ∈ {P0, P1}
  │   └─→ [即时熔断] 跳过正常流水线等待
  │         ├─→ Orchestrator.emergency_dispatch(annotation)
  │         │     ├─→ Handler.triage(annotation)  ← 仍然生成处置方案
  │         │     ├─→ Curator.ingest(annotation)   ← 仍然入库
  │         │     └─→ Notification.push(alert)     ← 新增：即时推送
  │         │           ├─ PowerShell弹窗 + 音效（桌面端）
  │         │           └─ Webhook（飞书/企业微信机器人，可配置）
  │         └─→ 解除熔断，继续后续流水线
  │
  └── severity ∈ {P2, P3}
      └─→ 正常流水线（等待21:00日报汇总）
```

**告警内容**：
```json
{
  "alert_type": "P0_EMERGENCY" | "P1_URGENT",
  "title": "舆情标题",
  "platform": "xhs|douyin|youtube",
  "severity": "P0",
  "risk_tags": ["隐私", "合规"],
  "url": "原始链接",
  "summary": "一句话摘要（≤50字）",
  "handler_suggestion": "处置建议（≤100字）",
  "timestamp": "2026-05-23T14:30:00+08:00"
}
```

**通知渠道配置**（`notification_config.json`）：
```json
{
  "desktop_alert": true,
  "webhooks": [
    {
      "name": "飞书舆情告警群",
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
      "enabled": true,
      "trigger_level": "P0"
    },
    {
      "name": "企业微信PR群",
      "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
      "enabled": false,
      "trigger_level": "P0+P1"
    }
  ]
}
```

---

## 4. 多模型策略 (v1.2 新增)

### 4.1 设计原则

> **每个Agent使用最适合其任务特征的模型，不强制统一Provider。模型选择是Agent能力的组成部分，与Prompt设计同等重要。**

### 4.2 模型分配矩阵

| Agent | 是否需要LLM | 推荐模型 | 选型理由 | 单次估计成本 |
|-------|-----------|---------|---------|------------|
| **Monitor** | ❌ 不需要 | — | 搜索/去重/Excel均为纯代码逻辑 | ¥0 |
| **Scraper** | ❌ 不需要 | — | 抓取/解析/Cookie均为纯代码逻辑 | ¥0 |
| **Analyst** | ✅ 核心依赖 | **DeepSeek (deepseek-chat)** | 复杂多维标注+推理链长+严格JSON输出，DeepSeek推理能力已验证（67%纠偏率） | ~¥0.02/条 |
| **Handler** | ✅ 核心依赖 | **DeepSeek (deepseek-chat)** | 结构化决策+处置方案生成，需要逻辑一致性，不能"飘" | ~¥0.01/条 |
| **Curator** | ⚡ 部分依赖 | **DeepSeek (deepseek-chat)** | 案例页面生成=模板化（低模型需求），Q&A检索=DeepSeek | ~¥0.005/条 |
| **Daily Report** | ✅ 核心依赖 | **MiniMax (abab6.5s-chat)** | 中文长文生成+格式约束+量大（日报30条/月报全量），MiniMax中文生成好且便宜 | ~¥0.01/日报 |
| **Orchestrator** | ❌ 不需要 | — | 纯调度逻辑，无LLM调用 | ¥0 |

**关键洞察**：7个Agent中只有3.5个需要LLM（Analyst/Handler/Daily Report + Curator的Q&A部分）。Monitor和Scraper是纯工程模块，它们的"智能"来自代码而非模型。

### 4.3 模型工厂设计

`agents/shared.py` 提供模型工厂，每个Agent初始化时声明自己的Provider：

```python
# agents/shared.py

from openai import OpenAI
from dataclasses import dataclass

@dataclass
class ModelConfig:
    client: OpenAI
    model: str

# 模型注册表（Provider在此统一管理）
MODEL_REGISTRY = {
    "deepseek": ModelConfig(
        client=OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", config.get("deepseek_api_key")),
            base_url="https://api.deepseek.com"
        ),
        model="deepseek-chat"
    ),
    "minimax": ModelConfig(
        client=OpenAI(
            api_key=os.environ.get("MINIMAX_API_KEY", config.get("minimax_api_key")),
            base_url="https://api.minimax.chat/v1"
        ),
        model="abab6.5s-chat"
    ),
}

def get_llm(provider: str) -> tuple[OpenAI, str]:
    """Agent调用此函数获取模型客户端。
    
    Usage:
        client, model = get_llm("deepseek")
        response = client.chat.completions.create(model=model, ...)
    """
    cfg = MODEL_REGISTRY[provider]
    return cfg.client, cfg.model
```

**各Agent初始化示例**：

```python
# agents/analyst.py
client, model = get_llm("deepseek")

# agents/daily_report.py
client, model = get_llm("minimax")

# agents/curator.py — 按场景切换
search_client, search_model = get_llm("deepseek")  # Q&A用DeepSeek
# case生成用模板，不需要LLM
```

### 4.4 多模型隔离收益

| 收益 | 说明 |
|------|------|
| **成本精准匹配** | Analyst推理贵但必要（¥0.02/条），Daily Report用便宜MiniMax（¥0.01/日报），月成本可控在¥15以内 |
| **故障隔离** | MiniMax挂了→日报暂缓，Analyst照常标注。不是全系统瘫痪 |
| **独立优化** | Analyst换Claude Opus提升准确率、Daily Report换更便宜的模型降成本，互不影响 |
| **Prompt专用** | DeepSeek和MiniMax的prompt格式偏好不同，独立模型意味着可以针对每个模型微调prompt |

### 4.5 需Spike验证

| # | 验证项 | 验证方式 |
|---|--------|---------|
| 1 | MiniMax API是否兼容OpenAI SDK格式 | 3行spike调用→检查返回结构 |
| 2 | MiniMax中文长文生成质量（日报场景） | 喂20条标注摘要→生成日报→人工评估 |
| 3 | MiniMax JSON输出稳定性（月报统计表） | 要求输出JSON格式统计→检查字段完整性 |

---

## 5. 功能需求

### 5.1 Monitor Agent（监测员）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| M-01 | 关键词配置加载 | P0 | 读取 `monitor_keywords.json`，解析为可执行任务列表 |
| M-02 | 双维度搜索 | P0 | 每个关键词×平台，分别按日期排序和热度排序搜索 |
| M-03 | 结果合并去重 | P0 | 同一关键词的两路结果按URL/ID合并去重 |
| M-04 | 增量去重 | P0 | 与上次留档对比，仅保留新增条目 |
| M-05 | Excel导出 | P0 | 产出 `outputs/monitor_YYYY-MM-DD_HHMM.xlsx` |
| M-06 | 留档存储 | P0 | 搜索结果存 `raw/monitor/YYYY-MM-DD/` |
| M-07 | 反馈接收 | P1 | 接收Analyst的无关标记，记录到关键词效果统计 |
| M-08 | 命中率统计 | P1 | 每个关键词×平台组合的信噪比追踪 |
| M-09 | 优化建议生成 | P2 | 连续3次命中率<30% → 自动生成优化建议 |
| M-10 | **品牌词SEO快照** | **P1** | **品牌关键词在百度/Google前3页搜索结果定期快照，追踪负面内容排名变化（评估SEO供应商压制效果）** |

**M-10 品牌词SEO快照说明**（v1.1 新增——对标JD 3.2 SEO供应商管理）：
- 独立于风险关键词监测，另设品牌词配置
- 搜索"品牌名"在百度/Google前30条结果，记录URL+标题+摘要+排名
- 对比上次快照 → 识别负面内容排名上升/下降 → 评估SEO压制效果
- 产出：`outputs/seo_snapshot_YYYY-MM-DD.xlsx`
- 频率：每日一次（百度+Google），低频率低成本

**隔离约束**：
- Monitor **不得**直接调用Scraper抓取详情（由Orchestrator调度）
- Monitor **不得**直接写入KB cases目录
- Monitor **不得**修改关键词配置（只读+建议，决策权在人）

### 5.2 Scraper Agent（采集员）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| S-01 | 小红书抓取 | P0 | 调用XHS-Downloader获取笔记详情+评论 |
| S-02 | 抖音抓取 | P0 | 调用TikTokDownloader获取视频详情+评论 |
| S-03 | YouTube抓取 | P0 | yt-dlp获取视频信息+评论+字幕 |
| S-04 | 标准化输出 | P0 | 所有平台输出统一 `RawData` 格式 |
| S-05 | Cookie管理 | P1 | 三级兜底（缓存→浏览器→手动） |
| S-06 | **人工喂料降级** | **P0** | **连续3次抓取失败→Streamlit弹出人工喂料框，分析师手动粘贴文本+评论，直接跳过Scraper交给Analyst** |
| S-07 | 抓取健康检查 | P1 | 每日记录各平台抓取成功率，连续<50%自动告警 |

**人工喂料降级流程**（v1.1 新增——应对反爬封禁）：
```
Scraper.fetch(url)
  ├─ 成功 → 正常流水线
  └─ 失败（连续3次）
      └─→ Orchestrator 发出 ScraperDegraded 信号
            ├─ Streamlit UI: 弹出"自动抓取失败，请手动输入"面板
            │   ├─ 输入框: 标题（必填）
            │   ├─ 文本区: 正文内容（必填）
            │   ├─ 文本区: 评论内容（选填，每行一条）
            │   └─ 按钮: "提交分析"
            └─→ 手动内容组装为 RawData → 直接交给 Analyst
```

**隔离约束**：
- Scraper **不得**做任何分析/标注（那是Analyst的工作）
- Scraper **不得**判断内容是否入库（那是Curator的工作）
- Scraper **仅**返回结构化原始数据

### 5.3 Analyst Agent（分析员）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| A-01 | 严重度评级 | P0 | P0-P3四级，含判定理由 |
| A-02 | 情感分析 | P0 | 正面/中性/负面 |
| A-03 | 风险标签 | P0 | 多标签（隐私/合规/安全/产品质量等） |
| A-04 | 分流建议 | P0 | 内部研判/上升法务/上升PR/忽略等 |
| A-05 | 评论区红绿灯 | P0 | 评论情绪风险分级 |
| A-06 | 舆情分类 | P1 | 6类色彩编码 |
| A-07 | 相关性判定 | P1 | 对Monitor批量内容判断是否与监测目标相关 |
| A-08 | 无关标记回传 | P1 | 通过Orchestrator回传Monitor |
| A-09 | 动态案例加载 | P2 | 按内容相关性选top-5案例注入prompt |
| A-10 | 流式输出 | P2 | 标注结果逐chunk生成 |

**隔离约束**：
- Analyst **不得**生成处置方案（那是Handler的工作）
- Analyst **不得**修改KB（那是Curator的工作）
- Analyst **不得**直接调用Monitor的feedback函数（通过Orchestrator）
- Analyst的System Prompt **必须包含**："你只负责分析内容。不要建议具体处置步骤、不要修改知识库、不要判断是否需要上报——这些由其他专业模块负责。"

### 5.4 Handler Agent（处置跟进）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| H-01 | 处置方案生成 | P0 | 基于标注结果生成具体行动步骤 |
| H-02 | 状态机管理 | P0 | 待跟进→处理中→已处理/已放弃/忽略 |
| H-03 | 状态同步 | P0 | 每次状态变更→自动调用Curator.update_case_status() |
| H-04 | 处置时间线 | P1 | 记录每次状态变更的时间+操作人+备注 |
| H-05 | 升级建议 | P1 | 需协调哪些部门/外部供应商 |

**处置状态流转**：
```
待跟进 ──→ 处理中 ──→ 已处理
  │          │
  └──────────┼──→ 已放弃
             │
             └──→ 忽略
```

**隔离约束**：
- Handler **不得**修改标注结果（那是Analyst的工作）
- Handler **不得**直接写KB文件（通过Curator.update_case_status()代理）
- Handler的System Prompt **必须包含**："你只负责制定处置方案和跟进状态。不要重新分析内容、不要修改标注结果、不要直接操作知识库文件。"

### 5.5 Curator Agent（保管员）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| C-01 | Case入库 | P0 | 接收标注结果→生成case-XXX.md（带四标签） |
| C-02 | 四标签维护 | P0 | 平台/严重度/处置状态/收录日期 |
| C-03 | 三维索引更新 | P0 | 平台×严重度×状态 |
| C-04 | 状态同步响应 | P0 | 接收Handler的状态更新→更新case frontmatter+索引+日志 |
| C-05 | 去重检查 | P0 | 基于URL避免重复入库 |
| C-06 | 作者库维护 | P1 | 跨平台作者聚合 |
| C-07 | 跨平台关联 | P1 | bigram Jaccard相似度检测 |
| C-08 | 知识库问答 | P1 | 基于KB的自然语言查询+引用来源 |
| C-09 | 纠偏处理 | P1 | 人工纠偏→校准案例生成→回灌 |
| C-10 | 基础内容管理 | P2 | foundation/下SOP文档的维护 |

**隔离约束**：
- Curator **不得**修改标注结果内容（只读入库）
- Curator **不得**主动修改处置状态（仅响应Handler的sync调用）
- Curator **不得**判定内容相关性（那是Analyst的工作）

### 5.6 Daily Report Agent（日报组）

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| R-01 | 日报生成 | P0 | 每日21:00自动生成，含声量/情感/议题/风险/处置统计 |
| R-02 | 月报生成 | P0 | 每月1日09:00自动生成，含趋势对比+效率统计 |
| R-03 | Monitor数据整合 | P1 | 日报含Monitor监测数据（搜索量/去重率/命中率） |
| R-04 | 处置效率统计 | P1 | 平均处理时长/处置完成率 |
| R-05 | 趋势预测 | P2 | 下月监测建议 |

**隔离约束**：
- Daily Report **不得**修改任何KB条目（只读查询）
- Daily Report **不得**修改case状态或标注结果
- Daily Report通过Curator.query_*()获取数据，不能直接读文件

---

## 6. 数据流与隔离示意

```
┌─────────────────────────────────────────────────────────────┐
│                       Orchestrator                          │
│  (唯一可跨Agent传递数据的组件)                               │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │Monitor  │  │Scraper  │  │Analyst  │  │Handler  │       │
│  │搜索+去重│→│URL→数据 │→│标注+相关│→│处置+状态│       │
│  │  R/W:   │  │  R/W:   │  │  R/W:   │  │  R/W:   │       │
│  │ raw/    │  │ raw/    │  │ (none)  │  │ (none)  │       │
│  │ monitor/│  │ cases/  │  │         │  │         │       │
│  │ outputs/│  │         │  │         │  │         │       │
│  └─────────┘  └─────────┘  └────┬────┘  └────┬────┘       │
│                                 │            │             │
│              反馈回路           │  标注结果   │  状态变更   │
│         Monitor←Analyst        ▼            ▼             │
│         (无关标记回传)    ┌─────────┐  ┌─────────┐       │
│                          │Curator  │◄─│Handler  │       │
│                          │入库+索引│  │状态同步 │       │
│                          │  R/W:   │  │         │       │
│                          │ wiki/   │  │         │       │
│                          └────┬────┘  └─────────┘       │
│                               │                          │
│                               │ 查询                     │
│                               ▼                          │
│                          ┌─────────┐                     │
│                          │Daily    │                     │
│                          │Report   │                     │
│                          │  R/W:   │                     │
│                          │ wiki/   │                     │
│                          │ reports/│                     │
│                          └─────────┘                     │
└─────────────────────────────────────────────────────────────┘

关键隔离点：
  A. Monitor → Scraper: 仅传URL列表，由Orchestrator中转
  B. Analyst → Monitor: 仅传无关标记，由Orchestrator中转
  C. Handler → Curator: 仅传状态变更，由Orchestrator代理
  D. Curator → Analyst: 仅传案例prompt，由Orchestrator构建
  E. 任何Agent不得直接import或调用另一个Agent的函数
```

---

## 7. 非功能需求

### 6.1 性能
- 单个URL端到端分析（抓取→标注→入库）≤ 60s
- Monitor单次巡检（3关键词×2平台）≤ 5min
- 日报生成 ≤ 30s
- Streamlit UI首屏加载 ≤ 3s

### 6.2 可靠性
- Agent间数据传递失败不扩散（一个Agent异常不影响其他）
- 抓取失败有降级策略（单平台失败不阻断整体流程）
- 所有对外API调用有timeout保护（默认120s）
- 所有KB写入操作有原子性保护（写临时文件→验证→rename）

### 6.3 可维护性
- 每个Agent ≤ 500行（Phase 2迁移阶段除外）
- 所有Agent遵循统一的dataclass接口规范
- 新增平台抓取只需修改Scraper Agent，其他Agent无感
- 关键词配置通过JSON文件编辑，无需改代码
- **System Prompt独立存放**：所有Agent的Prompt文本存放在 `prompts/` 目录，.py驱动文件只保留调用逻辑。公关团队可直接编辑prompt文件调优，无需改代码（v1.1 新增）
  ```
  prompts/
  ├── monitor_system.txt
  ├── scraper_system.txt      (如有LLM调用)
  ├── analyst_system.txt
  ├── handler_system.txt
  ├── curator_system.txt
  └── daily_report_system.txt
  ```

### 6.4 安全
- 知识库密码保护（保留现有三级密码源机制）
- API Key通过环境变量或config.json（gitignored）
- Cookie文件gitignored，7天过期自动清理
- Agent间数据传递仅通过Orchestrator，禁止side-channel

---

## 8. 验收标准

### Phase 1验收
- [ ] `agents/` 目录下7个Agent模块+shared.py+__init__.py全部创建
- [ ] 每个Agent有完整的dataclass接口定义
- [ ] 每个Agent有独立的System Prompt常量
- [ ] Orchestrator能走通4条流的空壳调用（返回mock数据）
- [ ] `python -m pytest tests/ -x -q` 全部通过（69旧+新接口测试）

### Phase 2验收
- [ ] 现有engine/逻辑迁移到对应Agent，69测试仍通过
- [ ] Scraper仅支持三平台（XHS/抖音/YT），Reddit和X的代码保留但标记为deprecated
- [ ] Curator支持四体系KB结构
- [ ] Handler↔Curator状态同步链路可调用

### Phase 3验收
- [ ] Monitor能加载monitor_keywords.json并执行双维度搜索
- [ ] Monitor产出Excel+留档
- [ ] **Monitor P0/P1即时熔断：Analyst返回P0/P1后1分钟内触发告警推送** ← v1.1新增
- [ ] **Scraper人工喂料降级：连续3次抓取失败→UI弹出人工输入框** ← v1.1新增
- [ ] **品牌词SEO快照：百度/Google品牌词搜索前3页结果生成Excel** ← v1.1新增
- [ ] Analyst能对批量内容做相关性判定
- [ ] Handler状态机完整（5状态×状态流转）
- [ ] Daily Report能生成日报Markdown

### Phase 4验收
- [ ] 定时调度器正常运行（日报21:00触发可验证）
- [ ] 通知推送（P0弹窗+音效+Webhook）
- [ ] **Webhook推送可配置（飞书/企业微信）** ← v1.1新增
- [ ] **Prompt文件独立于.py，公关团队可直接编辑** ← v1.1新增

### Phase 5验收
- [ ] Streamlit全Tab无widget异常
- [ ] Dashboard显示Monitor状态+告警
- [ ] Case处置页状态更新→KB同步可验证
- [ ] 日报/月报页面可查看历史

### 终期验收
- [ ] 以舆情总监JD五条职责逐项对标，覆盖度从15%提升至≥70%
- [ ] 所有Agent隔离约束可验证（通过代码审查+测试）

---

## 9. 附录

代码审查时逐项检查：

```
□ Monitor是否import了analyst/handler/curator? → 违规
□ Scraper是否做了严重度评级? → 违规
□ Analyst的prompt是否包含处置建议? → 违规
□ Handler是否直接写wiki/cases/文件? → 违规
□ Curator是否主动修改case的处置状态? → 违规
□ Daily Report是否直接读raw/monitor/文件? → 违规（应通过Curator.query()）
□ 任一Agent是否import了另一个Agent的模块? → 违规
□ Orchestrator是否传递了超出Agent需要的字段? → 待优化
```

---

## 10. 修订记录

| 版本 | 日期 | 变更 | 触发 |
|------|------|------|------|
| v1.0 | 2026-05-23 | 初稿 | 初始PRD |
| v1.1 | 2026-05-23 | 新增P0/P1即时熔断告警流、人工喂料降级、品牌词SEO快照、Prompt独立存放、平台扩展路线图 | 第三方审计（三条硬伤） |
| v1.2 | 2026-05-23 | 新增多模型策略（§4）、系统定性为AI原生自动化工作流（§1.4）、模型分配矩阵+工厂设计 | 技术评审 |

### v1.1 具体修订项

| # | 审计发现 | 修订措施 | 影响章节 |
|---|---------|---------|---------|
| 1 | P0/P1告警等到21:00日报，违背公关黄金1小时 | 新增3.6节P0/P1即时熔断流，Orchestrator在Analyst返回P0/P1后1分钟内推送告警（弹窗+Webhook） | 1.2, 3.5, 3.6, 7 |
| 2 | XHS/抖音反爬封禁风险，Scraper失败=全系统瘫痪 | 新增S-06人工喂料降级通道：3次抓取失败→Streamlit弹出人工输入框，跳过Scraper直接给Analyst | 4.2, 7 |
| 3 | 缺失SEO能见度追踪，无法评估供应商压制效果 | 新增M-10品牌词SEO快照：百度/Google品牌词前3页定期快照+排名变化对比 | 4.1, 7 |
| 4 | Prompt硬编码在.py中，公关团队无法调优 | 新增6.3节prompts/目录规范，Prompt独立存放 | 6.3, 7 |
| 5 | 平台覆盖缺口（微博/微信缺失） | 新增1.3节平台扩展路线图，标注已知局限 | 1.3 |
| — | Agent隔离设计 | 无需修改，审计评为"极其优秀" | 3 |

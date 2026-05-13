---
title: 舆情标注案例库索引
type: index
created: 2026-05-11
updated: 2026-05-13
confidence: high
tags: [yq, case, 索引]
---

# 舆情标注案例库

> 案例库是标注规范的**迭代引擎**。每新增一个案例，AI 会自动检查现有标注边界是否需要调整。
> 按严重度、分流建议、风险标签、平台多维度索引。

---

## 案例总览

| 编号 | 标题 | 严重度 | 分流建议 | 平台 | 关键维度 |
|------|------|--------|---------|------|---------|
| [[cases/case-001|001]] | 安全事故指控+P0立即响应 | P0 | 立即处理 | X | 安全、KOL、大规模传播 |
| [[cases/case-002|002]] | 产品质量讨论+P2持续观察 | P2 | 持续观察 | Reddit | 质量、真实用户 |
| [[cases/case-003|003]] | 物流吐槽无传播+P3可忽略 | P3 | 可忽略 | X | 物流、低影响力 |
| [[cases/case-004|004]] | 正面KOL推荐+可利用 | P3 | 正面可利用 | TikTok | 正面、KOL、UGC |
| [[cases/case-005|005]] | 竞品对比公正评测+观察 | P3 | 持续观察 | YouTube | 竞品、混合情感、大V |
| [[cases/case-006|006]] | 疑似水军攻击+P3可忽略 | P3 | 可忽略 | X | 虚假信号、竞品攻击 |
| [[cases/case-007|007]] | 小红书用户分享DJI Pocket 4使用体验，肯定夜景和色彩，但吐槽自拍效果差 | P2 | 立即处理 | — | 纠偏案例 | 2026-05-11 |
| [[cases/case-008|008]] | 1160万粉YouTuber发布shorts视频，标题'Is Temu A Sc | P2 | 持续观察 | ? | KOL负面 |
| [[cases/case-009|009]] | 6.24万粉手工艺YouTuber指控TEMU盗用其钩针设计，获3649赞，评论 | P2 | 持续观察 | ? | 合规, KOL负面 |
| [[cases/case-010|010]] | Reddit用户发现Temu夜间后台频繁获取位置(4h/47次)，质疑GDPR/CCPA | P1 | 持续观察 | Reddit | 数据隐私, 合规, 法律风险 |
| [[cases/case-011|011]] | 小红书用户投诉大疆产品质量差，刚买几天就坏，寄回后商家私自换新不给退款，提及12 | P2 | 持续观察 | ? | 质量, 客服 |
| [[cases/case-012|012]] | 小红书用户(自称电子工程师)投诉DJI Neo 2在16米高空因电池缺陷断电坠毁 | P1 | 立即处理 | 小红书 | 安全, 质量, 客服 |
| [[cases/case-013|013]] | 1.97万粉科技频道测试DJI OSMO NANO最新固件对过热问题的修复效果， | P2 | 持续观察 | YouTube | 质量, KOL负面 |

---

## 按维度索引

### 按严重度
| 严重度 | 案例 |
|--------|------|
| P0 | [[cases/case-001|001]] |
| P1 | [[cases/case-010|010]], [[cases/case-012|012]] |
| P2 | [[cases/case-002|002]], [[cases/case-007|007]], [[cases/case-008|008]], [[cases/case-009|009]], [[cases/case-011|011]], [[cases/case-013|013]] |
| P3 | [[cases/case-003|003]], [[cases/case-004|004]], [[cases/case-005|005]], [[cases/case-006|006]] |

### 按分流建议
| 建议 | 案例 |
|------|------|
| 立即处理 | [[cases/case-001|001]], [[cases/case-007|007]], [[cases/case-012|012]] |
| 持续观察 | [[cases/case-002|002]], [[cases/case-005|005]], [[cases/case-008|008]], [[cases/case-009|009]], [[cases/case-010|010]], [[cases/case-011|011]], [[cases/case-013|013]] |
| 可忽略 | [[cases/case-003|003]], [[cases/case-006|006]] |
| 正面可利用 | [[cases/case-004|004]] |

### 按平台
| 平台 | 案例 |
|------|------|
| X (Twitter) | [[cases/case-001|001]], [[cases/case-003|003]], [[cases/case-006|006]] |
| Reddit | [[cases/case-002|002]], [[cases/case-010|010]] |
| TikTok | [[cases/case-004|004]] |
| 小红书 | [[cases/case-007|007]], [[cases/case-011|011]], [[cases/case-012|012]] |
| YouTube | [[cases/case-005|005]], [[cases/case-008|008]], [[cases/case-009|009]], [[cases/case-013|013]] |

---

## 覆盖度分析

| 维度 | 已覆盖 | 缺失 |
|------|--------|------|
| 严重度 | P0, P1, P2, P3 | — |
| 平台 | X, Reddit, TikTok, YouTube | Instagram, 新闻媒体, 论坛 |
| 内容类型 | 新闻、问答、投诉、视频、社媒帖子 | 产品评价（纯文本） |
| 情感 | 负面、正面、混合 | — |
| 真实性 | 真实、存疑、虚假 | — |

> **迭代提示**：优先添加 **P1 边界案例**（中危内容+高影响力，或高危内容+低影响力），这是当前案例库最大的覆盖盲区。

---

## 案例格式规范

```yaml
---
title: 案例XXX：一句话标题
type: case
created: YYYY-MM-DD
severity: P0 | P1 | P2 | P3
action: 立即处理 | 持续观察 | 可忽略 | 正面可利用
platform: 平台名称
tags: [标签]
related_concepts:
  - "[[concepts/xxx]]"
related_cases:
  - "[[cases/case-xxx]]"
---

## 原始输入
## 标注输出
## 判据链
## 边界讨论
## 对标注规范的影响
```

---

## 迭代机制

1. **新增案例**：用户投放原始舆情到 `raw/cases/` → AI 执行 ingest → 创建 case 页面
2. **边界检查**：判断该案例是否触及现有决策规则的模糊地带
3. **规范更新**：如需调整规则，更新对应 concept 页面和 [[syntheses/opinion-annotation-spec|标注规范]]
4. **日志记录**：所有变更写入 [[log.md|操作日志]]
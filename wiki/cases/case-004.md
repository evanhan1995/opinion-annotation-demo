---
title: 案例004：正面KOL强力推荐 + 非赞助声明 → 正面可利用
type: case
created: 2026-05-11
severity: P3
action: 正面可利用
platform: TikTok
tags: [正面, KOL, UGC, DJI, 潜在合作]
related_concepts:
  - "[[concepts/sentiment-analysis-dimensions|多维度情感分析]]"
  - "[[concepts/public-opinion-triaging|舆情分流判断]]"
related_cases:
  - "[[cases/case-005|005-竞品对比]]"
---

## 原始输入

```
平台：TikTok
发布者：摄影爱好者，粉丝5.2万
内容："ok I finally understand the DJI Pocket 3 hype. Shot my entire Japan trip on this tiny thing 
and the footage is INSANE. The low light performance?? The gimbal?? 
If you're on the fence just get it. Not sponsored btw just genuinely impressed 
#djipocket3 #travelcamera #japan"
互动：点赞4.8万，评论1200，收藏8900
发布时间：5天前
```

## 标注输出

```json
{
  "内容分类": "视频/短视频",
  "情感分析": {
    "整体情感": "正面",
    "品牌维度": {"情感": "正面", "关键短语": "genuinely impressed"},
    "产品维度": [{"产品名称": "DJI Pocket 3", "情感": "正面", "关键短语": "INSANE footage, low light performance, just get it"}],
    "竞品维度": {"是否提及竞品": "否"}
  },
  "严重度评级": "P3",
  "严重度理由": "正面内容，无风险",
  "分流建议": "正面可利用",
  "分流理由": "5.2万粉中型KOL+高互动(4.8万赞/8900收藏)+主动声明非赞助(增加公信力)+具体使用场景→优质UGC，建议PR侧评估合作或转发授权",
  "真实性评估": {
    "判断": "大概率真实",
    "信号": ["具体使用场景(日本旅行)", "多维度产品评价", "主动声明非赞助", "账号为摄影垂类"]
  },
  "摘要": "5.2万粉摄影KOL在TikTok强烈推荐DJI Pocket 3，展示日本旅拍效果，获4.8万赞，主动声明非赞助",
  "风险标签": [],
  "置信度": {"分类置信度": "高", "情感置信度": "高", "整体置信度": "高"}
}
```

## 判据链

1. **情感**：全部维度为正面
2. **严重度 = P3**：正面内容无风险
3. **分流建议**：KOL粉丝≥1万 + 互动≥1万 + 正面 + 非赞助声明 → 触发"正面可利用"

## 边界讨论

**"正面可利用"的分层标准**：
- **高价值（建议优先联系）**：粉丝≥10万 + 互动≥5万 + 非赞助声明 + 垂类匹配
- **中价值（建议观察储备）**：粉丝1-10万 + 互动≥5000 + 正面质量高 ← 本案例
- **低价值（仅归档）**：粉丝<1万 或 互动<5000

**"非赞助声明"为何是加分项**：增加内容公信力 → 如合作，粉丝信任度损失较小。

## 对标注规范的影响

- 细化"正面可利用"分层标准
- "非赞助声明"纳为正向信号
- "收藏数"纳为互动指标（TikTok 平台，收藏=行动意图）

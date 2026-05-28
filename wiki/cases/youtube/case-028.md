---
title: 案例028: YouTube博主Lindey 2.0发布15分钟反应视频，展示Temu购物失败案例，播放量超108万，评论区出现呼吁诉
type: case
created: 2026-05-28
severity: P3
action: 立即处理
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=8p9SCscUqnM
categories: [商品问题, 其他]
author: "[[authors/author-lindey-2-0.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Lindey 2.0
互动数据：点赞28579, 播放1085027
时间：2025-06-27
链接：https://www.youtube.com/watch?v=8p9SCscUqnM

原文内容：
标题：They Ordered from Temu and Were SHOCKED by What Arrived

描述：Think shopping on Temu is a good deal? Think again! In this video, I react to some of the craziest Temu fails and worst shopping disasters shared on social media. From shocking unboxings to hilarious product fails, you won’t believe what people actually received after ordering from Temu! Watch until the end to see the most unbelievable Temu regret stories, and let me know if you’ve ever had a Temu fail of your own. Don’t forget to like, comment, and subscribe for more wild online shopping reactions and scam alerts!

#TemuFails #OnlineShoppingFail #ReactionVideo

时长：15分5秒
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "视频播放量超100万，点赞近3万，属于高影响力传播；内容聚焦商品质量问题和购物体验负面，虽未涉及安全红线，但大规模传播可能损害品牌声誉，且评论区出现呼吁诉讼和联系监管机构的言论，需密切关注",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "大规模传播",
    "KOL负面"
  ],
  "分流建议": "立即处理",
  "评论区分析": {
    "评论红绿灯": {
      "红": 1,
      "黄": 0,
      "绿": 0
    }
  },
  "舆情分类": [
    "商品问题",
    "其他"
  ],
  "摘要": "YouTube博主Lindey 2.0发布15分钟反应视频，展示Temu购物失败案例，播放量超108万，评论区出现呼吁诉讼和联系监管机构的极端言论"
}
```

## 判据链

- **严重度判决**：视频播放量超100万，点赞近3万，属于高影响力传播；内容聚焦商品质量问题和购物体验负面，虽未涉及安全红线，但大规模传播可能损害品牌声誉，且评论区出现呼吁诉讼和联系监管机构的言论，需密切关注
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, 大规模传播, KOL负面

## 边界讨论

- **异常组合**：严重度「P3」+ 分流建议「立即处理」的组合在现有案例中不常见，值得关注。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

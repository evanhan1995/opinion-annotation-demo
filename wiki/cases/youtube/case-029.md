---
title: 案例029: YouTube频道Unbox Analysis发布Temu 2025年畅销品推荐视频，包含多个商品链接和折扣码，评论区有
type: case
created: 2026-05-28
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=AzQ5D83UNPA
categories: [商品问题, 其他]
author: "[[authors/author-unbox-analysis.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Unbox Analysis
互动数据：点赞1507, 播放139910
时间：2025-09-06
链接：https://www.youtube.com/watch?v=AzQ5D83UNPA

原文内容：
标题：Temu's Most Sold of 2025

描述：Tactical Hiking Boots | $ | https://temu.to/k/pdoiho70aet
Chest Pack | $ | https://temu.to/k/pw65r9w6idp
Folding Red Dot Sight | $25.09 | https://temu.to/k/po4fm5h79pi
Smart Glasses (not smart) | $29.90 | Discontinued
6 Place Hard Case | $64.62 | https://temu.to/k/px2h3w6odvx
Tactical Flashlight | $22.53 |  https://temu.to/k/psj2tih9itm
Dual-Head Light | $9.69 | https://temu.to/k/pkalbb1g086
Better Chest Bag | $13.35 | https://temu.to/k/prp15lcf0xn
LED Magnetic Light | $5.66 | https://temu.to/k/podg3ycbgwm

https://www.temu.com/k/cd5be1b9 (Exclusive Link w/ Discounts)
Code: fav37971

Disclaimer: Some links may be affiliate links. If you purchase through them, I may earn a small commission at no extra cost to you.
#temu #temufinds #temufinds #temuunboxing 
 

```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "中危内容（产品功能缺陷/质量问题的详细描述，评论区有具体负面体验） × 中影响力（播放量13.9万，点赞1507） = P2",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量"
  ],
  "分流建议": "持续观察",
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
  "摘要": "YouTube频道Unbox Analysis发布Temu 2025年畅销品推荐视频，包含多个商品链接和折扣码，评论区有用户反馈靴子质量差导致脚痛，智能眼镜被标注'not smart'。"
}
```

## 判据链

- **严重度判决**：中危内容（产品功能缺陷/质量问题的详细描述，评论区有具体负面体验） × 中影响力（播放量13.9万，点赞1507） = P2
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

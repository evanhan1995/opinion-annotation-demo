---
title: 案例045: KOL Drew Dirksen发布17分钟视频，标题称Temu产品为'最懒的'，展示9款产品并附购买链接，播放量323
type: case
created: 2026-05-28
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=Ti14pPDmZA4
categories: [商品问题, 其他]
author: "[[authors/author-drew-dirksen.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Drew Dirksen
互动数据：点赞21018, 播放3233156
时间：2025-05-11
链接：https://www.youtube.com/watch?v=Ti14pPDmZA4

原文内容：
标题：I Tested the Laziest Temu Products!

描述：Download Temu App now, and search code【dwy9628】to claim $100 Coupon Bundle!
👉 https://app.temu.com/k/uvzhgbcb7c6

My Temu Picks:
Multifunctional Scooter Luggage, 2in 1 Riderable Suitcase, Thickened Aluminum Alloy Tie Rod, Foldable Skateboard, Foot Brake, Non-slip Deck, Blue, yumingliao $154.35💰
https://temu.to/k/u36e8m991ih
1pair Non-electric Version Extreme Outdoor Sports Wind And Fire Wheel, PU Wheel, Double Wheel Foot Pedal Skateboard, Solid Wheel, Adult Scooter, Outdoor Two-wheel Roller Skate Shoes Christmas Halloween Gift $107.20💰
https://temu.to/k/us35oahx9yu
1pc Portable Automatic Electric Nail Clipper And Filer With LED Light, Compact Nail Trimmer Grinder For Home Use, Grooming Tool, Christmas And Thanksgiving Gifts $10.70💰
https://temu.to
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "标题使用'Laziest'（最懒的）对Temu产品进行整体负面定性，播放量323万、点赞2.1万，属于中危内容×高影响力，但内容为娱乐性评测，无安全或合规红线，且评论区未出现对产品的实质批评，故评为P2",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "KOL负面",
    "大规模传播"
  ],
  "分流建议": "持续观察",
  "评论区分析": {
    "评论红绿灯": {
      "红": 0,
      "黄": 1,
      "绿": 0
    }
  },
  "舆情分类": [
    "商品问题",
    "其他"
  ],
  "摘要": "KOL Drew Dirksen发布17分钟视频，标题称Temu产品为'最懒的'，展示9款产品并附购买链接，播放量323万，评论区主要讨论饮料名称（soda/pop），未出现对产品的实质批评"
}
```

## 判据链

- **严重度判决**：标题使用'Laziest'（最懒的）对Temu产品进行整体负面定性，播放量323万、点赞2.1万，属于中危内容×高影响力，但内容为娱乐性评测，无安全或合规红线，且评论区未出现对产品的实质批评，故评为P2
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：KOL负面, 大规模传播

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

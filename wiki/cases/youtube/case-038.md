---
title: 案例038: KOL分享TEMU购物开箱，展示多款商品，评论区出现质量质疑（廉价、材质不符）和负面体验，整体情感混合
type: case
created: 2026-05-28
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=dLCoKehkR6U
categories: [商品问题, 其他]
author: "[[authors/author-aimee-michelle.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Aimee Michelle
互动数据：点赞3220, 播放41767
时间：2026-05-21
链接：https://www.youtube.com/watch?v=dLCoKehkR6U

原文内容：
标题：TRENDING from TEMU! | Blue & White Summer, Designer, Fashion & More | WHAT I ORDERED VS WHAT I GOT

描述：Download Temu App：https://app.temu.com/k/esbvmt4sf44 shop my piscks and to get ￡100 in Coupons FOR FREE
🔍Or search my code【kne6867】on Temu App to claim

Shop my picks：
Miu Miu Hairpins - https://temu.to/k/ewh4o94jq0m
YS Heels - https://temu.to/k/e54t8s8u8dn
Coach Sholder Bag - https://temu.to/k/ewa5qw3x4tp
Two-Piece Set with Floral Off-Shoulder Top - https://temu.to/k/efltzyrum6u
Blue & White Ruffle Dress - https://temu.to/k/eyq0e6xmtgq
Men's Blue & White Linen Shirt - https://temu.to/k/eo5mquktra2
Blue & White Flower Enamel Earrings - https://temu.to/k/e6jotdkyyoo
Blue & White China Earrings - https://temu.to/k/ew3ywmyxg2d
Blue & White Glazed Bracelet - https://temu.to/k/e1q7222oqfy
S
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "视频本身为购物分享，情感混合，但评论区出现商品质量质疑（如廉价、材质不符）和负面体验，互动量中等，未大规模爆发",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "KOL负面"
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
  "摘要": "KOL分享TEMU购物开箱，展示多款商品，评论区出现质量质疑（廉价、材质不符）和负面体验，整体情感混合"
}
```

## 判据链

- **严重度判决**：视频本身为购物分享，情感混合，但评论区出现商品质量质疑（如廉价、材质不符）和负面体验，互动量中等，未大规模爆发
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, KOL负面

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

---
title: 案例021: YouTube博主Aimee Michelle发布TEMU开箱视频，展示多品类商品，评论区出现商品侵权讨论和部分质量反馈
type: case
created: 2026-05-27
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=TXEGhdOzzqI
categories: [商品侵权问题, 其他]
author: "[[authors/author-aimee-michelle.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Aimee Michelle
互动数据：点赞3066, 播放48038
时间：2026-05-12
链接：https://www.youtube.com/watch?v=TXEGhdOzzqI

原文内容：
标题：TEMU Spring Finds! Designer, Homewear, Jewellery & more! | TEMU WHAT I ORDERED VS WHAT I GOT UK

描述：Download Temu App：https://app.temu.com/k/efgl3ngfiz0 shop my piscks and to get ￡100 in Coupons FOR FREE
🔍Or search my code【kmm6867】on Temu App to claim

Shop my picks：
LV Belt - https://temu.to/k/e43154jw6r7
Mui Mui Inspired Jeans - https://temu.to/k/e8xn91cgsjx
CC Belt - https://temu.to/k/ens12ih7d3r
Natural Marble Round Storage Container with Lid - https://temu.to/k/e14rjxcqq3j
Chain-style Golden Hoop Earrings - https://temu.to/k/esrjtvgg5io
Moving Honeycomb Paper for Shipping - https://temu.to/k/elavbecld1b
Black Pannel Jacket - https://temu.to/k/eevh76wj77p
Heated Massage Pillow - https://temu.to/k/e7qlz8q567l
6pcs Reusable Silicone Nipple Covers - https://temu.to/k/eifajmezdih
3pcs, 
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "视频本身为中性开箱，但评论区出现商品侵权讨论（'Temu and shein have been in court over copy rights'）及商品质量问题（'bras hit and miss'），属于中危内容×低影响力（播放4.8万，互动3066，未爆发）",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "合规"
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
    "商品侵权问题",
    "其他"
  ],
  "摘要": "YouTube博主Aimee Michelle发布TEMU开箱视频，展示多品类商品，评论区出现商品侵权讨论和部分质量反馈，整体中性。"
}
```

## 判据链

- **严重度判决**：视频本身为中性开箱，但评论区出现商品侵权讨论（'Temu and shein have been in court over copy rights'）及商品质量问题（'bras hit and miss'），属于中危内容×低影响力（播放4.8万，互动3066，未爆发）
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, 合规

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

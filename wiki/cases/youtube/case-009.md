---
title: 案例009: KOL John Malecki发布58分钟视频，标题称Temu商品为'SCAM'，播放量超105万，点赞2.6万，内容
type: case
created: 2026-05-27
severity: P3
action: 立即处理
platform: YouTube
source: auto_ingest
status: 处理中
url: https://www.youtube.com/watch?v=RhFmNY43W0c
categories: [商品问题, 其他]
author: "[[authors/author-john-malecki-unscrewed.md]]"
notes: 自动化处置
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：John Malecki Unscrewed
互动数据：点赞26118, 播放1058970
时间：2026-04-26
链接：https://www.youtube.com/watch?v=RhFmNY43W0c

原文内容：
标题：I Bought SCAM Temu Products

描述：I Bought SCAM Temu Products
Enter for a chance to win 791 Tool Mod Box! - https://johnmalecki.com/pages/tool-box-giveaway

Sub to The Podcast! - https://bit.ly/SAAPodcast

Check out the new Smoke Grey Color Shop Shades and our new Protector frames! - https://bit.ly/ShopShades_Unscrewed

WANT MORE VIDEOS???
Join THE BUILDER BUNKER - http://link.johnmalecki.com/Bunker_Subscribe
- Become part of our exclusive online community of people just like you who love tools and building and being awesome! Get access to behind the scenes videos, building tips, cooking, booze reviews, and more!

Check Out Muckender Cleaning Towels! https://www.muckenders.com/discount/johnbuilds?redirect=%2Fcollections%2Fall-products Discount Code: johnbuilds

Check out the Creator Playb
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "KOL(粉丝量>100万)发布负面视频，标题含'SCAM'指控，播放量超100万，属于高影响力中危内容，但内容为个人评测性质，未涉及安全或法律红线，按矩阵中危×高影响力=P1",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "KOL负面",
    "大规模传播",
    "质量"
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
  "摘要": "KOL John Malecki发布58分钟视频，标题称Temu商品为'SCAM'，播放量超105万，点赞2.6万，内容为产品评测但标题具有攻击性，需关注传播风险"
}
```

## 判据链

- **严重度判决**：KOL(粉丝量>100万)发布负面视频，标题含'SCAM'指控，播放量超100万，属于高影响力中危内容，但内容为个人评测性质，未涉及安全或法律红线，按矩阵中危×高影响力=P1
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：KOL负面, 大规模传播, 质量

## 边界讨论

- **异常组合**：严重度「P3」+ 分流建议「立即处理」的组合在现有案例中不常见，值得关注。

## 处置备注

自动化处置

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

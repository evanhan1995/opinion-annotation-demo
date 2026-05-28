---
title: 案例032: DankPods发布1小时视频，标题称Temu/Aliexpress商品为'Trash'，播放量超107万，点赞近4万，
type: case
created: 2026-05-28
severity: P3
action: 立即处理
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=0i6fN8Seq8Y
categories: [商品问题]
author: "[[authors/author-dankpods.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：DankPods
互动数据：点赞38982, 播放1074946
时间：2025-12-15
链接：https://www.youtube.com/watch?v=0i6fN8Seq8Y

原文内容：
标题：The Temu / Aliexpress Trash Xmas Special

描述：Thanks Floaties!! https://www.floatplane.com/channel/TheTrashNetwork/home

时长：1时0分38秒
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "KOL(粉丝量级>100万)发布负面视频，播放量超100万，点赞近4万，属于高影响力中危内容，且标题直接贬低Temu商品为'Trash'，可能引发大规模传播，但未涉及安全/法律红线，故评为P1",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "KOL负面",
    "大规模传播"
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
    "商品问题"
  ],
  "摘要": "DankPods发布1小时视频，标题称Temu/Aliexpress商品为'Trash'，播放量超107万，点赞近4万，内容为拆解吐槽低价商品质量，评论区有共鸣和补充讨论"
}
```

## 判据链

- **严重度判决**：KOL(粉丝量级>100万)发布负面视频，播放量超100万，点赞近4万，属于高影响力中危内容，且标题直接贬低Temu商品为'Trash'，可能引发大规模传播，但未涉及安全/法律红线，故评为P1
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, KOL负面, 大规模传播

## 边界讨论

- **异常组合**：严重度「P3」+ 分流建议「立即处理」的组合在现有案例中不常见，值得关注。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

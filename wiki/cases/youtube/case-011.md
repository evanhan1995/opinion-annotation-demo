---
title: 案例011: TFG Vlogs发布视频称从Temu购买1000美元商品为'垃圾'，播放284万，评论区有正面体验和质疑，整体情绪化指
type: case
created: 2026-05-27
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=wiafcoYeDLI
categories: [商品问题, 其他]
author: "[[authors/author-tfg-vlogs.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：TFG Vlogs
互动数据：点赞28284, 播放2844106
时间：2023-08-13
链接：https://www.youtube.com/watch?v=wiafcoYeDLI

原文内容：
标题：I Bought $1,000 of Junk from Temu!

描述：I Bought $1000 of Junk from Temu | TFG Vlogs is back and today I will show you my Temu Haul 2023. I have always wondered is temu legit, today we find out! There will be a new tfg vlog every Sunday so stay tuned! 
#temu #tfgvlogs #tfg 

► Making $0.01 For Every Step I Take! https://youtu.be/GOl90WKhbJ0 

► Follow me on Instagram! https://www.instagram.com/tfgvlogs

时长：9分34秒
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "中危内容（商品质量问题指控）但影响力中等（播放284万，点赞2.8万，但标题含'Junk'情绪化，缺乏具体证据），传播态势稳定，未出现加速传播或变体",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "KOL负面",
    "大规模传播"
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
  "摘要": "TFG Vlogs发布视频称从Temu购买1000美元商品为'垃圾'，播放284万，评论区有正面体验和质疑，整体情绪化指控但缺乏具体证据"
}
```

## 判据链

- **严重度判决**：中危内容（商品质量问题指控）但影响力中等（播放284万，点赞2.8万，但标题含'Junk'情绪化，缺乏具体证据），传播态势稳定，未出现加速传播或变体
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, KOL负面, 大规模传播

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

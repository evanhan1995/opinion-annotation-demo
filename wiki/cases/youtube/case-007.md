---
title: 案例007: YouTube大频道发布娱乐挑战视频，标题提及从Temu购买房屋，但内容为家庭娱乐，未涉及商品评价或负面舆情
type: case
created: 2026-05-27
severity: P3
action: 可忽略
platform: YouTube
source: auto_ingest
status: 处理中
url: https://www.youtube.com/watch?v=I-QRt_qagNk
categories: [其他]
author: "[[authors/author-the-royalty-family.md]]"
notes: 自动化处置
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：The Royalty Family
互动数据：点赞138429, 播放20007113
时间：2025-06-22
链接：https://www.youtube.com/watch?v=I-QRt_qagNk

原文内容：
标题：I Bought a REAL House off Temu

描述：I Bought a REAL House off Temu
SUBSCRIBE HERE 👉 ​⁠@royaltyfam 
SUBSCRIBE To Gaming Channel 👉 ​⁠ ​⁠@RoyaltyGaming1 
 
More AMAZING Videos! 👇

Our Son's EPIC 14th Birthday Surprise
👉 https://youtu.be/XuNqMOGENZk

Eating Only GAS STATION FOOD for 24 Hours!! 🤮
👉 https://youtu.be/UtcJZnyFTQE

i Survived the World's STRICTEST Babysitter
👉 https://youtu.be/oC2o2-Nteyw?si=QA8BqYP16RCloMUz

First Class Dream Vacation!
👉https://youtu.be/pE09zW0m0Kk

HOME ALONE Without Parents for 24 Hours *Security Cameras*
👉 https://youtu.be/T6IuTOAYS8k?si=iG5BjzALXi0uACvl

Our Son's EPIC 13th BIRTHDAY SURPRISE!
👉 https://youtu.be/ppAIBR_BxO4

He Finally Got His DREAM Christmas PRESENT!! **EMOTIONAL**
👉 https://youtu.be/Ot17zf95YNA?si=SSjqvSYrj8qqMmIg

Father Tries to Find his 
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "内容为娱乐挑战视频，标题提及Temu但实际未涉及商品问题或负面评价，无实质风险",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [],
  "分流建议": "可忽略",
  "评论区分析": {
    "评论红绿灯": {
      "红": 1,
      "黄": 0,
      "绿": 0
    }
  },
  "舆情分类": [
    "其他"
  ],
  "摘要": "YouTube大频道发布娱乐挑战视频，标题提及从Temu购买房屋，但内容为家庭娱乐，未涉及商品评价或负面舆情"
}
```

## 判据链

- **严重度判决**：内容为娱乐挑战视频，标题提及Temu但实际未涉及商品问题或负面评价，无实质风险
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：(无)

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

自动化处置

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

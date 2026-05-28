---
title: 案例037: YouTube博主测试Temu厨房小工具，产品表现尚可，但评论区出现品牌负面指控（劳动实践、污染、版权），传播量低。
type: case
created: 2026-05-28
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=S-AfbIxO50c
categories: [商品问题, 其他]
author: "[[authors/author-scubeskitchen.md]]"
notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Scubeskitchen
互动数据：点赞712, 播放10506
时间：2026-05-23
链接：https://www.youtube.com/watch?v=S-AfbIxO50c

原文内容：
标题：I Tested Temu’s Highest Rated Kitchen Gadgets... Worth It?

描述：I bought the 6 highest-rated kitchen gadgets I could find on Temu and put them to the test. Are the reviews actually right, or did I just waste my money?

Comment which gadget you'd actually try!

时长：10分15秒
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "中危内容（商品质量讨论+品牌负面指控）×低影响力（播放1万，点赞712，无加速传播）→P2",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "合规",
    "竞品攻击"
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
  "摘要": "YouTube博主测试Temu厨房小工具，产品表现尚可，但评论区出现品牌负面指控（劳动实践、污染、版权），传播量低。"
}
```

## 判据链

- **严重度判决**：中危内容（商品质量讨论+品牌负面指控）×低影响力（播放1万，点赞712，无加速传播）→P2
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, 合规, 竞品攻击

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

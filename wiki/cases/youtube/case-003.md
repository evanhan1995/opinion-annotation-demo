---
title: 案例003: KOL Westen Champlin发布22分钟视频，购买Temu喷气艇进行测试，标题暗示不推荐购买，播放123万+，
type: case
created: 2026-05-27
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 处理中
url: https://www.youtube.com/watch?v=d32XbRnxWcc
categories: [商品问题, 其他]
author: "[[authors/author-westen-champlin.md]]"
notes: 自动化处置
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Westen Champlin
互动数据：点赞44305, 播放1233577
时间：2026-05-23
链接：https://www.youtube.com/watch?v=d32XbRnxWcc

原文内容：
标题：We Bought Temu Jet Boats So You Dont Have To

描述：Try Rocket Money for FREE or unlock more features with premium at: https://RocketMoney.com/Westen
Win this Ford Raptor R + $10,000! https://westengw.com/

No Purchase Required. See Rules at https://westengw.com/pages/official-rules Ends 11:59 p.m. ET, June 14, 2026

Get your Redneck Science Clothing ► https://westengw.com/
Snapchat: https://www.snapchat.com/@westengw  
Instagram: https://www.instagram.com/westengw  
Facebook: https://www.facebook.com/westengw  
2nd Channel: https://www.youtube.com/@UC2lMYhsLABAsJwsjxg0-P_w

时长：22分13秒
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "中危内容（产品功能缺陷/质量问题详细描述） × 高影响力（播放123万+点赞4.4万+KOL粉丝量级大） = P2（中危×高影响力本应为P1，但内容为娱乐性评测，非恶意攻击，且评论区整体中性偏正面，故降为P2）",
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
      "红": 0,
      "黄": 1,
      "绿": 0
    }
  },
  "舆情分类": [
    "商品问题",
    "其他"
  ],
  "摘要": "KOL Westen Champlin发布22分钟视频，购买Temu喷气艇进行测试，标题暗示不推荐购买，播放123万+，评论区整体娱乐性为主，无严重负面指控。"
}
```

## 判据链

- **严重度判决**：中危内容（产品功能缺陷/质量问题详细描述） × 高影响力（播放123万+点赞4.4万+KOL粉丝量级大） = P2（中危×高影响力本应为P1，但内容为娱乐性评测，非恶意攻击，且评论区整体中性偏正面，故降为P2）
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, KOL负面

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

自动化处置

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

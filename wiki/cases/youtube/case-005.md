---
title: 案例005: YouTube娱乐视频合集展示TEMU购物失败案例，包括商品尺寸不符、侵权仿冒、有毒材料等指控，播放17.5万，评论区部
type: case
created: 2026-05-27
severity: P3
action: 持续观察
platform: YouTube
source: auto_ingest
status: 处理中
url: https://www.youtube.com/watch?v=d_hdZhCflCk
categories: [商品问题, 商品侵权问题, 其他]
author: "[[authors/author-video-rec.md]]"
notes: 自动化处置
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：Video_Rec 
互动数据：点赞2498, 播放175892
时间：2025-07-25
链接：https://www.youtube.com/watch?v=d_hdZhCflCk

原文内容：
标题：TEMU Shopping Fails You Won't Believe! #1

描述：Are you ready to see the most unbelievable TEMU shopping fails ever? In this video episode, we reveal the funniest and most shocking TEMU disasters that will make you think twice before clicking Add to Cart! From miniature furniture to ridiculous knock-offs, we rank the worst online shopping fails people actually received from TEMU.

Some of these disasters could’ve been avoided… But where’s the fun in that? 
👉 If you love watching hilarious shopping fails, expectation vs reality and funny online shopping reviews, this video is for you!

⭐ Don’t forget to hit LIKE, SUBSCRIBE, and turn on the bell for more crazy shopping fail compilations every week.

💬 Have you ever had a TEMU shopping fail? Share your funniest online shopping disasters with
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "内容为购物失败合集视频，包含商品质量、侵权等负面指控，但属于娱乐化内容，非真实用户投诉，传播影响力中等（播放17.5万，点赞2498），未达到P1红线标准",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [
    "质量",
    "合规",
    "竞品攻击",
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
    "商品侵权问题",
    "其他"
  ],
  "摘要": "YouTube娱乐视频合集展示TEMU购物失败案例，包括商品尺寸不符、侵权仿冒、有毒材料等指控，播放17.5万，评论区部分用户批评视频内容陈旧且与TEMU无关"
}
```

## 判据链

- **严重度判决**：内容为购物失败合集视频，包含商品质量、侵权等负面指控，但属于娱乐化内容，非真实用户投诉，传播影响力中等（播放17.5万，点赞2498），未达到P1红线标准
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：质量, 合规, 竞品攻击, 大规模传播

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

自动化处置

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

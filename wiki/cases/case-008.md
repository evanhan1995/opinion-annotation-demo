---
title: 案例008: 1160万粉YouTuber发布shorts视频，标题'Is Temu A Scam?'展示廉价产品，播放146万，评论
type: case
created: 2026-05-12
severity: P2
action: 持续观察
platform: YouTube
url: https://www.youtube.com/shorts/-VGsjKF27Fg
source: auto_ingest
tags: [auto_ingest, P2]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: Sambucha, 11,600,000订阅
互动数据：播放1,466,395, 点赞92,021, 评论1,204
时间：2025-03-20
链接：https://www.youtube.com/shorts/-VGsjKF27Fg

原文内容：
标题：Is Temu A Scam?

描述：Follow me here:
Instagram ► https://www.instagram.com/sambucha 
X ► https://www.x.com/sambucha 

Become a Member:
https://www.youtube.com/channel/UCWBWgCD4oAqT3hUeq40SCUw/join 

#shorts #temu #scam #scams #product #products #cheap #money #funny #sambucha
```

## AI 原始标注

```json
{
  "内容分类": "视频/短视频",
  "情感分析": {
    "整体情感": "混合",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "标题'Is Temu A Scam?'暗示欺诈嫌疑"
    },
    "产品维度": [
      {
        "产品名称": "TEMU（平台）",
        "情感": "负面",
        "关键短语": "标题'Is Temu A Scam?'，视频内容展示廉价产品"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否"
    }
  },
  "严重度评级": "P2",
  "严重度理由": "中危内容(标题含'Scam'关键词，可能引发品牌信任质疑)+高影响力(1160万粉大V，播放146万，点赞9.2万)+已发布超2个月无加速传播态势→P2",
  "分流建议": "持续观察",
  "分流理由": "高影响力但内容为娱乐性短视频，标题为疑问句而非指控，评论区未出现集中负面攻击，需监控评论区风向及是否被二次传播",
  "真实性评估": {
    "判断": "无法判断",
    "信号": [
      "视频为娱乐性shorts，内容可能夸张",
      "标题为疑问句，未提供具体证据",
      "发布者为大V但内容风格偏搞笑"
    ]
  },
  "摘要": "1160万粉YouTuber发布shorts视频，标题'Is Temu A Scam?'展示廉价产品，播放146万，评论区以调侃和中性讨论为主",
  "风险标签": [
    "KOL负面"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "中",
    "整体置信度": "中"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 1,
      "黄": 7,
      "绿": 2
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "Bro dosent know to unfold the drone 😢",
        "情感": "中性",
        "关键短语": "调侃用户不会展开无人机"
      },
      {
        "序号": 2,
        "内容": "I never thought I would find hope again after everything I went through, but Byteprov changed my story completely. A huge thank you from me and everyone you’ve helped.",
        "情感": "中性",
        "关键短语": "疑似广告/无关内容"
      },
      {
        "序号": 3,
        "内容": "\"Outside of technology\" bro that's literally a pie e of technology",
        "情感": "中性",
        "关键短语": "调侃视频内容逻辑"
      },
      {
        "序号": 4,
        "内容": "That talking cactus I bought in India is $5",
        "情感": "中性",
        "关键短语": "分享个人经历，无评价TEMU"
      },
      {
        "序号": 5,
        "内容": "U just gotta read the reviews and look the stuff up",
        "情感": "正面",
        "关键短语": "建议用户自行判断，隐含TEMU可用"
      },
      {
        "序号": 6,
        "内容": "i have one of those gameboy consoles :p",
        "情感": "中性",
        "关键短语": "分享个人经历，无评价"
      },
      {
        "序号": 7,
        "内容": "did i see chinese translator pen? is that a bringus studios reference",
        "情感": "中性",
        "关键短语": "提问，无关品牌评价"
      },
      {
        "序号": 8,
        "内容": "bro is buying stuff that is made by slave labor in china💀🥵🗿",
        "情感": "负面",
        "关键短语": "负面指控'奴隶劳动'，但语气夸张"
      },
      {
        "序号": 9,
        "内容": "It depends on the seller",
        "情感": "正面",
        "关键短语": "理性分析，为TEMU辩护"
      },
      {
        "序号": 10,
        "内容": "Talk about the promise of getting money back",
        "情感": "中性",
        "关键短语": "建议讨论退款承诺，中性"
      }
    ],
    "评论总结": "评论区以调侃和中性讨论为主，无集中负面攻击，个别负面评论语气夸张"
  }
}
```

## 判据链

- **严重度判决**：中危内容(标题含'Scam'关键词，可能引发品牌信任质疑)+高影响力(1160万粉大V，播放146万，点赞9.2万)+已发布超2个月无加速传播态势→P2
- **分流判决**：高影响力但内容为娱乐性短视频，标题为疑问句而非指控，评论区未出现集中负面攻击，需监控评论区风向及是否被二次传播
- **真实性判断**：无法判断
- **风险标签**：KOL负面

## 边界讨论

- **新平台**：「YouTube」在现有案例库中尚无覆盖，扩展了知识库的平台维度。

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

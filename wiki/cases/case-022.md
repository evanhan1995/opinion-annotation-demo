---
title: 案例022: YouTuber Lindey Glenn（48.2万粉）发布视频，指控Temu面临亚利桑那州诉讼，涉及误导用户、过度收
type: case
created: 2026-05-14
severity: P0
action: 立即处理
platform: YouTube
source: human_correction
url: https://www.youtube.com/watch?v=7kIJxo7XBLY
original_ai_output:
  severity: P1
  action: 立即处理
tags: [纠偏案例, P0]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: This Morning, 2,520,000订阅
互动数据：播放1,445,977, 点赞8,574, 评论50
时间：2024-05-30
链接：https://www.youtube.com/watch?v=7kIJxo7XBLY

原文内容：
标题：The Truth About Temu: Are The Deals Too Good To Be True? | This Morning

描述：Fancy treating yourself to a handbag for 87p? What about a new electric toothbrush for £2.24? Or you could splurge on a kitchen blender for £6.75? Those are just some of the deals that are being offered by the hugely popular online retailer Temu - with the app being downloaded more than 19 MILLION times in the UK alone. But are their offers too good to be true? As that becomes the subject of a brand-new documentary, we’re joined by investigative journalist Ellie Flynne alongside Alice Beer. 

Broadcast on 30/05/2024
Subscribe to This Morning for more exclusive videos: http://bit.ly/1JM41yF

FOLLOW US:
https://www.facebook.com/ThisMorning
https://www.instagram.com/thismorning
https://www.tiktok.com/@thismorning


```

## AI 原始标注

```json
{
  "内容分类": "新闻报道",
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "Are The Deals Too Good To Be True?; investigative journalist alongside Alice Beer"
    },
    "产品维度": [
      {
        "产品名称": "Temu平台",
        "情感": "混合",
        "关键短语": "deals that are being offered by the hugely popular online retailer Temu; are their offers too good to be true?"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否",
      "竞品名称": "不适用",
      "竞品情感": "不适用",
      "与我方对比": "不适用"
    }
  },
  "严重度评级": "P1",
  "严重度理由": "中危内容（质疑商业模式/数据安全）+ 高影响力（2.52M订阅频道、144万播放、8.5K点赞）+ 发展态势加速（新闻媒体转载风险高）",
  "分流建议": "立即处理",
  "分流理由": "高影响力媒体节目质疑商业模式，涉及数据安全等红线话题，且评论区出现负面体验投诉，需立即响应",
  "真实性评估": {
    "判断": "大概率真实",
    "信号": [
      "权威媒体（ITV）制作，有具体播出日期和主持人",
      "引用调查记者和专家评论",
      "评论区有用户真实负面体验（未收到货、退货问题）"
    ]
  },
  "摘要": "ITV《This Morning》节目质疑Temu低价模式是否可信，邀请调查记者讨论，播放量超144万，评论区出现未收货、退货难等投诉。",
  "风险标签": [
    "质量",
    "客服",
    "物流",
    "大规模传播",
    "数据安全"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "中",
    "整体置信度": "高"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 4,
      "黄": 4,
      "绿": 2
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "Global postal rates give Chinese companies an unfair advantage - it will cost a British company at least double in postage to send a small parcel to a customer than the same item sent from China.",
        "情感": "中性",
        "关键短语": "unfair advantage"
      },
      {
        "序号": 2,
        "内容": "How",
        "情感": "中性",
        "关键短语": "无实质内容"
      },
      {
        "序号": 3,
        "内容": "The large majority of products including high-end luxury fashion such as LV or Apple are all made in China. You from Amazon makes absolutely no difference, except you get worse, Customer Service than",
        "情感": "中性",
        "关键短语": "made in China"
      },
      {
        "序号": 4,
        "内容": "The more fundamental issue, my understanding is that it’s data scrapping, that’s the aim of the model.",
        "情感": "负面",
        "关键短语": "data scrapping"
      },
      {
        "序号": 5,
        "内容": "The difference is price!!",
        "情感": "中性",
        "关键短语": "price"
      },
      {
        "序号": 6,
        "内容": "I have orders some times three times a week, I bought everything for my daughter’s wedding for under £20. So as these lot have high wages and I live on a pension, so don’t preach about things you don’",
        "情感": "正面",
        "关键短语": "bought everything for my daughter’s wedding for under £20"
      },
      {
        "序号": 7,
        "内容": "Complete fraud, ordered 6 items got NOTHING",
        "情感": "负面",
        "关键短语": "Complete fraud, got NOTHING"
      },
      {
        "序号": 8,
        "内容": "I will never order from temu again!!  They sent wrong item!!  Ridiculous return issues!! (赞:1)",
        "情感": "负面",
        "关键短语": "never order from temu again, wrong item, ridiculous return issues"
      },
      {
        "序号": 9,
        "内容": "Made in china, your not paying treble prices for the same items on the high street",
        "情感": "中性",
        "关键短语": "not paying treble prices"
      },
      {
        "序号": 10,
        "内容": "I have bought an abundance of items from Temu and I get compliments from friends on my new clothing products.  The variety is brilliant, plus due to there being duplicates on the site from different s",
        "情感": "正面",
        "关键短语": "bought an abundance, get compliments, variety is brilliant"
      },
      {
        "序号": 11,
        "内容": "Cost me £250 bought 2 solar power stations  evre delivered 2 solar panels strapped together FedEx delivered 1 power station and 1 power station missing not impressed been ripped off possibly been stol",
        "情感": "负面",
        "关键短语": "cost me £250, 1 power station missing, been ripped off"
      }
    ],
    "评论总结": "评论区负面为主，有用户投诉未收货、退货难、数据安全担忧，也有正面体验分享。"
  }
}
```

## 人工修正标注

```json
{
  "内容分类": "新闻报道",
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "Are The Deals Too Good To Be True?; investigative journalist alongside Alice Beer"
    },
    "产品维度": [
      {
        "产品名称": "Temu平台",
        "情感": "混合",
        "关键短语": "deals that are being offered by the hugely popular online retailer Temu; are their offers too good to be true?"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否",
      "竞品名称": "不适用",
      "竞品情感": "不适用",
      "与我方对比": "不适用"
    }
  },
  "严重度评级": "P0",
  "严重度理由": "涉及法律诉讼（Arizona lawsuit）、数据隐私合规红线、KOL（48.2万粉）发布且传播加速（播放12.7万+点赞8k+评论50），满足P0红线第2条（法律/监管行动）和第7条（KOL>10万粉严重负面+传播加速）",
  "分流建议": "立即处理",
  "分流理由": "高影响力媒体节目质疑商业模式，涉及数据安全等红线话题，且评论区出现负面体验投诉，需立即响应",
  "真实性评估": {
    "判断": "大概率真实",
    "信号": [
      "权威媒体（ITV）制作，有具体播出日期和主持人",
      "引用调查记者和专家评论",
      "评论区有用户真实负面体验（未收到货、退货问题）"
    ]
  },
  "摘要": "YouTuber Lindey Glenn（48.2万粉）发布视频，指控Temu面临亚利桑那州诉讼，涉及误导用户、过度收集数据、神秘扣费和返现陷阱，播放12.7万，传播加速。",
  "风险标签": [
    "质量",
    "客服",
    "物流",
    "大规模传播",
    "数据安全"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "中",
    "整体置信度": "高"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 5,
      "黄": 2,
      "绿": 4
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "Global postal rates give Chinese companies an unfair advantage - it will cost a British company at least double in postage to send a small parcel to a customer than the same item sent from China.",
        "情感": "负面",
        "关键短语": "unfair advantage"
      },
      {
        "序号": 2,
        "内容": "How",
        "情感": "中性",
        "关键短语": "无实质内容"
      },
      {
        "序号": 3,
        "内容": "The large majority of products including high-end luxury fashion such as LV or Apple are all made in China. You from Amazon makes absolutely no difference, except you get worse, Customer Service than",
        "情感": "正面",
        "关键短语": "made in China"
      },
      {
        "序号": 4,
        "内容": "The more fundamental issue, my understanding is that it’s data scrapping, that’s the aim of the model.",
        "情感": "负面",
        "关键短语": "data scrapping"
      },
      {
        "序号": 5,
        "内容": "The difference is price!!",
        "情感": "中性",
        "关键短语": "price"
      },
      {
        "序号": 6,
        "内容": "I have orders some times three times a week, I bought everything for my daughter’s wedding for under £20. So as these lot have high wages and I live on a pension, so don’t preach about things you don’",
        "情感": "正面",
        "关键短语": "bought everything for my daughter’s wedding for under £20"
      },
      {
        "序号": 7,
        "内容": "Complete fraud, ordered 6 items got NOTHING",
        "情感": "负面",
        "关键短语": "Complete fraud, got NOTHING"
      },
      {
        "序号": 8,
        "内容": "I will never order from temu again!!  They sent wrong item!!  Ridiculous return issues!! (赞:1)",
        "情感": "负面",
        "关键短语": "never order from temu again, wrong item, ridiculous return issues"
      },
      {
        "序号": 9,
        "内容": "Made in china, your not paying treble prices for the same items on the high street",
        "情感": "正面",
        "关键短语": "not paying treble prices"
      },
      {
        "序号": 10,
        "内容": "I have bought an abundance of items from Temu and I get compliments from friends on my new clothing products.  The variety is brilliant, plus due to there being duplicates on the site from different s",
        "情感": "正面",
        "关键短语": "bought an abundance, get compliments, variety is brilliant"
      },
      {
        "序号": 11,
        "内容": "Cost me £250 bought 2 solar power stations  evre delivered 2 solar panels strapped together FedEx delivered 1 power station and 1 power station missing not impressed been ripped off possibly been stol",
        "情感": "负面",
        "关键短语": "cost me £250, 1 power station missing, been ripped off"
      }
    ],
    "评论总结": "前排评论以负面为主（5条），用户普遍批评Temu为骗局或浪费精力，少数中性评论为客观讨论或辩护，正面仅1条针对博主外貌。"
  },
  "_meta": {
    "model": "deepseek-chat",
    "streamed": true,
    "output_chars": 3394
  }
}
```

## 差异分析

- **严重度评级**：AI 判为「P1」→ 人工修正为「P0」
- **评论区分析.评论红绿灯**：AI 判为「{"红": 4, "黄": 4, "绿": 2}」→ 人工修正为「{"红": 5, "黄": 2, "绿": 4}」
- **评论区分析.评论总结**：AI 判为「评论区负面为主，有用户投诉未收货、退货难、数据安全担忧，也有正面体验分享。」→ 人工修正为「前排评论以负面为主（5条），用户普遍批评Temu为骗局或浪费精力，少数中性评论为客观讨论或辩护，正面仅1条针对博主外貌。」

## 对标注规范的影响

（待分析：此纠偏案例揭示的规则盲区或阈值调整建议。）

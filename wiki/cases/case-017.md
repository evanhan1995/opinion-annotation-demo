---
title: 案例017: 69.1万粉YouTuber发布视频指控TEMU虚假宣传免费赠品，规则不透明，播放18.5万，评论区出现集体诉讼呼声和劝
type: case
created: 2026-05-14
severity: P2
action: 持续观察
platform: YouTube
source: auto_ingest
url: https://www.youtube.com/watch?v=-GoAFaMHYY8
tags: [auto_ingest, P2]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: Jacob R, 691,000订阅
互动数据：播放185,223, 点赞6,835, 评论540
时间：2025-10-23
链接：https://www.youtube.com/watch?v=-GoAFaMHYY8

原文内容：
标题：TEMU does NOT want this video going Public... 😬

描述：Can't make this stuff up 😂 cmon temu... what are we doing here?

Buy stuff from our previous videos on my website here: https://shop.jrobgaming.com/

Check out the other videos in this temu saga:
https://youtu.be/VtHsnIA5BpY
https://youtu.be/zWZlj457_F4

My other YouTube channels:
Smokin' Silicon (phones & other tech): https://www.youtube.com/@SmokinSilicon
Crackin' Carts (retro video game hardware): https://www.youtube.com/@CrackinCarts
Jacob R TWO (video game news): https://www.youtube.com/@JacobRTWO

Where I sell consoles & games: 
My Website: https://www.jrobgaming.com/
Whatnot: https://whatnot.com/invite/jacobr
Encore: https://www.buyencore.com/invite/jrob0021

My other social media platforms:
Sign up for my newsletter: https://jr
```

## AI 原始标注

```json
{
  "内容分类": "投诉",
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "TEMU does NOT want this video going Public, what are we doing here?"
    },
    "产品维度": [
      {
        "产品名称": "TEMU（平台）",
        "情感": "负面",
        "关键短语": "free items, fine print, scam, class action"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否"
    }
  },
  "严重度评级": "P2",
  "严重度理由": "中危内容(指控TEMU虚假宣传免费赠品、规则不透明，涉及消费欺诈争议)+中影响力(69.1万粉KOL，播放18.5万，点赞6835)+已发布超7个月无加速传播态势→P2",
  "分流建议": "持续观察",
  "分流理由": "内容涉及虚假宣传和消费欺诈指控，KOL有一定粉丝基础，评论区出现'集体诉讼'呼声和劝退购买言论，需监控是否出现同类投诉聚集(≥3个同类报告→升级P1)",
  "真实性评估": {
    "判断": "存疑",
    "信号": [
      "KOL为游戏/科技频道，有历史内容",
      "标题暗示TEMU试图压制视频(情绪化)",
      "评论区有用户质疑KOL自身责任('you knew it was a scam')",
      "缺少具体订单号或截图证据"
    ]
  },
  "摘要": "69.1万粉YouTuber发布视频指控TEMU虚假宣传免费赠品，规则不透明，播放18.5万，评论区出现集体诉讼呼声和劝退购买言论",
  "风险标签": [
    "合规",
    "KOL负面"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "高",
    "整体置信度": "中"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 3,
      "黄": 4,
      "绿": 3
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "I'm surprised they actually gave you one of the free items you picked, given that the fine print you glossed over said \"for illustrative purposes only\"!",
        "情感": "中性",
        "关键短语": "指出KOL忽略细则，中性"
      },
      {
        "序号": 2,
        "内容": "You're fighting over not getting a Switch for a penny? Come on, man. It was a scam and you knew it. Cut your losses. It could be worse, you could have sent $1000 to a Nigerian prince! 😂",
        "情感": "正面",
        "关键短语": "批评KOL明知是骗局还纠缠，正面(维护TEMU)"
      },
      {
        "序号": 3,
        "内容": "The ads can't even decide how the name of the company is pronounced. Is it Teamu or Temmu?",
        "情感": "中性",
        "关键短语": "调侃发音，中性"
      },
      {
        "序号": 4,
        "内容": "You have some responsibility in interacting with this crap. And, where is all this stuff going? To recycling or to the landfill?",
        "情感": "正面",
        "关键短语": "批评KOL自身责任，正面(维护TEMU)"
      },
      {
        "序号": 5,
        "内容": "Thanks that is horrible of an experience you had  I definitely will never order from them 😳😢💯",
        "情感": "负面",
        "关键短语": "感谢KOL分享，表示永不购买，负面"
      },
      {
        "序号": 6,
        "内容": "@seekervr3s show me a screenshot of your cart before you buy anything and I’ll tell you what you need to do to get the credit.",
        "情感": "中性",
        "关键短语": "提供获取积分建议，中性"
      },
      {
        "序号": 7,
        "内容": "Bro I got temu ads before watching videos dammmm",
        "情感": "中性",
        "关键短语": "调侃广告投放，中性"
      },
      {
        "序号": 8,
        "内容": "And I got a Temu Ad at the end of the video 😂",
        "情感": "中性",
        "关键短语": "调侃广告投放，中性"
      },
      {
        "序号": 9,
        "内容": "Class action suit anybody?  They do say free gifts pay nothing pick them out but then the rules change and it's credit or payback in coupons or make a minimum order.....",
        "情感": "负面",
        "关键短语": "呼吁集体诉讼，负面"
      },
      {
        "序号": 10,
        "内容": "Some things on temu are good tbh",
        "情感": "正面",
        "关键短语": "为TEMU辩护，正面"
      }
    ],
    "评论总结": "评论区观点分化，部分批评KOL明知故犯，部分劝退购买并呼吁集体诉讼，整体风向偏中性"
  }
}
```

## 判据链

- **严重度判决**：中危内容(指控TEMU虚假宣传免费赠品、规则不透明，涉及消费欺诈争议)+中影响力(69.1万粉KOL，播放18.5万，点赞6835)+已发布超7个月无加速传播态势→P2
- **分流判决**：内容涉及虚假宣传和消费欺诈指控，KOL有一定粉丝基础，评论区出现'集体诉讼'呼声和劝退购买言论，需监控是否出现同类投诉聚集(≥3个同类报告→升级P1)
- **真实性判断**：存疑
- **风险标签**：合规, KOL负面

## 边界讨论

- **新平台**：「YouTube」在现有案例库中尚无覆盖，扩展了知识库的平台维度。

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

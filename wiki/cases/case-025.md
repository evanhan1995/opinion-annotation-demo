---
title: 案例025: 用户投诉在TEMU购买布包却收到假花，且申诉仅获半额退款，表达强烈不满
type: case
created: 2026-05-14
severity: P2
action: 持续观察
platform: YouTube
source: human_correction
url: https://www.youtube.com/watch?v=DIBL7PKlzaU
original_ai_output:
  severity: P1
  action: 立即处理
tags: [纠偏案例, P2]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: China Observer, 814,000订阅
互动数据：播放1,013,104, 点赞14,371, 评论50
时间：2023-11-22
链接：https://www.youtube.com/watch?v=DIBL7PKlzaU

原文内容：
标题：Temu Pinduoduo Flooded With Fakes & Trash, Dare to Shop at These Platforms? Made in China Is Dubious

描述：From the earlier days of online ecommerce giant, Taobao, to the low-price champion Pinduoduo, and now TikTok entering the online shopping race, all are rife with counterfeit and inferior products. In China, shopping mishaps are a common occurrence, almost everyone who has shopped online has encountered them.
#temu #pinduoduo #fake #trash #kickoff #chinaobserver
All rights reserved.
```

## AI 原始标注

```json
{
  "内容分类": "投诉",
  "舆情分类": [
    "商品问题",
    "商品侵权问题"
  ],
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "Temu Pinduoduo Flooded With Fakes & Trash, Dare to Shop at These Platforms? Made in China Is Dubious"
    },
    "产品维度": [
      {
        "产品名称": "Temu/Pinduoduo平台商品",
        "情感": "负面",
        "关键短语": "counterfeit and inferior products, shopping mishaps"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否",
      "竞品名称": "",
      "竞品情感": "不适用",
      "与我方对比": "不适用"
    }
  },
  "严重度评级": "P1",
  "严重度理由": "中危内容（商品质量/侵权指控）×高影响力（播放超100万，KOL粉丝81.4万）→P1；未触发P0红线（无安全/法律/政治敏感等）",
  "分流建议": "立即处理",
  "分流理由": "P1+高影响力，需立即建联沟通并监控传播态势",
  "真实性评估": {
    "判断": "存疑",
    "信号": [
      "视频包含具体产品展示和案例（有细节），但标题和描述存在情绪化概括（'Flooded With Fakes & Trash'），且发布者China Observer有特定立场"
    ]
  },
  "摘要": "YouTuber China Observer（81.4万粉）发布视频指控Temu/Pinduoduo充斥假货劣品，播放超101万，评论50条，评论区多为负面附和。",
  "风险标签": [
    "质量",
    "合规",
    "KOL负面",
    "大规模传播"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "高",
    "整体置信度": "高"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 7,
      "黄": 2,
      "绿": 1
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "You are lucky if you don't receive something hazzardous to ANY live being !!  Harmfull to YOU your KIDS or even your PETS !!!  CHINA RIPS EVERYONE OFF WITH LIE'S UPON LIE'S !!!       Never trust anyth",
        "情感": "负面",
        "关键短语": "hazzardous, Harmfull, CHINA RIPS EVERYONE OFF"
      },
      {
        "序号": 2,
        "内容": "Chinese counterfeiters are too much 😂😂 it’s so funny. 😂😂 it’s funny only when it’s harmless though",
        "情感": "负面",
        "关键短语": "counterfeiters, too much"
      },
      {
        "序号": 3,
        "内容": "All from Taiwan are pure original 🇹🇼🇹🇼🇹🇼",
        "情感": "负面",
        "关键短语": "All from Taiwan are pure original（暗示大陆产品非原创）"
      },
      {
        "序号": 4,
        "内容": "No dis but what do ppl expect to get when they buy dirt cheap stuff?",
        "情感": "中性",
        "关键短语": "what do ppl expect（理性讨论）"
      },
      {
        "序号": 5,
        "内容": "4:49 😂🤣🤣🤣🤣🤣 That horn sounds like a guy being pleasured from the rear!!😅🤣🤣",
        "情感": "中性",
        "关键短语": "无关内容，对视频具体片段调侃"
      },
      {
        "序号": 6,
        "内容": "4:41 is the best cant stop laughing haha :)))",
        "情感": "中性",
        "关键短语": "无关内容，对视频具体片段调侃"
      },
      {
        "序号": 7,
        "内容": "Australian politicians love made in china. They can't get enough of it! Australian culture? Made in China culture.",
        "情感": "负面",
        "关键短语": "讽刺性评论，暗示中国制造泛滥"
      },
      {
        "序号": 8,
        "内容": "8:25 then the dies will have a very high lead content , goodbye health- hello to new kidney donors and kidney failures",
        "情感": "负面",
        "关键短语": "high lead content, goodbye health, kidney failures"
      },
      {
        "序号": 9,
        "内容": "Never buy stuff from temu",
        "情感": "负面",
        "关键短语": "Never buy stuff from temu"
      },
      {
        "序号": 10,
        "内容": "China observ e as calculadoras cientificas fakes eim ????",
        "情感": "负面",
        "关键短语": "fakes（葡萄牙语，质疑计算器假货）"
      }
    ],
    "评论总结": "评论区以负面为主，多数附和视频指控，部分评论情绪激烈并上升至对中国制造的攻击。"
  }
}
```

## 人工修正标注

```json
{
  "内容分类": "投诉",
  "舆情分类": [
    "商品问题",
    "售后问题"
  ],
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "Temu Pinduoduo Flooded With Fakes & Trash, Dare to Shop at These Platforms? Made in China Is Dubious"
    },
    "产品维度": [
      {
        "产品名称": "Temu/Pinduoduo平台商品",
        "情感": "负面",
        "关键短语": "counterfeit and inferior products, shopping mishaps"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否",
      "竞品名称": "",
      "竞品情感": "不适用",
      "与我方对比": "不适用"
    }
  },
  "严重度评级": "P2",
  "严重度理由": "中危内容（商品发错+售后申诉困难）但低影响力（点赞6，评论3，无加速传播迹象），按矩阵中危×低影响力=P2",
  "分流建议": "持续观察",
  "分流理由": "P1+高影响力，需立即建联沟通并监控传播态势",
  "真实性评估": {
    "判断": "存疑",
    "信号": [
      "视频包含具体产品展示和案例（有细节），但标题和描述存在情绪化概括（'Flooded With Fakes & Trash'），且发布者China Observer有特定立场"
    ]
  },
  "摘要": "用户投诉在TEMU购买布包却收到假花，且申诉仅获半额退款，表达强烈不满",
  "风险标签": [
    "质量",
    "合规",
    "KOL负面",
    "大规模传播"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "高",
    "整体置信度": "高"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 6,
      "黄": 2,
      "绿": 2
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "You are lucky if you don't receive something hazzardous to ANY live being !!  Harmfull to YOU your KIDS or even your PETS !!!  CHINA RIPS EVERYONE OFF WITH LIE'S UPON LIE'S !!!       Never trust anyth",
        "情感": "负面",
        "关键短语": "hazzardous, Harmfull, CHINA RIPS EVERYONE OFF"
      },
      {
        "序号": 2,
        "内容": "Chinese counterfeiters are too much 😂😂 it’s so funny. 😂😂 it’s funny only when it’s harmless though",
        "情感": "负面",
        "关键短语": "counterfeiters, too much"
      },
      {
        "序号": 3,
        "内容": "All from Taiwan are pure original 🇹🇼🇹🇼🇹🇼",
        "情感": "正面",
        "关键短语": "All from Taiwan are pure original（暗示大陆产品非原创）"
      },
      {
        "序号": 4,
        "内容": "No dis but what do ppl expect to get when they buy dirt cheap stuff?",
        "情感": "正面",
        "关键短语": "what do ppl expect（理性讨论）"
      },
      {
        "序号": 5,
        "内容": "4:49 😂🤣🤣🤣🤣🤣 That horn sounds like a guy being pleasured from the rear!!😅🤣🤣",
        "情感": "中性",
        "关键短语": "无关内容，对视频具体片段调侃"
      },
      {
        "序号": 6,
        "内容": "4:41 is the best cant stop laughing haha :)))",
        "情感": "中性",
        "关键短语": "无关内容，对视频具体片段调侃"
      },
      {
        "序号": 7,
        "内容": "Australian politicians love made in china. They can't get enough of it! Australian culture? Made in China culture.",
        "情感": "负面",
        "关键短语": "讽刺性评论，暗示中国制造泛滥"
      },
      {
        "序号": 8,
        "内容": "8:25 then the dies will have a very high lead content , goodbye health- hello to new kidney donors and kidney failures",
        "情感": "负面",
        "关键短语": "high lead content, goodbye health, kidney failures"
      },
      {
        "序号": 9,
        "内容": "Never buy stuff from temu",
        "情感": "负面",
        "关键短语": "Never buy stuff from temu"
      },
      {
        "序号": 10,
        "内容": "China observ e as calculadoras cientificas fakes eim ????",
        "情感": "负面",
        "关键短语": "fakes（葡萄牙语，质疑计算器假货）"
      }
    ],
    "评论总结": "前排评论以负面为主，用户抱怨退款政策并放弃平台，另一条提及法律案件"
  },
  "_meta": {
    "model": "deepseek-chat",
    "streamed": true,
    "output_chars": 2672
  }
}
```

## 差异分析

- **严重度评级**：AI 判为「P1」→ 人工修正为「P2」
- **分流建议**：AI 判为「立即处理」→ 人工修正为「持续观察」
- **评论区分析.评论红绿灯**：AI 判为「{"红": 7, "黄": 2, "绿": 1}」→ 人工修正为「{"红": 6, "黄": 2, "绿": 2}」
- **评论区分析.评论总结**：AI 判为「评论区以负面为主，多数附和视频指控，部分评论情绪激烈并上升至对中国制造的攻击。」→ 人工修正为「前排评论以负面为主，用户抱怨退款政策并放弃平台，另一条提及法律案件」

## 对标注规范的影响

（待分析：此纠偏案例揭示的规则盲区或阈值调整建议。）

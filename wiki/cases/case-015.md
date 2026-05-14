---
title: 案例015: 208万粉YouTuber发布shorts视频揭露TEMU真相，引用CNN报道指控间谍软件，播放1352万，评论区出现删
type: case
created: 2026-05-14
severity: P1
action: 立即处理
platform: YouTube
source: auto_ingest
url: https://www.youtube.com/shorts/pWBPRh0lDmM
tags: [auto_ingest, P1]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: Nathan Espinoza, 2,080,000订阅
互动数据：播放13,525,752, 点赞631,889, 评论7,626
时间：2023-06-10
链接：https://www.youtube.com/shorts/pWBPRh0lDmM

原文内容：
标题：The TRUTH About Temu
```

## AI 原始标注

```json
{
  "内容分类": "新闻报道",
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "The TRUTH About Temu, Spyware, CNN news report"
    },
    "产品维度": [
      {
        "产品名称": "TEMU（平台）",
        "情感": "负面",
        "关键短语": "Spyware, malware, app is the Spyware not the website"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否"
    }
  },
  "严重度评级": "P1",
  "严重度理由": "高危内容(涉及间谍软件/恶意软件指控，引用CNN报道，有组织传播信号)+高影响力(208万粉大V，播放1352万，点赞63万)+已发布近3年无加速传播态势→高危×高影响力×衰减=P1(不满足P0条件：无安全事故/法律行动/监管介入/大规模传播中的品牌核心攻击)",
  "分流建议": "立即处理",
  "分流理由": "内容涉及间谍软件/恶意软件指控，发布者为208万粉大V，播放量超1352万，评论区出现CNN报道引用和删除APP号召，虽已发布近3年但内容仍具传播力，需法务和PR侧评估是否需要官方回应或法律行动",
  "真实性评估": {
    "判断": "存疑",
    "信号": [
      "引用CNN报道(可验证来源)",
      "发布者为大V但内容为shorts短视频",
      "评论区有用户分享CNN链接",
      "但标题'The TRUTH'暗示立场，缺少具体技术证据"
    ]
  },
  "摘要": "208万粉YouTuber发布shorts视频揭露TEMU真相，引用CNN报道指控间谍软件，播放1352万，评论区出现删除APP号召和CNN链接分享",
  "风险标签": [
    "安全",
    "合规",
    "KOL负面",
    "大规模传播"
  ],
  "置信度": {
    "分类置信度": "高",
    "情感置信度": "高",
    "整体置信度": "中"
  },
  "评论区分析": {
    "评论红绿灯": {
      "红": 2,
      "黄": 5,
      "绿": 3
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "Here’s the CNN news report if you want to learn more: https://amp.cnn.com/cnn/2023/03/21/tech/china-google-pinduoduo-malware-app-intl-hk/index.html What about the Temu Nintendo Switch?: https://you",
        "情感": "负面",
        "关键短语": "CNN news report, malware app"
      },
      {
        "序号": 2,
        "内容": "Right after this video I got an add for TEMU",
        "情感": "中性",
        "关键短语": "观察到广告投放，中性"
      },
      {
        "序号": 3,
        "内容": "​ @FTTCCT Omg",
        "情感": "中性",
        "关键短语": "感叹，无实质内容"
      },
      {
        "序号": 4,
        "内容": "​​ @FTTCCT Revelation 3:20 Behold, I stand at the door, and knock: if any man hear my voice, and open the door, I will come in to him, and will sup with him, and he with me. HEY THERE 🤗 JESUS IS CAL",
        "情感": "中性",
        "关键短语": "宗教内容，无关"
      },
      {
        "序号": 5,
        "内容": "I got a temu ad directly after watching this. Havent laughed that hard at a ad timing ever",
        "情感": "中性",
        "关键短语": "调侃广告时机，中性"
      },
      {
        "序号": 6,
        "内容": "​@The_medicine_frog Omg",
        "情感": "中性",
        "关键短语": "感叹，无实质内容"
      },
      {
        "序号": 7,
        "内容": "Just don't use the app because the app is the Spyware not the website",
        "情感": "负面",
        "关键短语": "app是间谍软件，负面"
      },
      {
        "序号": 8,
        "content": "Bro really shared an amp link",
        "情感": "中性",
        "关键短语": "调侃链接格式，中性"
      },
      {
        "序号": 9,
        "内容": "Thank you for this!  Deleting their app.",
        "情感": "正面",
        "关键短语": "感谢发布者，删除APP"
      },
      {
        "序号": 10,
        "内容": "​ @GlassOwl84 good ❤",
        "情感": "正面",
        "关键短语": "赞同，正面"
      }
    ],
    "评论总结": "评论区出现CNN报道引用和删除APP号召，负面指控被传播，但部分评论为调侃和无关内容"
  }
}
```

## 判据链

- **严重度判决**：高危内容(涉及间谍软件/恶意软件指控，引用CNN报道，有组织传播信号)+高影响力(208万粉大V，播放1352万，点赞63万)+已发布近3年无加速传播态势→高危×高影响力×衰减=P1(不满足P0条件：无安全事故/法律行动/监管介入/大规模传播中的品牌核心攻击)
- **分流判决**：内容涉及间谍软件/恶意软件指控，发布者为208万粉大V，播放量超1352万，评论区出现CNN报道引用和删除APP号召，虽已发布近3年但内容仍具传播力，需法务和PR侧评估是否需要官方回应或法律行动
- **真实性判断**：存疑
- **风险标签**：安全, 合规, KOL负面, 大规模传播

## 边界讨论

- **P1 边界案例**：当前案例属于 P1 严重度，这是案例库的覆盖盲区，建议优先人工复核。
- **新平台**：「YouTube」在现有案例库中尚无覆盖，扩展了知识库的平台维度。

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

---
title: 案例016: 167万粉YouTuber发布视频标题称TEMU为'最卑鄙公司'，播放131万，评论区出现对发布者虚伪的批评但未减轻对T
type: case
created: 2026-05-14
severity: P1
action: 立即处理
platform: YouTube
source: auto_ingest
url: https://www.youtube.com/watch?v=36bb2b24Qto
tags: [auto_ingest, P1]
---

## 原始输入

```
平台：YouTube
发布者：YouTuber: Moon, 1,670,000订阅
互动数据：播放1,310,409, 点赞38,001, 评论5,404
时间：2023-10-21
链接：https://www.youtube.com/watch?v=36bb2b24Qto

原文内容：
标题：Temu: The Scummiest Company In The World

描述：Try out invideo AI for FREE here! ➡️ https://invideo.io/i/moon

Moon Newsletter - https://mailchi.mp/3ded12821743/moon

Support the channel here (all money goes straight back into the channel):
►  Become a Patron:  https://www.patreon.com/MoonReal
► Follow my Twitter: https://twitter.com/MoonRealYT

Here's the truth about Temu.
```

## AI 原始标注

```json
{
  "内容分类": "视频/短视频",
  "情感分析": {
    "整体情感": "负面",
    "品牌维度": {
      "情感": "负面",
      "关键短语": "The Scummiest Company In The World, truth about Temu"
    },
    "产品维度": [
      {
        "产品名称": "TEMU（平台）",
        "情感": "负面",
        "关键短语": "Scummiest Company, truth about Temu"
      }
    ],
    "竞品维度": {
      "是否提及竞品": "否"
    }
  },
  "严重度评级": "P1",
  "严重度理由": "高危内容(标题极端负面指控'最卑鄙公司'，涉及品牌核心攻击)+高影响力(167万粉大V，播放131万，点赞3.8万)+已发布超2.5年无加速传播态势→高危×高影响力×衰减=P1(不满足P0条件：无安全事故/法律行动/监管介入/大规模传播中的品牌核心攻击，且已衰减)",
  "分流建议": "立即处理",
  "分流理由": "内容标题极端负面，发布者为167万粉大V，播放量超131万，虽已发布超2.5年但内容仍具长尾传播力，需法务和PR侧评估是否需要官方回应或法律行动，评论区出现对发布者虚伪的批评但未减轻对TEMU的负面指控",
  "真实性评估": {
    "判断": "无法判断",
    "信号": [
      "标题极端情绪化('Scummiest')",
      "视频为揭露类内容，缺少具体可验证细节",
      "发布者有赞助广告历史，立场存疑",
      "评论区有用户批评其虚伪"
    ]
  },
  "摘要": "167万粉YouTuber发布视频标题称TEMU为'最卑鄙公司'，播放131万，评论区出现对发布者虚伪的批评但未减轻对TEMU的负面指控",
  "风险标签": [
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
      "红": 0,
      "黄": 6,
      "绿": 4
    },
    "评论详情": [
      {
        "序号": 1,
        "内容": "Try out invideo AI for FREE here! ➡ https://invideo.io/i/moon",
        "情感": "中性",
        "关键短语": "发布者置顶赞助链接，中性"
      },
      {
        "序号": 2,
        "内容": "So you criticie scummy adverts ,, then promote another scummy ..... how ironic like still great vid but you get the point",
        "情感": "正面",
        "关键短语": "批评发布者虚伪，但肯定视频内容，正面"
      },
      {
        "序号": 3,
        "内容": "@sourlab He did multiple videos shilling established titles. The guy is the epitome of being a hypocrite given the themes/context of his videos.",
        "情感": "正面",
        "关键短语": "批评发布者虚伪，正面"
      },
      {
        "序号": 4,
        "内容": "@sourlab True, a lot of people will just close the video at that point thinking just how hypocritical this is.",
        "情感": "正面",
        "关键短语": "批评发布者虚伪，正面"
      },
      {
        "序号": 5,
        "内容": "These brands did not do their research lmao.",
        "情感": "中性",
        "关键短语": "调侃赞助商，中性"
      },
      {
        "序号": 6,
        "内容": "@sourlab You've seen the truth of politics, brother.",
        "情感": "中性",
        "关键短语": "无关内容，中性"
      },
      {
        "序号": 7,
        "内容": "@Mr_Schizo yup",
        "情感": "中性",
        "关键短语": "附和，中性"
      },
      {
        "序号": 8,
        "内容": "so, this channel is like a hypocrisy speedrun at 420%",
        "情感": "正面",
        "关键短语": "批评发布者虚伪，正面"
      },
      {
        "序号": 9,
        "内容": "@sourlab its litterally just a editing software 💀",
        "情感": "中性",
        "关键短语": "为赞助商辩护，中性"
      },
      {
        "序号": 10,
        "内容": "@zzSvinn they probably paid him like 200$ to sponsor them 💀",
        "情感": "中性",
        "关键短语": "调侃赞助费，中性"
      }
    ],
    "评论总结": "评论区主要批评发布者虚伪(一边批评TEMU一边接赞助)，但未质疑TEMU负面指控本身，整体风向偏中性"
  }
}
```

## 判据链

- **严重度判决**：高危内容(标题极端负面指控'最卑鄙公司'，涉及品牌核心攻击)+高影响力(167万粉大V，播放131万，点赞3.8万)+已发布超2.5年无加速传播态势→高危×高影响力×衰减=P1(不满足P0条件：无安全事故/法律行动/监管介入/大规模传播中的品牌核心攻击，且已衰减)
- **分流判决**：内容标题极端负面，发布者为167万粉大V，播放量超131万，虽已发布超2.5年但内容仍具长尾传播力，需法务和PR侧评估是否需要官方回应或法律行动，评论区出现对发布者虚伪的批评但未减轻对TEMU的负面指控
- **真实性判断**：无法判断
- **风险标签**：KOL负面, 大规模传播

## 边界讨论

- **P1 边界案例**：当前案例属于 P1 严重度，这是案例库的覆盖盲区，建议优先人工复核。
- **新平台**：「YouTube」在现有案例库中尚无覆盖，扩展了知识库的平台维度。

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

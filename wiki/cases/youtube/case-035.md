---
title: 案例035: YouTube视频无法访问，抓取失败，无有效舆情内容
type: case
created: 2026-05-28
severity: P3
action: 可忽略
platform: YouTube
source: auto_ingest
status: 待跟进
url: https://www.youtube.com/watch?v=UCkmEIhdd0mgRkDfGLz8BayQ
categories: [其他]

notes: 
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：
互动数据：点赞0, 播放0
时间：
链接：https://www.youtube.com/watch?v=UCkmEIhdd0mgRkDfGLz8BayQ

原文内容：
[抓取失败: ERROR: [youtube] UCkmEIhdd0m: Video unavailable]
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "内容抓取失败，无有效信息，无传播，无风险",
  "情感分析": {
    "整体情感": "中性"
  },
  "风险标签": [],
  "分流建议": "可忽略",
  "评论区分析": {
    "评论红绿灯": {
      "红": 0,
      "黄": 0,
      "绿": 1
    }
  },
  "舆情分类": [
    "其他"
  ],
  "摘要": "YouTube视频无法访问，抓取失败，无有效舆情内容"
}
```

## 判据链

- **严重度判决**：内容抓取失败，无有效信息，无传播，无风险
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：(无)

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

（无）

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

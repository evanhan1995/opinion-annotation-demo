---
title: 案例001: YouTube视频内容抓取失败，无有效文本，零互动，无舆情价值
type: case
created: 2026-05-27
severity: P3
action: 可忽略
platform: YouTube
source: auto_ingest
status: 处理中
url: https://www.youtube.com/watch?v=kJpgnywrLjc
categories: [其他]

notes: 自动化处置
tags: [auto_ingest, P3]
---

## 原始输入

```
平台：YouTube
发布者：
互动数据：点赞0, 播放0
时间：
链接：https://www.youtube.com/watch?v=kJpgnywrLjc

原文内容：
[抓取失败: 'NoneType' object is not subscriptable]
```

## AI 原始标注

```json
{
  "严重度评级": "P3",
  "严重度理由": "内容抓取失败，无有效信息，零互动，无传播风险",
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
  "摘要": "YouTube视频内容抓取失败，无有效文本，零互动，无舆情价值"
}
```

## 判据链

- **严重度判决**：内容抓取失败，无有效信息，零互动，无传播风险
- **分流判决**：(无)
- **真实性判断**：未评估
- **风险标签**：(无)

## 边界讨论

- 此案例落在现有规则覆盖范围内，无明显边界异常。

## 处置备注

自动化处置

## 对标注规范的影响

（自动标注案例。如后续人工纠偏确认了此标注，则规范无需调整；
如纠偏发现差异，则需根据差异类型更新对应决策规则。）

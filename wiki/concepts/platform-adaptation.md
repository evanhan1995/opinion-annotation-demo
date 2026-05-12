---
title: 平台特性适配
type: concept
created: 2026-05-11
updated: 2026-05-11
confidence: high
sources:
  - "[[sources/evan-dji-opinion-summary|DJI舆情系统]]"
  - "[[sources/evan-temu-opinion-summary|TEMU舆情体系]]"
related:
  - "[[concepts/severity-rating-matrix|严重度评级矩阵]]"
  - "[[concepts/sentiment-analysis-dimensions|多维度情感分析]]"
tags: [yq, platform]
---

# 平台特性适配

## 概述

不同社媒平台的内容形态、传播规律、用户画像差异显著。标注时需针对平台特性做判断标准微调。来自 DJI 对 YouTube/INS/TT 的海外平台操作经验。

## 六大平台适配表

| 平台 | 内容特点 | 影响力计算特殊性 |
|------|---------|-----------------|
| **YouTube** | 长视频+评论区；搜索长尾效应强 | 播放量+点赞+评论；粉丝量权重高 |
| **Instagram** | 图片/Reels；视觉驱动 | 点赞权重高（含水分，×0.7）；Reels传播性>静态 |
| **TikTok** | 短视频；病毒式传播 | 播放量**增速**>绝对值；跟拍/二创=升级信号 |
| **X (Twitter)** | 短文本；实时性强 | 转发权重最高；认证用户影响力+1级；**必须追溯线程全文** |
| **Reddit/论坛** | 长文讨论；社区文化强 | 子版块规模影响影响力；被downvote=社区纠正 |
| **新闻媒体** | 权威性；SEO影响大 | 媒体权威分级（全国>行业>地方）；转载监测 |

## 平台特定微调规则

### YouTube
- 长尾搜索流量≠实时传播，>1个月的内容降一级
- 大频道(≥100万粉)+负面 → 影响力+1级

### Instagram
- 点赞需打折（礼貌性点赞）
- Reels 影响力 > 静态帖子

### TikTok
- 前4小时播放>10万 → 发展态势自动标"加速传播"
- 跟拍/二创→严重度上调一级
- 收藏>1万→影响力上调

### X (Twitter)
- 蓝V/认证用户+负面→影响力+1级
- 必须追溯线程全文

### Reddit
- r/all 首页→影响力自动"高"
- 被downvote至≤0→影响力降级

### 新闻媒体
- 全国性头部→高影响力；行业垂直→中；地方→低
- 被转载后风险升级

## 平台无关通用原则

1. 多平台同类→取最高单平台影响力，但严重度上调一级
2. 跨平台传播链：TikTok→IG→YouTube→新闻媒体，约24-72h
3. 缺失平台数据→按"普通社媒"默认判断，标注 confidence:low

## 关联案例

- [[cases/case-001|001]]：X平台，记者/KOL→高影响力
- [[cases/case-002|002]]：Reddit，子版块讨论→中等互动
- [[cases/case-004|004]]：TikTok，收藏数→影响力指标
- [[cases/case-005|005]]：YouTube，大频道+长尾播放量

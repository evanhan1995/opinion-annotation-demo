---
title: 案例005：竞品对比公正评测 + 大V + 提及我方短板 → 持续观察
type: case
created: 2026-05-11
severity: P3
action: 持续观察
platform: YouTube
tags: [竞品, 混合情感, 大V, DJI, P3]
related_concepts:
  - "[[concepts/sentiment-analysis-dimensions|多维度情感分析]]"
  - "[[concepts/platform-adaptation|平台特性适配]]"
related_cases:
  - "[[cases/case-004|004-正面KOL]]"
  - "[[cases/case-002|002-质量讨论P2]]"
---

## 原始输入

```
平台：YouTube
发布者：科技评测频道，粉丝85万
内容："GoPro Hero 13 vs DJI Action 5 Pro: After 2 months of using both, here's my honest take. 
DJI wins on battery life and low light, no question. But GoPro still has the edge on 
image stabilization in extreme conditions and the accessory ecosystem is just bigger. 
Both are great cameras but serve slightly different users. 
Timestamps in description."
互动：播放量56万，点赞1.2万，评论2800
发布时间：2周前
```

## 标注输出

```json
{
  "内容分类": "视频/短视频",
  "情感分析": {
    "整体情感": "混合",
    "品牌维度": {"情感": "正面", "关键短语": "honest, great cameras"},
    "产品维度": [{"产品名称": "DJI Action 5 Pro", "情感": "正面", "关键短语": "wins on battery life and low light"}],
    "竞品维度": {
      "是否提及竞品": "是",
      "竞品名称": "GoPro Hero 13",
      "竞品情感": "正面",
      "与我方对比": "中性"
    }
  },
  "严重度评级": "P3",
  "严重度理由": "整体态度为中性偏正面+虽提及我方不足但评价客观且给出了正面优势→不构成负面舆情",
  "分流建议": "持续观察",
  "分流理由": "85万粉大V+56万播放具有显著影响力：(1)评论区可能出现对我方短板的集中讨论需监控；(2)产品短板是有效反馈可转产品团队；(3)整体公正无恶意，不需要处置介入",
  "真实性评估": {
    "判断": "大概率真实",
    "信号": ["专业评测频道", "长期使用(2个月)", "具体对比维度", "提供时间戳", "结论平衡非极端"]
  },
  "摘要": "85万粉科技频道对比Action 5 Pro与GoPro Hero 13，结论DJI续航和低光胜出，但防抖极端场景和配件生态不及GoPro，整体评价公正",
  "风险标签": [],
  "置信度": {"分类置信度": "高", "情感置信度": "高", "整体置信度": "中"}
}
```

## 判据链

1. **整体情感 = 混合**：既有正面(battery, low light)又有负面(stabilization, ecosystem)
2. **内容严重程度 = 无风险**：公正评测非恶意攻击
3. **为什么不是"可忽略"而是"持续观察"？**
   - 85万粉 + 56万播放 = 高影响力
   - 提及我方产品短板，评论区可能发酵
   - 产品团队可从中获取竞品情报

## 边界讨论

**最难判断的点：竞品对比中的"负面"算不算舆情负面？**
- **不算**。客观竞品对比是正常市场信息，不是需处置的"舆情"
- **除非**：出现明显踩一捧一、恶意扭曲事实、煽动性语言 → "竞品攻击"
- 本案例中"Both are great cameras"——这是公正评测的典型信号

**为什么整体置信度标"中"？**
- 混合情感的判断比纯正面/纯负面复杂，AI 更容易误判

## 对标注规范的影响

确认**竞品对比判定边界**：
1. 公正评测（有褒有贬、结论不极端）→ 不构成负面，但持续观察
2. 恶意对比（踩一捧一、煽动性、事实扭曲）→ 按负面评级
3. **区分判据**：平衡性语言 + 长期使用证据 + 结论是否极端

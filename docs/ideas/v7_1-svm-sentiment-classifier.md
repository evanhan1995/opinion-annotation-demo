# v7.1 SVM 情感分类器 — 实现规格

## Objective

用自有 KB 案例（91条 AI 标注）+ LLM 蒸馏训练 LinearSVC 分类器，替换 SnowNLP 在 `screen_content()` 中的位置。只在 `predict_proba > 0.85` 时触发 fast_track。

## grill-me 决议汇总

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 训练特征 | 案例 `原文内容` 区块文本 |
| 2 | 特征工程 | jieba 分词 + TF-IDF, `ngram_range=(1,2)`, `max_features=5000`, `min_df=2` |
| 3 | 模型 | `LinearSVC(C=1.0, max_iter=3000)` + `CalibratedClassifierCV(method='sigmoid')` |
| 4 | 置信度阈值 | `max(proba) > 0.85` → fast_track |
| 5 | 集成方式 | 替换 SnowNLP；SVM pkl 未加载时 fallback 到 SnowNLP |
| 6 | 加载时机 | Streamlit 启动时预加载 |
| 7 | 持久化 | `engine/sentiment_model.pkl` → `{"svm": ..., "vectorizer": ..., "labels": ["负面","中性","正面"]}` |
| 8 | 数据清洗 | 批处理脚本 `engine/sentiment_trainer.py` → `engine/seed_labels.csv` → Excel 人工审核 |

## 新依赖

`requirements.txt` 新增：
```
scikit-learn>=1.3.0
joblib>=1.3.0
```

## MVP Scope

**In (v7.1):**
- `agents/sentinel.py`:
  - `_train_svm_classifier(texts, labels)` 训练函数
  - `_load_sentiment_model()` 启动加载 pkl
  - `_ml_sentiment_predict(text)` 预测函数，返回 `(verdict, sentiment, proba)` 或 `None`
  - 修改 `screen_content()` — 规则后先调 SVM（可用时），不自信再调 SnowNLP，再不自信走 LLM
- `engine/sentiment_trainer.py` — 离线训练脚本：读案例 → 提取原文+标签 → jieba+TF-IDF → LinearSVC+CalibratedCV → joblib dump
- `engine/seed_labels.csv` — LLM 交叉验证输出：`原文 | 原AI标签 | LLM置信度(1-5) | LLM理由 | 人工修正标签`
- `tests/test_sentiment_ml.py` — ~8 个测试（训练/预测/阈值/fallback/持久化/多分类/空文本/置信度）
- `engine/sentiment_model.pkl` — 训练产物，gitignore

**Out (v7.1):**
- 不做在线学习/增量更新
- 不做多平台分模型
- 不做中性情感细分
- 不删除 SnowNLP 依赖

## screen_content() 新流程

```
screen_content(text, platform)
  ├─ apply_rules(text) → reject/fast_track/pass
  ├─ if pass:
  │    ├─ if model_loaded → _ml_sentiment_predict(text)
  │    │    └─ if proba > 0.85 → fast_track (建议情感/严重度)
  │    │    └─ else → _apply_snownlp(text)  # fallback
  │    └─ else → _apply_snownlp(text)  # model not loaded
  └─ return SentinelResult
```

## 文件清单

```
agents/sentinel.py              ← +_train_svm(), +_load_sentiment_model(), +_ml_sentiment_predict(), 改 screen_content() (~100行)
engine/sentiment_trainer.py     ← 新增：离线训练脚本 (~80行)
engine/sentiment_model.pkl      ← 新增：joblib序列化（gitignore）
engine/seed_labels.csv          ← 新增：LLM交叉验证中间产物
tests/test_sentiment_ml.py      ← 新增测试 (~60行)
requirements.txt               ← +scikit-learn, +joblib
```

## 训练数据管道

```
91条AI标注案例
  → engine/sentiment_trainer.py 提取原文+标签
    → LLM交叉验证（每条给置信度1-5+理由）→ engine/seed_labels.csv
      → 人工 Excel 审核修正 → engine/seed_labels_curated.csv
        → sentiment_trainer.py 训练：jieba分词 → TF-IDF → LinearSVC+CalibratedCV
          → joblib dump → engine/sentiment_model.pkl
```

## 成功标准

- [ ] 清洗后训练数据 >= 40 条
- [ ] SVM 在留出测试集上准确率 > SnowNLP 极端分数的准确率
- [ ] fast_track 触发率接近当前（33/72 = 46%）或合理
- [ ] `python -m pytest tests/ -x -q` 所有测试通过（187 + 新增 ~8 = 195+）
- [ ] 模型加载时间 < 100ms（不影响 Streamlit 启动）
- [ ] 模型未加载时 fallback 到原 SnowNLP 行为

## Commands

```
# 安装新依赖
pip install scikit-learn joblib

# 离线训练
python engine/sentiment_trainer.py

# 运行全部测试
python -m pytest tests/ -x -q
```

## Open Questions

- LLM 交叉验证用哪个模型？（DeepSeek 最便宜，建议 V4-Pro 和标注时模型一致）
- `seed_labels_curated.csv` 的审核周期？（建议积累到 >= 40 条清洗后标签就触发训练）
- 模型更新频率？（建议每月或积累 15+ 条新人工标注后重训）

# -*- coding: utf-8 -*-
"""v7.1: Offline SVM sentiment classifier training script.

Usage:
    python engine/sentiment_trainer.py              # train on all KB cases
    python engine/sentiment_trainer.py --csv engine/seed_labels_curated.csv  # train from curated CSV
    python engine/sentiment_trainer.py --cross-validate  # LLM cross-validation mode

The full pipeline:
  91 KB cases -> extract text+labels -> LLM cross-validation -> seed_labels.csv
    -> human Excel review -> seed_labels_curated.csv
      -> jieba + TF-IDF -> LinearSVC + CalibratedClassifierCV -> sentiment_model.pkl
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import engine._compat  # noqa: F401 — Windows UTF-8 adapter
import joblib
import jieba
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
MODEL_PATH = Path(__file__).resolve().parent / "sentiment_model.pkl"
SEED_CSV_PATH = Path(__file__).resolve().parent / "seed_labels.csv"


def _extract_content_from_case(md_text: str) -> str:
    """Extract the original post text from the 原始输入 code block."""
    # Find the 原文内容 section header
    match = re.search(r"原文内容：\s*\n(.*?)(?=\n\w+：|\n```)", md_text, re.DOTALL)
    if not match:
        return ""
    content = match.group(1).strip()
    # Remove leading "标题：" line if present
    content = re.sub(r"^标题：.*\n", "", content)
    return content.strip()


def _extract_sentiment_from_case(md_text: str) -> str:
    """Extract sentiment label from AI 原始标注 JSON block."""
    match = re.search(r'"整体情感"\s*:\s*"([^"]+)"', md_text)
    if not match:
        return ""
    label = match.group(1)
    if label in ("正面", "中性", "负面"):
        return label
    return ""


def _extract_platform_from_case(md_text: str) -> str:
    """Extract platform from frontmatter or 原始输入."""
    m = re.search(r"platform:\s*(\S+)", md_text)
    if m:
        return m.group(1)
    m = re.search(r"平台：(\S+)", md_text)
    return m.group(1) if m else ""


def _tokenize(text: str) -> list[str]:
    """Jieba tokenizer for TfidfVectorizer — must be module-level for pickle."""
    return list(jieba.cut(text[:1000]))


def load_cases(cases_dir: Path | None = None) -> list[dict]:
    """Load all cases from wiki/cases/, extracting text + sentiment + platform.

    Returns list of {"text": str, "sentiment": str, "platform": str, "source": str}.
    """
    if cases_dir is None:
        cases_dir = WIKI_DIR / "cases"

    cases = []
    for md_file in sorted(cases_dir.rglob("*.md")):
        try:
            raw = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        text = _extract_content_from_case(raw)
        sentiment = _extract_sentiment_from_case(raw)
        platform = _extract_platform_from_case(raw)

        if text and sentiment:
            cases.append({
                "text": text,
                "sentiment": sentiment,
                "platform": platform,
                "source": str(md_file.relative_to(cases_dir)),
            })

    return cases


def train_model(cases: list[dict], model_path: Path | None = None) -> dict:
    """Train LinearSVC + CalibratedClassifierCV on case data.

    Returns dict with model, vectorizer, labels, and evaluation metrics.
    """
    texts = [c["text"] for c in cases]
    y = [c["sentiment"] for c in cases]

    # Pre-tokenize with jieba (avoids pickle issues with custom tokenizer)
    tokenized = [" ".join(jieba.cut(t[:1000])) for t in texts]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(tokenized)

    # Map labels to consistent order
    label_order = ["负面", "中性", "正面"]
    y_encoded = [label_order.index(label) if label in label_order else 1 for label in y]

    # Train/test split for evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded,
    )

    svm = LinearSVC(C=1.0, max_iter=3000, random_state=42, dual="auto")
    model = CalibratedClassifierCV(svm, method="sigmoid", cv=5)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    report = classification_report(
        y_test, y_pred,
        target_names=label_order,
        zero_division=0,
    )

    if model_path is None:
        model_path = MODEL_PATH

    # Persist
    bundle = {
        "svm": model,
        "vectorizer": vectorizer,
        "labels": label_order,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    return {
        "model": model,
        "vectorizer": vectorizer,
        "labels": label_order,
        "n_cases": len(cases),
        "n_features": X.shape[1],
        "report": report,
        "model_path": str(model_path),
    }


def cross_validate_with_llm(cases: list[dict], model_name: str = "deepseek-chat") -> None:
    """Run LLM cross-validation on case labels, output seed_labels.csv.

    Uses engine/agent.py ask_agent for LLM calls.
    Writes CSV with columns: 原文 | 原AI标签 | LLM置信度(1-5) | LLM理由 | 人工修正标签
    """
    import csv

    from engine.agent import ask_agent
    from engine.annotate import load_config

    config = load_config()
    if not config or not config.get("api_key"):
        print("ERROR: No API key configured. Set api_key in config.json.")
        sys.exit(1)

    output_path = SEED_CSV_PATH
    rows = []

    for i, case in enumerate(cases):
        text = case["text"]
        label = case["sentiment"]
        platform = case.get("platform", "")

        prompt = (
            f"你是情感标注质量审查员。以下是一条社交媒体帖子的内容及AI标注的情感标签。\n\n"
            f"帖子内容：{text[:500]}\n"
            f"平台：{platform}\n"
            f"AI标注情感：{label}\n\n"
            f"请评估这个AI标注是否准确。回答格式：\n"
            f"置信度：[1-5，1=完全错误，5=完全正确]\n"
            f"正确情感：[正面/中性/负面]\n"
            f"理由：[一句话说明]"
        )

        try:
            result = ask_agent(prompt, config)
            answer = result.get("answer", "") if result else ""
        except Exception as e:
            answer = f"ERROR: {e}"

        # Parse LLM response
        conf_match = re.search(r"置信度.*?([1-5])", answer)
        correct_match = re.search(r"正确情感.*?(正面|中性|负面)", answer)
        reason_match = re.search(r"理由.*?[：:]\s*(.+)", answer)

        confidence = conf_match.group(1) if conf_match else "?"
        correct_label = correct_match.group(1) if correct_match else ""
        reason = reason_match.group(1) if reason_match else answer[:100]

        rows.append({
            "原文": text,
            "原AI标签": label,
            "LLM置信度(1-5)": confidence,
            "LLM理由": reason,
            "LLM建议标签": correct_label,
            "人工修正标签": "",
            "平台": platform,
        })

        print(f"[{i+1}/{len(cases)}] {label} → LLM置信度={confidence}, 建议={correct_label}")

    # Write CSV
    fieldnames = ["原文", "原AI标签", "LLM置信度(1-5)", "LLM理由", "LLM建议标签", "人工修正标签", "平台"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWritten {len(rows)} rows to {output_path}")
    print("Open in Excel, review flagged items (LLM置信度 < 4), fill 人工修正标签 column.")
    print("Save as seed_labels_curated.csv, then run: python engine/sentiment_trainer.py --csv seed_labels_curated.csv")


def train_from_csv(csv_path: str) -> None:
    """Train model from a curated CSV file (after human review)."""
    import csv

    cases = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("原文", "").strip()
            # Use manually corrected label if provided, otherwise original AI label
            label = row.get("人工修正标签", "").strip()
            if not label:
                label = row.get("原AI标签", "").strip()
            if text and label in ("正面", "中性", "负面"):
                cases.append({"text": text, "sentiment": label, "platform": "", "source": ""})

    if len(cases) < 10:
        print(f"ERROR: Only {len(cases)} valid cases found. Need at least 10 to train.")
        sys.exit(1)

    result = train_model(cases)
    print(f"Trained on {result['n_cases']} cases, {result['n_features']} features")
    print(f"Model saved to: {result['model_path']}")
    print(f"\nClassification report (20% test set):\n{result['report']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="v7.1 SVM Sentiment Trainer")
    parser.add_argument("--csv", type=str, help="Train from curated CSV file")
    parser.add_argument("--cross-validate", action="store_true", help="Run LLM cross-validation")
    parser.add_argument("--model", type=str, default="deepseek-chat", help="LLM model for cross-validation")
    args = parser.parse_args()

    if args.csv:
        train_from_csv(args.csv)
    elif args.cross_validate:
        cases = load_cases()
        print(f"Loaded {len(cases)} cases from KB")
        cross_validate_with_llm(cases, model_name=args.model)
    else:
        # Default: train on all KB cases directly
        cases = load_cases()
        print(f"Loaded {len(cases)} cases from KB")
        if len(cases) < 10:
            print(f"ERROR: Only {len(cases)} valid cases. Need at least 10.")
            sys.exit(1)
        result = train_model(cases)
        print(f"Trained on {result['n_cases']} cases, {result['n_features']} features")
        print(f"Model saved to: {result['model_path']}")
        print(f"\nClassification report (20% test set):\n{result['report']}")

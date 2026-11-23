"""Train on synthetic data; separate validation from a one-time final evaluation."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from imblearn.over_sampling import SMOTENC
from imblearn.pipeline import Pipeline
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

from ml.career_profiles import CAREERS
from config import PROJECT_ROOT
from ml.generate_data import DEFAULT_DATA_PATH, validate_dataset
from ml.preprocessing import FEATURE_COLUMNS, PREPROCESSING_CONFIG, prepare_dataset


DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "cpp_model.joblib"
RF_CONFIG = {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 2,
             "max_features": "sqrt", "n_jobs": -1}
SMOTE_NEIGHBORS = 5


def split_indices(frame: pd.DataFrame, seed: int = 42) -> dict[str, list[int]]:
    """Stratify 70/15/15 before fitting or oversampling; return disjoint positions."""
    if set(frame["career"]) != set(CAREERS):
        raise ValueError("Training data must contain all 12 career categories.")
    try:
        train, holdout = train_test_split(np.arange(len(frame)), test_size=.30, random_state=seed, stratify=frame["career"])
        validation, test = train_test_split(holdout, test_size=.50, random_state=seed, stratify=frame.iloc[holdout]["career"])
    except ValueError:
        raise ValueError("Dataset is too small for stratified 70/15/15 splits across 12 careers. Use 4000 rows; each training class needs at least 6 records for SMOTENC(k_neighbors=5).") from None
    counts = frame.iloc[train]["career"].value_counts()
    if counts.min() <= SMOTE_NEIGHBORS:
        raise ValueError("SMOTENC(k_neighbors=5) requires at least 6 TRAINING records per class after splitting. Increase the dataset (4000 rows recommended).")
    return {"train": train.tolist(), "validation": validation.tolist(), "test": test.tolist()}


def evaluate(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> dict:
    """Report synthetic classification quality using identical inference ranking."""
    probabilities = pipeline.predict_proba(X)
    labels = pipeline.classes_
    order = np.argsort(-probabilities, axis=1, kind="stable")
    predictions = labels[order[:, 0]]
    top3 = labels[order[:, :3]]
    return {
        "n_rows": len(y), "top1_accuracy": float(accuracy_score(y, predictions)),
        "top3_accuracy": float(np.mean(np.any(top3 == np.array(y)[:, None], axis=1))),
        "macro_f1": float(f1_score(y, predictions, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
        "per_class": classification_report(y, predictions, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y, predictions, labels=labels).tolist(),
        "class_order": labels.tolist(),
    }


def fit_model(frame: pd.DataFrame, seed: int = 42, *, forest_config: dict | None = None) -> dict:
    """Fit only the training partition. Validation is measured; test is not evaluated."""
    validate_dataset(frame)
    splits = split_indices(frame, seed)
    X_train = prepare_dataset(frame.iloc[splits["train"]])
    X_validation = prepare_dataset(frame.iloc[splits["validation"]])
    config = dict(RF_CONFIG if forest_config is None else forest_config)
    pipeline = Pipeline([
        ("smote", SMOTENC(categorical_features=list(range(14, 21)), random_state=seed, k_neighbors=SMOTE_NEIGHBORS)),
        ("forest", RandomForestClassifier(random_state=seed, **config)),
    ])
    pipeline.fit(X_train, frame.iloc[splits["train"]]["career"].to_numpy())
    return {
        "pipeline": pipeline, "feature_columns": list(FEATURE_COLUMNS),
        "classes": pipeline.classes_.tolist(), "preprocessing": PREPROCESSING_CONFIG,
        "seed": seed, "forest_config": config, "smote_neighbors": SMOTE_NEIGHBORS,
        "splits": splits, "split_counts": {name: len(indices) for name, indices in splits.items()},
        "train_class_counts": frame.iloc[splits["train"]]["career"].value_counts().to_dict(),
        "validation_metrics": evaluate(pipeline, X_validation, frame.iloc[splits["validation"]]["career"]),
        "feature_importance": dict(zip(FEATURE_COLUMNS, map(float, pipeline.named_steps["forest"].feature_importances_))),
        "versions": {name: version(name) for name in ("scikit-learn", "imbalanced-learn", "numpy", "pandas", "joblib")},
        "synthetic": True,
    }


def format_report(metrics: dict, importance: dict, title: str) -> str:
    """Explain metrics and retain full per-class results and confusion matrix."""
    class_order = metrics["class_order"]
    per_class = pd.DataFrame({label: metrics["per_class"][label] for label in class_order}).T
    matrix = pd.DataFrame(metrics["confusion_matrix"], index=class_order, columns=class_order)
    text = (
        f"{title}\nSYNTHETIC DATA ONLY — not evidence of real-world career suitability.\n"
        f"Rows: {metrics['n_rows']}\n"
        f"Top-1 accuracy: {metrics['top1_accuracy']:.2%}\n"
        f"Top-3 accuracy: {metrics['top3_accuracy']:.2%}\n"
        f"Macro F1: {metrics['macro_f1']:.4f}\n"
        f"Balanced accuracy: {metrics['balanced_accuracy']:.2%}\n\n"
        "Top-1 counts exact assigned-label matches. Top-3 checks whether the assigned label is among three results.\n"
        "Macro F1 gives each career equal weight. Balanced accuracy averages recall across careers.\n"
        "Precision asks how often a predicted class is correct; recall asks how many members of that class were found.\n"
        "Inspect minority classes (Mathematics and Environmental Science) rather than overall accuracy alone.\n\n"
        f"Per-class metrics:\n{per_class.to_string()}\n\n"
        f"Confusion matrix (rows = actual, columns = predicted):\n{matrix.to_string()}\n\n"
        "Forest impurity-based feature importance (descriptive, not causal; may favor continuous features):\n"
        + pd.Series(importance).sort_values(ascending=False).to_string()
    )
    if metrics["top1_accuracy"] > .90:
        text += "\n\nINVESTIGATE: top-1 exceeds 90%; synthetic separation may be too easy."
    if not (.60 <= metrics["top1_accuracy"] <= .80 and .85 <= metrics["top3_accuracy"] <= .95):
        text += "\n\nDiagnostic targets were not both achieved. Related profiles intentionally overlap; 8% atypical labels and missing subjects add ambiguity. Report these actual results, not a target score."
    return text


def save_reports(model: dict, metrics: dict, model_path: Path, split: str) -> None:
    """Write machine-readable and human-readable evaluation sidecars."""
    report = {"model_version": model["model_version"], "dataset_sha256": model["dataset_sha256"],
              "split": split, "synthetic": True, "metrics": metrics,
              "feature_importance": model["feature_importance"]}
    model_path.with_suffix(f".{split}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    model_path.with_suffix(f".{split}.txt").write_text(format_report(metrics, model["feature_importance"], split.upper()), encoding="utf-8")


def train(data_path: Path = DEFAULT_DATA_PATH, model_path: Path = DEFAULT_MODEL_PATH, seed: int = 42) -> dict:
    """Create a versioned artifact without accessing final-test predictions."""
    if model_path.exists() or model_path.with_suffix(".test.json").exists():
        raise ValueError("Model or final-test report already exists. Keep the finalized experiment; choose a new --model path for a separate experiment.")
    frame = pd.read_csv(data_path)
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    metadata_path = data_path.with_suffix(".metadata.json")
    if not metadata_path.exists():
        raise ValueError("Synthetic generation metadata is missing. Run generate_data.py first.")
    generator_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if generator_metadata.get("synthetic") is not True or generator_metadata.get("sha256") != digest:
        raise ValueError("Dataset does not match its generation metadata.")
    model = fit_model(frame, seed)
    model.update({"dataset_sha256": digest, "generator_metadata": generator_metadata,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "model_version": "cpp-rf-v1-" + hashlib.sha256((digest + str(seed) + json.dumps(RF_CONFIG, sort_keys=True)).encode()).hexdigest()[:16]})
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    save_reports(model, model["validation_metrics"], model_path, "validation")
    return model


def finalize(data_path: Path = DEFAULT_DATA_PATH, model_path: Path = DEFAULT_MODEL_PATH) -> dict:
    """Evaluate the saved model once on its untouched test partition; never retrain."""
    from ml.predict import load_model

    model = load_model(model_path)
    if hashlib.sha256(data_path.read_bytes()).hexdigest() != model["dataset_sha256"]:
        raise ValueError("Final-test dataset differs from the training dataset.")
    existing = model_path.with_suffix(".test.json")
    if existing.exists():
        report = json.loads(existing.read_text(encoding="utf-8"))
        if report["model_version"] != model["model_version"] or report["dataset_sha256"] != model["dataset_sha256"]:
            raise ValueError("Final-test report belongs to a different experiment.")
        return report["metrics"]  # Re-display recorded results; do not evaluate again.
    frame = pd.read_csv(data_path)
    test = frame.iloc[model["splits"]["test"]]
    metrics = evaluate(model["pipeline"], prepare_dataset(test), test["career"])
    save_reports(model, metrics, model_path, "test")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--finalize", action="store_true", help="Freeze decisions first, then evaluate held-out test data once.")
    args = parser.parse_args()
    try:
        if args.finalize:
            metrics = finalize(args.data, args.model)
            print(f"Recorded final test: top-1={metrics['top1_accuracy']:.2%}, top-3={metrics['top3_accuracy']:.2%}, macro F1={metrics['macro_f1']:.4f}, balanced accuracy={metrics['balanced_accuracy']:.2%}")
        else:
            model = train(args.data, args.model, args.seed)
            print(format_report(model["validation_metrics"], model["feature_importance"], "VALIDATION"))
            print("\nModel saved. Final test NOT evaluated. Review validation, freeze configuration, then use --finalize.")
    except (ValueError, OSError) as error:
        print(f"Training/evaluation failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

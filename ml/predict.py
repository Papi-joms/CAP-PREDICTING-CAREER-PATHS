"""Validated top-three classification outputs, never career-success probabilities."""

from importlib.metadata import version
from pathlib import Path
import pickle

from imblearn.pipeline import Pipeline
import joblib
import numpy as np

from ml.career_profiles import CAREERS
from config import PROJECT_ROOT
from ml.preprocessing import FEATURE_COLUMNS, PREPROCESSING_CONFIG, prepare_features


DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "cpp_model.joblib"
MATCH_SCORE_EXPLANATION = (
    "The displayed match scores represent the model's relative classification outputs "
    "based on the information provided. They are generated using a synthetic training "
    "dataset and should be treated as guidance, not as a guarantee of career suitability or future success."
)


def validate_model(model: dict) -> dict:
    """Reject incompatible artifact schemas instead of silently reordering inputs."""
    required = {"pipeline", "feature_columns", "classes", "preprocessing", "seed", "model_version", "versions"}
    if not isinstance(model, dict) or not required <= set(model):
        raise ValueError("Model artifact is missing required metadata.")
    if not isinstance(model["model_version"], str) or not model["model_version"].strip():
        raise ValueError("Model version is missing or invalid.")
    if model["feature_columns"] != list(FEATURE_COLUMNS) or model["preprocessing"] != PREPROCESSING_CONFIG:
        raise ValueError("Model preprocessing metadata is incompatible with this application.")
    pipeline = model["pipeline"]
    if not isinstance(pipeline, Pipeline) or not hasattr(pipeline, "classes_"):
        raise ValueError("Artifact does not contain a fitted imbalanced-learn pipeline.")
    if model["classes"] != pipeline.classes_.tolist() or set(model["classes"]) != set(CAREERS):
        raise ValueError("Model class metadata is inconsistent.")
    if list(pipeline.feature_names_in_) != model["feature_columns"]:
        raise ValueError("Pipeline feature ordering does not match its metadata.")
    for package in ("scikit-learn", "imbalanced-learn", "numpy", "pandas", "joblib"):
        if model["versions"].get(package) != version(package):
            raise ValueError(f"Model dependency mismatch for {package}; use the training environment versions.")
    return model


def load_model(path: Path = DEFAULT_MODEL_PATH) -> dict:
    """Load only a trusted locally generated joblib artifact; pickle can execute code."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("Trained model is missing. Complete Step 1C training first.")
    try:
        artifact = joblib.load(path)
    except (EOFError, pickle.UnpicklingError, ImportError, AttributeError, IndexError, KeyError, ValueError) as error:
        raise ValueError("Trained model could not be read. Restore the trusted model artifact and its matching dependencies.") from None
    return validate_model(artifact)


def load_streamlit_model(path: Path = DEFAULT_MODEL_PATH) -> dict:
    """Cache only the shared model resource, never student-specific results."""
    import streamlit as st

    # Defined lazily so command-line tools do not initialize Streamlit caching.
    @st.cache_resource(show_spinner=False)
    def cached_model(resolved_path: str, modified_ns: int, file_size: int) -> dict:
        return load_model(Path(resolved_path))

    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError("Trained model is missing. Complete Step 1C training first.")
    stat = resolved.stat()
    return cached_model(str(resolved), stat.st_mtime_ns, stat.st_size)


def predict_top3(features_dict: dict, *, model: dict | None = None) -> list[dict]:
    """Return three ordered match scores in [0,1], without renormalizing the top three."""
    artifact = load_model() if model is None else validate_model(model)
    features = prepare_features(features_dict, feature_columns=artifact["feature_columns"])
    probabilities = artifact["pipeline"].predict_proba(features)[0]
    if not np.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any() or not np.isclose(probabilities.sum(), 1):
        raise ValueError("Model returned invalid class scores.")
    order = np.argsort(-probabilities, kind="stable")[:3]
    return [{"rank": rank, "career": artifact["classes"][int(index)], "match_score": float(probabilities[index])}
            for rank, index in enumerate(order, start=1)]


if __name__ == "__main__":
    try:
        for recommendation in predict_top3({"gwa": 89, "answers": [3] * 30}):
            print(f"{recommendation['rank']}. {recommendation['career']}: {recommendation['match_score']:.2%}")
        print(MATCH_SCORE_EXPLANATION)
    except (ValueError, OSError) as error:
        print(f"Prediction failed: {error}")
        raise SystemExit(1)

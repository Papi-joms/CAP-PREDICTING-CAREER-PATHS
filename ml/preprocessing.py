"""One deterministic, non-learning transformation for training and prediction."""

from collections.abc import Mapping
from numbers import Real

import numpy as np
import pandas as pd

from validation import RIASEC_TYPES, SUBJECTS, score_riasec, validate_academics


SCORE_COLUMNS = tuple(f"riasec_{kind}" for kind in RIASEC_TYPES)
ANSWER_COLUMNS = tuple(f"{kind}{item}" for kind in RIASEC_TYPES for item in range(1, 6))
FEATURE_COLUMNS = ("gwa", *SCORE_COLUMNS, *SUBJECTS, *(f"{name}_missing" for name in SUBJECTS))
PREPROCESSING_CONFIG = {
    "version": "gwa-substitution-v1", "missing_strategy": "student_gwa",
    "grade_range": [75, 100], "score_range": [5, 25],
    "answer_order": list(ANSWER_COLUMNS), "feature_columns": list(FEATURE_COLUMNS),
}


def _is_missing(value: object) -> bool:
    """Treat CSV NaN as an absent optional grade, but never as a valid GWA."""
    return value is None or (isinstance(value, str) and not value.strip()) or (
        isinstance(value, Real) and not isinstance(value, bool) and np.isnan(value)
    )


def prepare_features(features: Mapping, *, feature_columns=None) -> pd.DataFrame:
    """Validate one profile and return exactly 21 ordered numeric features.

    Supply gwa, optional subject keys, and either answers or riasec_scores (a
    mapping keyed R/I/A/S/E/C). If both are supplied they must agree. Inference
    passes the saved artifact's feature order; incompatible schemas fail closed.
    """
    if not isinstance(features, Mapping):
        raise ValueError("Student features must be a mapping.")
    allowed = {"gwa", "answers", "riasec_scores", *SUBJECTS}
    if set(features) - allowed:
        raise ValueError("Unrecognized student feature key.")
    order = list(FEATURE_COLUMNS if feature_columns is None else feature_columns)
    if order != list(FEATURE_COLUMNS):
        raise ValueError("Saved feature metadata is incompatible with preprocessing.")
    subjects = {name: None if _is_missing(features.get(name)) else features[name] for name in SUBJECTS}
    academics = validate_academics(features.get("gwa"), subjects)
    scores = None
    if "answers" in features:
        scores = score_riasec(features["answers"])
    if "riasec_scores" in features:
        supplied = features["riasec_scores"]
        if not isinstance(supplied, Mapping) or set(supplied) != set(RIASEC_TYPES):
            raise ValueError("Supply exactly the six RIASEC scores.")
        if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
               or not np.isfinite(value) or value != int(value) or not 5 <= value <= 25
               for value in supplied.values()):
            raise ValueError("RIASEC scores must be whole numbers from 5 to 25.")
        supplied = {key: int(value) for key, value in supplied.items()}
        if scores is not None and scores != supplied:
            raise ValueError("RIASEC scores do not match the original answers.")
        scores = supplied
    if scores is None:
        raise ValueError("Complete RIASEC answers or six validated scores are required.")
    row = {"gwa": float(academics["gwa"])}
    row.update({f"riasec_{key}": value for key, value in scores.items()})
    for name in SUBJECTS:
        missing = academics[name] is None
        row[name] = row["gwa"] if missing else float(academics[name])
        row[f"{name}_missing"] = int(missing)
    return pd.DataFrame([row], columns=order, dtype=float)


def prepare_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    """Use the same single-student transformation for every dataset row."""
    required = {"gwa", *SUBJECTS, *ANSWER_COLUMNS, *SCORE_COLUMNS}
    if not required <= set(frame.columns) or frame.empty:
        raise ValueError("Dataset is empty or missing required input columns.")
    rows = []
    for row in frame.to_dict("records"):
        raw = [row[name] for name in ANSWER_COLUMNS]
        if any(isinstance(value, bool) or not isinstance(value, Real)
               or not np.isfinite(value) or value != int(value) for value in raw):
            raise ValueError("Dataset answers must be integers.")
        features = {"gwa": row["gwa"], **{name: row[name] for name in SUBJECTS},
                    "answers": [int(value) for value in raw],
                    "riasec_scores": {kind: row[f"riasec_{kind}"] for kind in RIASEC_TYPES}}
        rows.append(prepare_features(features))
    return pd.concat(rows, ignore_index=True)

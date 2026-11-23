"""Training and prediction must agree on GWA filling, indicators, and ordering."""

import numpy as np
import pandas as pd
import pytest

from ml.generate_data import generate_students
from ml.preprocessing import ANSWER_COLUMNS, FEATURE_COLUMNS, prepare_dataset, prepare_features
from validation import SUBJECTS


def test_gwa_substitution_and_actual_grade_indicator():
    row = prepare_features({"gwa": 89, "physics": 89, "chemistry": np.nan, "answers": [3] * 30})
    assert list(row.columns) == list(FEATURE_COLUMNS)
    assert row.shape == (1, 21)
    assert row.loc[0, "physics"] == row.loc[0, "chemistry"] == 89
    assert row.loc[0, "physics_missing"] == 0
    assert row.loc[0, "chemistry_missing"] == 1
    assert row.loc[0, "riasec_R"] == 15


def test_training_and_single_prediction_identical():
    data = generate_students(10)
    batch = prepare_dataset(data)
    for index, record in enumerate(data.to_dict("records")):
        single = prepare_features({"gwa": record["gwa"], **{name: record[name] for name in SUBJECTS},
                                   "answers": [record[name] for name in ANSWER_COLUMNS]})
        pd.testing.assert_frame_equal(batch.iloc[[index]].reset_index(drop=True), single)


@pytest.mark.parametrize("features", [
    {"gwa": np.nan, "answers": [3] * 30}, {"gwa": 101, "answers": [3] * 30},
    {"gwa": 89, "answers": [3] * 29}, {"gwa": 89, "physics": "bad", "answers": [3] * 30},
    {"gwa": 89, "riasec_scores": dict.fromkeys("RIASEC", 26)},
    {"gwa": 89, "riasec_scores": dict.fromkeys("RIASEC", True)},
    {"gwa": 89, "answers": [3] * 30, "riasec_scores": dict.fromkeys("RIASEC", 16)},
    {"gwa": 89, "answers": [3] * 30, "career": "Nursing"},
])
def test_invalid_inputs_rejected(features):
    with pytest.raises(ValueError):
        prepare_features(features)


def test_score_only_input_and_feature_order_guard():
    assert prepare_features({"gwa": 89, "riasec_scores": dict.fromkeys("RIASEC", 15)}).shape == (1, 21)
    with pytest.raises(ValueError):
        prepare_features({"gwa": 89, "answers": [3] * 30}, feature_columns=list(reversed(FEATURE_COLUMNS)))


def test_corrupt_dataset_scores_rejected():
    data = generate_students(10)
    data.loc[0, "riasec_R"] = 99
    with pytest.raises(ValueError):
        prepare_dataset(data)

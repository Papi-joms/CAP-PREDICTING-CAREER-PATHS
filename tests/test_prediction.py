"""Use a small isolated model, never the final experiment's held-out test set."""

from copy import deepcopy
import hashlib
import json

import joblib
import numpy as np
import pytest

from ml.career_profiles import CAREERS
from ml.generate_data import generate_students
from ml.predict import load_model, predict_top3
from ml.preprocessing import FEATURE_COLUMNS, prepare_features
from ml.train_model import finalize, fit_model, split_indices, train


@pytest.fixture(scope="module")
def model():
    result = fit_model(generate_students(600), forest_config={"n_estimators": 24, "min_samples_leaf": 2, "n_jobs": 1})
    result["model_version"] = "isolated-unit-test"
    return result


def test_load_and_predict_three_ordered_valid_results(model, tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)
    loaded = load_model(path)
    features = {"gwa": 89, "answers": [3] * 30}
    results = predict_top3(features, model=loaded)
    assert [result["rank"] for result in results] == [1, 2, 3]
    assert len({result["career"] for result in results}) == 3
    assert all(result["career"] in CAREERS for result in results)
    scores = [result["match_score"] for result in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= score <= 1 for score in scores)
    expected = loaded["pipeline"].predict_proba(prepare_features(features))[0]
    assert np.allclose(scores, np.sort(expected)[::-1][:3])


def test_splits_and_features_exclude_target_leakage(model):
    splits = model["splits"]
    assert {key: len(value) for key, value in splits.items()} == {"train": 420, "validation": 90, "test": 90}
    assert not set(splits["train"]) & set(splits["validation"])
    assert not set(splits["train"]) & set(splits["test"])
    assert not set(splits["validation"]) & set(splits["test"])
    assert set().union(*map(set, splits.values())) == set(range(600))
    assert model["feature_columns"] == list(FEATURE_COLUMNS)
    assert not {"career", "student_id", "is_atypical"} & set(FEATURE_COLUMNS)
    # sampling_strategy_ reports additions relative to TRAIN counts, not all rows.
    counts = model["train_class_counts"]
    for label, additions in model["pipeline"].named_steps["smote"].sampling_strategy_.items():
        assert additions == max(counts.values()) - counts[label]
    assert list(model["pipeline"].named_steps["smote"].categorical_features_) == list(range(14, 21))
    assert "test_metrics" not in model


def test_artifact_schema_and_class_mismatch_rejected(model):
    broken = deepcopy(model)
    broken["feature_columns"] = list(reversed(FEATURE_COLUMNS))
    with pytest.raises(ValueError):
        predict_top3({"gwa": 89, "answers": [3] * 30}, model=broken)
    broken = deepcopy(model)
    broken["classes"] = list(reversed(broken["classes"]))
    with pytest.raises(ValueError):
        predict_top3({"gwa": 89, "answers": [3] * 30}, model=broken)


def test_small_dataset_explains_minority_requirement():
    with pytest.raises(ValueError, match="6|small"):
        split_indices(generate_students(100))


def test_missing_artifact_has_actionable_error(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        load_model(tmp_path / "absent.joblib")


@pytest.mark.parametrize("contents", [b"", b"not a valid model"])
def test_damaged_artifact_has_actionable_error(tmp_path, contents):
    path = tmp_path / "damaged.joblib"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="Restore the trusted model"):
        load_model(path)


def test_final_report_is_reused_without_reevaluation(model, tmp_path, monkeypatch):
    data_path = tmp_path / "students.csv"
    generate_students(600).to_csv(data_path, index=False)
    saved = dict(model, dataset_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest())
    model_path = tmp_path / "test-model.joblib"
    joblib.dump(saved, model_path)
    metrics = finalize(data_path, model_path)
    assert metrics["n_rows"] == 90
    assert model_path.with_suffix(".test.json").is_file()
    def forbidden(*args, **kwargs):
        raise AssertionError("Final test must not be evaluated again")
    monkeypatch.setattr("ml.train_model.evaluate", forbidden)
    assert finalize(data_path, model_path) == metrics
    data_path.write_text("different dataset", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        finalize(data_path, model_path)


def test_training_preserves_existing_artifact(tmp_path):
    artifact = tmp_path / "existing.joblib"
    artifact.write_bytes(b"existing experiment")
    with pytest.raises(ValueError, match="already exists"):
        train(tmp_path / "missing.csv", artifact)
    assert artifact.read_bytes() == b"existing experiment"


def test_training_requires_matching_synthetic_provenance(tmp_path):
    data = tmp_path / "students.csv"
    generate_students(20).to_csv(data, index=False)
    with pytest.raises(ValueError, match="metadata is missing"):
        train(data, tmp_path / "new.joblib")
    data.with_suffix(".metadata.json").write_text(json.dumps({"synthetic": True, "sha256": "wrong"}), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        train(data, tmp_path / "new.joblib")

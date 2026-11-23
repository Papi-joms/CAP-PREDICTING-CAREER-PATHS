"""Reviewed submission, inference failures, and persistent-history presentation."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from config import PROJECT_ROOT
from database import db
from ml import predict
from ui.riasec import QUESTIONS
from ui.student_inputs import DRAFT_KEY, RUN_KEY, STAGE_KEY


@pytest.fixture
def prediction_app(monkeypatch):
    identity = {"user_id": 1, "username": "prediction_test", "role": db.STUDENT}
    monkeypatch.setattr(db, "get_user_identity", lambda user_id: dict(identity) if user_id == 1 else None)
    monkeypatch.setattr(db, "get_student_record", lambda actor, target: {"profile": None, "riasec": None})
    runs = []
    monkeypatch.setattr(db, "get_prediction_history", lambda actor, target: deepcopy(list(reversed(runs))))
    save_only = MagicMock()
    monkeypatch.setattr(db, "save_student_inputs", save_only)
    results = [{"rank": 1, "career": "Computer Science", "match_score": .40},
               {"rank": 2, "career": "Information Technology", "match_score": .30},
               {"rank": 3, "career": "Mathematics", "match_score": .15}]
    load = MagicMock(return_value={"model_version": "ui-test-model"})
    infer = MagicMock(return_value=results)
    monkeypatch.setattr(predict, "load_streamlit_model", load)
    monkeypatch.setattr(predict, "predict_top3", infer)
    def save(actor, target, features, recommendations, model_version):
        assert actor == target == identity["user_id"]
        snapshot, validated = db._prediction_payload(features, recommendations, model_version)
        run_id = len(runs) + 1
        runs.append({"prediction_run_id": run_id, "input_snapshot": snapshot, "model_version": model_version,
                     "created_at": datetime(2026, 11, 23, 12, 0, run_id),
                     "recommendations": [{"rank": item["rank"], "career": item["career"], "probability": item["match_score"]} for item in validated]})
        return run_id
    save_run = MagicMock(side_effect=save)
    monkeypatch.setattr(db, "save_prediction_run", save_run)
    app = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=20)
    app.session_state[auth.IDENTITY_KEY] = dict(identity)
    app.run()
    assert not app.exception
    app.number_input(key="input_gwa").set_value(89.0)
    for question in QUESTIONS:
        app.radio(key=f"input_{question['id']}").set_value(3)
    return app, runs, load, infer, save_run, save_only, identity


def press(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_generation_requires_review_and_does_not_repeat_on_rerun(prediction_app):
    app, runs, load, infer, save_run, save_only, _ = prediction_app
    assert not any(button.label == "Generate recommendations" for button in app.button)
    press(app, "Review my information")
    infer.assert_not_called()
    press(app, "Generate recommendations")
    assert app.session_state[STAGE_KEY] == "results"
    assert len(runs) == 1
    load.assert_called_once()
    infer.assert_called_once()
    save_run.assert_called_once()
    save_only.assert_not_called()
    assert all(value is None for value in runs[0]["input_snapshot"]["subjects"].values())
    assert predict.MATCH_SCORE_EXPLANATION in [item.value for item in app.info]
    assert "40.00% match score" in " ".join(item.value for item in app.markdown)
    app.run()
    assert len(runs) == 1 and infer.call_count == 1


def test_edit_resubmit_keeps_old_snapshot_and_scores(prediction_app):
    app, runs, _, _, _, _, _ = prediction_app
    press(app, "Review my information")
    press(app, "Generate recommendations")
    first_run = deepcopy(runs[0])
    press(app, "Review and update my information")
    app.number_input(key="input_gwa").set_value(92.5)
    app.number_input(key="input_physics").set_value(95.0)
    app.radio(key="input_R1").set_value(5)
    press(app, "Review my information")
    press(app, "Generate recommendations")
    assert len(runs) == 2 and runs[0] == first_run
    assert runs[1]["input_snapshot"]["gwa"] == 92.5
    assert runs[1]["input_snapshot"]["answers"][0] == 5
    assert app.session_state[RUN_KEY] == 2
    app.selectbox(key=RUN_KEY).select(1).run()
    assert not app.exception
    assert "differ from your current profile" in app.warning[0].value
    assert app.metric[0].value == "89.00"
    assert runs[0] == first_run
    # An explicit new submission still creates a run when inputs are unchanged.
    press(app, "Review current information for another prediction")
    press(app, "Generate recommendations")
    assert len(runs) == 3
    assert runs[1]["input_snapshot"] == runs[2]["input_snapshot"]


@pytest.mark.parametrize("failure", ["model", "database"])
def test_prediction_failure_preserves_review_and_does_not_save_partial_inputs(prediction_app, failure):
    app, runs, load, infer, save_run, save_only, _ = prediction_app
    press(app, "Review my information")
    original = deepcopy(app.session_state[DRAFT_KEY])
    if failure == "model":
        load.side_effect = ValueError("Model missing or incompatible.")
    else:
        save_run.side_effect = db.DatabaseError("Transaction rolled back.")
    press(app, "Generate recommendations")
    assert "could not be generated and saved" in app.error[0].value
    assert app.session_state[STAGE_KEY] == "review"
    assert app.session_state[DRAFT_KEY] == original
    assert not runs
    save_only.assert_not_called()
    if failure == "model":
        infer.assert_not_called()
        save_run.assert_not_called()


def test_save_only_after_edit_preserves_previous_results(prediction_app):
    app, runs, _, infer, _, save_only, _ = prediction_app
    press(app, "Review my information")
    press(app, "Generate recommendations")
    first_run = deepcopy(runs[0])
    press(app, "Review and update my information")
    app.number_input(key="input_gwa").set_value(94.0)
    press(app, "Review my information")
    press(app, "Save without generating")
    save_only.assert_called_once()
    assert runs == [first_run]
    assert infer.call_count == 1
    assert "differ from your current profile" in app.warning[0].value


def test_role_change_before_prediction_cannot_write(prediction_app):
    app, runs, load, infer, save_run, _, identity = prediction_app
    press(app, "Review my information")
    identity["role"] = db.COUNSELOR
    press(app, "Generate recommendations")
    assert not runs
    load.assert_not_called()
    infer.assert_not_called()
    save_run.assert_not_called()

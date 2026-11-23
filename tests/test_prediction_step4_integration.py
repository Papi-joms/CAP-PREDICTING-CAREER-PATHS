"""Use the selected model with real MySQL; temporary prediction runs roll back."""

from copy import deepcopy
import os
from uuid import uuid4

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from config import PROJECT_ROOT
from database import db
from ml.predict import load_model, load_streamlit_model, predict_top3
from ui.riasec import QUESTIONS
from ui.student_inputs import RUN_KEY


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("CPP_RUN_DB_TESTS") != "1", reason="Set CPP_RUN_DB_TESTS=1 for local MySQL checks.",
)]


def press(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_actual_model_student_resubmission_and_saved_history(monkeypatch):
    connection = db._connect()
    username = "test_" + uuid4().hex
    password = uuid4().hex
    class RollbackOnlyConnection:
        def cursor(self):
            return connection.cursor()
        def commit(self):
            pass
        def rollback(self):
            connection.rollback()
        def close(self):
            pass
    try:
        with monkeypatch.context() as patch:
            patch.setattr(db, "_connect", RollbackOnlyConnection)
            user_id = auth.register_student(username, password, password)
            identity = auth.login({}, username, password)
            app = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=30)
            app.session_state[auth.IDENTITY_KEY] = identity
            app.run()
            app.number_input(key="input_gwa").set_value(88.5)
            for question in QUESTIONS:
                app.radio(key=f"input_{question['id']}").set_value(3)
            press(app, "Review my information")
            assert db.get_prediction_history(user_id, user_id) == []
            press(app, "Generate recommendations")
            first = deepcopy(db.get_prediction_history(user_id, user_id)[0])
            assert len(first["recommendations"]) == 3
            snapshot = first["input_snapshot"]
            expected = predict_top3({"gwa": snapshot["gwa"], **snapshot["subjects"], "answers": snapshot["answers"]})
            for saved, result in zip(first["recommendations"], expected):
                assert saved["career"] == result["career"]
                assert np.isclose(saved["probability"], result["match_score"])
            press(app, "Review and update my information")
            app.number_input(key="input_gwa").set_value(95.0)
            app.radio(key="input_R1").set_value(5)
            press(app, "Review my information")
            press(app, "Generate recommendations")
            history = db.get_prediction_history(user_id, user_id)
            assert len(history) == 2
            assert history[1] == first
            assert history[0]["prediction_run_id"] != first["prediction_run_id"]
            assert history[0]["input_snapshot"]["gwa"] == 95.0
            assert history[0]["input_snapshot"]["answers"][0] == 5
            assert float(db.get_student_record(user_id, user_id)["profile"]["gwa"]) == 95.0
            # A new session retrieves persisted history, not temporary UI results.
            reopened = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=30)
            reopened.session_state[auth.IDENTITY_KEY] = identity
            reopened.run()
            assert not reopened.exception
            assert len(reopened.selectbox(key=RUN_KEY).options) == 2
            press(app, "Review current information for another prediction")
            press(app, "Generate recommendations")
            assert len(db.get_prediction_history(user_id, user_id)) == 3
    finally:
        connection.rollback()
        connection.close()
    assert db.get_login_record(username) is None


def test_demo_snapshot_reproduces_recorded_scores_without_new_write():
    account = db.get_login_record(db.DEMO_STUDENT)
    assert account is not None
    history = db.get_prediction_history(account["user_id"], account["user_id"])
    model = load_model()
    run = next(run for run in history if run["model_version"] == model["model_version"])
    snapshot = run["input_snapshot"]
    expected = predict_top3({"gwa": snapshot["gwa"], **snapshot["subjects"], "answers": snapshot["answers"]}, model=model)
    assert len(run["recommendations"]) == 3
    for saved, result in zip(run["recommendations"], expected):
        assert saved["career"] == result["career"]
        assert np.isclose(saved["probability"], result["match_score"])
    assert db.get_prediction_history(account["user_id"], account["user_id"]) == history


def test_resource_loader_reuses_model_object():
    assert load_streamlit_model() is load_streamlit_model()

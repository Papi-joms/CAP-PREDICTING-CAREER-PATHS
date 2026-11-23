"""Opt-in real MySQL form saving; all temporary student rows roll back."""

import os
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from config import PROJECT_ROOT
from database import db
from ui.riasec import QUESTIONS


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("CPP_RUN_DB_TESTS") != "1", reason="Set CPP_RUN_DB_TESTS=1 for local MySQL checks.",
)]


def test_live_review_save_reload_and_incomplete_rejection(monkeypatch):
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
            app = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=20)
            app.session_state[auth.IDENTITY_KEY] = identity
            app.run()
            app.number_input(key="input_gwa").set_value(91.25)
            next(button for button in app.button if button.label == "Review my information").click().run()
            assert not app.exception
            assert db.get_student_record(user_id, user_id)["profile"] is None
            for question in QUESTIONS:
                app.radio(key=f"input_{question['id']}").set_value(4)
            app.number_input(key="input_physics").set_value(93.5)
            next(button for button in app.button if button.label == "Review my information").click().run()
            assert not app.exception
            assert db.get_student_record(user_id, user_id)["profile"] is None
            next(button for button in app.button if button.label == "Save without generating").click().run()
            assert not app.exception
            record = db.get_student_record(user_id, user_id)
            assert float(record["profile"]["gwa"]) == 91.25
            assert float(record["profile"]["physics"]) == 93.5
            assert record["profile"]["chemistry"] is None
            assert record["riasec"]["answers"] == [4] * 30
            assert record["riasec"]["scores"] == dict.fromkeys("RIASEC", 20)
            assert db.get_prediction_history(user_id, user_id) == []
            reopened = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=20)
            reopened.session_state[auth.IDENTITY_KEY] = identity
            reopened.run()
            assert not reopened.exception
            assert any(button.label == "Review and update my information" for button in reopened.button)
    finally:
        connection.rollback()
        connection.close()
    assert db.get_login_record(username) is None

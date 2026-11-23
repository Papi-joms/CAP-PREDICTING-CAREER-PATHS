"""Report privacy, empty states, student switching, and immutable history UI."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from database import db
from config import PROJECT_ROOT
from validation import SUBJECTS


@pytest.fixture
def report_data(monkeypatch):
    identity = {"user_id": 10, "username": "counselor", "role": db.COUNSELOR}
    monkeypatch.setattr(db, "get_user_identity", lambda value: dict(identity))
    monkeypatch.setattr(db, "list_students", lambda actor: [
        {"user_id": 1, "username": "student_one"}, {"user_id": 2, "username": "student_two"}])
    profile = {"gwa": 94.0, **{name: None for name in SUBJECTS}}
    records = {1: {"student": {"username": "student_one"}, "profile": profile,
                   "riasec": {"is_complete": True, "answers": [3] * 30}},
               2: {"student": {"username": "student_two"}, "profile": None, "riasec": None}}
    run = {"prediction_run_id": 5, "created_at": datetime(2026, 11, 23), "model_version": "test-model",
           "input_snapshot": {"gwa": 89.0, "subjects": {name: None for name in SUBJECTS}, "answers": [4] * 30},
           "recommendations": [{"rank": 1, "career": "Computer Science", "probability": .4},
                               {"rank": 2, "career": "Information Technology", "probability": .3},
                               {"rank": 3, "career": "Mathematics", "probability": .1}]}
    read = MagicMock(side_effect=lambda actor, target: deepcopy(records[target]))
    history = MagicMock(side_effect=lambda actor, target: [deepcopy(run)] if target == 1 else [])
    monkeypatch.setattr(db, "get_student_record", read)
    monkeypatch.setattr(db, "get_prediction_history", history)
    write = MagicMock(side_effect=AssertionError("Reports must not write"))
    monkeypatch.setattr(db, "save_student_inputs", write)
    monkeypatch.setattr(db, "save_prediction_run", write)
    app = AppTest.from_file(str(PROJECT_ROOT / "pages/2_Counselor_Dashboard.py"), default_timeout=20)
    app.session_state[auth.IDENTITY_KEY] = dict(identity)
    return app, identity, read, history, write


def test_counselor_switches_students_without_leaking_prior_report(report_data):
    app, _, read, history, write = report_data
    app.run()
    assert not app.exception
    assert [item.value for item in app.metric] == ["94.00", "89.00"]
    assert "differ" in app.warning[0].value
    assert "40.00% match score" in " ".join(item.value for item in app.markdown)
    assert not app.button and not app.number_input and not app.radio
    app.selectbox(key="counselor_report_student").select(2).run()
    assert not app.exception and not app.metric
    assert not any("Computer Science" in item.value for item in app.markdown)
    assert any("Not completed" in item.value for item in app.info)
    assert any("No prediction runs" in item.value for item in app.info)
    read.assert_called_with(10, 2)
    history.assert_called_with(10, 2)
    write.assert_not_called()


def test_student_cannot_open_counselor_page(report_data):
    app, identity, read, history, _ = report_data
    identity["role"] = db.STUDENT
    app.session_state[auth.IDENTITY_KEY] = dict(identity)
    app.run()
    assert not app.exception and app.error
    read.assert_not_called()
    history.assert_not_called()


def test_student_report_uses_authenticated_owner_not_selection_state(report_data, monkeypatch):
    _, identity, read, history, _ = report_data
    identity.update(user_id=1, role=db.STUDENT, username="student_one")
    # Render the real report page with only the navigation link stubbed out;
    # isolated AppTest pages do not have the entry point's navigation registry.
    monkeypatch.setattr("streamlit.page_link", lambda *args, **kwargs: None)
    app = AppTest.from_file(str(PROJECT_ROOT / "pages/3_Student_Report.py"), default_timeout=20)
    app.session_state[auth.IDENTITY_KEY] = dict(identity)
    app.session_state["counselor_report_student"] = 2
    app.run()
    assert not app.exception
    read.assert_called_once_with(1, 1)
    history.assert_called_once_with(1, 1)
    assert not any(box.label == "Select a student" for box in app.selectbox)


def test_report_denial_displays_no_partial_profile(report_data):
    app, _, _, history, _ = report_data
    history.side_effect = db.AuthorizationError("Access denied.")
    app.run()
    assert not app.exception and not app.metric
    assert "Report could not be loaded" in app.error[0].value


def test_empty_student_list(report_data, monkeypatch):
    app, _, read, _, _ = report_data
    monkeypatch.setattr(db, "list_students", lambda actor: [])
    app.run()
    assert not app.exception and not app.selectbox
    assert any("No student accounts" in item.value for item in app.info)
    read.assert_not_called()


def test_deleted_student_selection_resets(report_data):
    app, _, read, _, _ = report_data
    app.session_state["counselor_report_student"] = 999
    app.run()
    assert not app.exception
    read.assert_called_with(10, 1)

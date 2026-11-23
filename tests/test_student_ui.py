"""Exercise the student form, validation, review, editing, and retry behavior."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from config import PROJECT_ROOT
from database import db
from ui.riasec import QUESTIONS
from ui.student_inputs import DRAFT_KEY, STAGE_KEY


@pytest.fixture
def student_app(monkeypatch):
    identity = {"user_id": 1, "username": "student_test", "role": db.STUDENT}
    monkeypatch.setattr(db, "get_user_identity", lambda user_id: dict(identity) if user_id == 1 else None)
    monkeypatch.setattr(db, "get_student_record", lambda actor, target: {"profile": None, "riasec": None})
    monkeypatch.setattr(db, "get_prediction_history", lambda actor, target: [])
    save = MagicMock()
    monkeypatch.setattr(db, "save_student_inputs", save)
    app = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=20)
    app.session_state[auth.IDENTITY_KEY] = identity
    app.run()
    assert not app.exception
    return app, save


def press(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def fill_complete_form(app):
    app.number_input(key="input_gwa").set_value(89.12)
    for question in QUESTIONS:
        app.radio(key=f"input_{question['id']}").set_value(3)


def test_new_student_has_no_preselected_answers(student_app):
    app, save = student_app
    assert len(app.number_input) == 8
    assert len(app.radio) == 30
    assert all(widget.value is None for widget in app.number_input)
    assert all(widget.value is None for widget in app.radio)
    save.assert_not_called()


def test_incomplete_form_stays_on_input_and_preserves_draft(student_app):
    app, save = student_app
    press(app, "Review my information")
    assert "GWA is required" in app.error[0].value
    app.number_input(key="input_gwa").set_value(89.12)
    app.radio(key="input_R1").set_value(4)
    press(app, "Review my information")
    assert "29 still need" in app.error[0].value
    assert app.number_input(key="input_gwa").value == 89.12
    assert app.radio(key="input_R1").value == 4
    assert app.session_state[STAGE_KEY] == "input"
    save.assert_not_called()


def test_review_edit_save_and_edit_after_save(student_app):
    app, save = student_app
    fill_complete_form(app)
    press(app, "Review my information")
    assert app.session_state[STAGE_KEY] == "review"
    response_groups = [item.value for item in app.markdown if "3 · Neutral" in item.value]
    assert len(response_groups) == 6
    assert all(group.count("3 · Neutral") == 5 for group in response_groups)
    assert all(question["text"] in response_groups[index // 5] for index, question in enumerate(QUESTIONS))
    assert "tied" in " ".join(item.value for item in app.markdown)
    save.assert_not_called()
    press(app, "Back to edit")
    assert app.number_input(key="input_gwa").value == 89.12
    assert app.number_input(key="input_physics").value is None
    assert all(widget.value == 3 for widget in app.radio)
    app.number_input(key="input_gwa").set_value(90.25)
    app.number_input(key="input_physics").set_value(91.5)
    app.radio(key="input_R1").set_value(4)
    press(app, "Review my information")
    press(app, "Save without generating")
    save.assert_called_once()
    actor, target, gwa, subjects, answers = save.call_args.args
    assert actor == target == 1
    assert gwa == 90.25
    assert subjects["physics"] == 91.5 and subjects["chemistry"] is None
    assert answers == [4] + [3] * 29
    assert app.session_state[STAGE_KEY] == "saved"
    assert "have been saved" in app.success[-1].value
    press(app, "Review and update my information")
    assert app.number_input(key="input_physics").value == 91.5
    assert app.radio(key="input_R1").value == 4


def test_database_failure_keeps_review_and_allows_retry(student_app):
    app, save = student_app
    fill_complete_form(app)
    press(app, "Review my information")
    original = deepcopy(app.session_state[DRAFT_KEY])
    save.side_effect = db.DatabaseError("Database unavailable; no data saved.")
    press(app, "Save without generating")
    assert "Database unavailable" in app.error[0].value
    assert app.session_state[STAGE_KEY] == "review"
    assert app.session_state[DRAFT_KEY] == original
    save.side_effect = None
    press(app, "Save without generating")
    assert app.session_state[STAGE_KEY] == "saved"

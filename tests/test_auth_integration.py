"""Opt-in MySQL authentication checks; registration test writes always roll back."""

import os
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from database import db
from config import PROJECT_ROOT
from database.seed_demo import read_demo_passwords


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("CPP_RUN_DB_TESTS") != "1", reason="Set CPP_RUN_DB_TESTS=1 for local MySQL checks.",
)]


def test_demo_roles_login_and_access_restrictions():
    student_password, counselor_password = read_demo_passwords()
    student_state, counselor_state = {}, {}
    student = auth.login(student_state, db.DEMO_STUDENT, student_password)
    counselor = auth.login(counselor_state, db.DEMO_COUNSELOR, counselor_password)
    assert student["role"] == db.STUDENT
    assert counselor["role"] == db.COUNSELOR
    assert auth.current_user(student_state) == student
    assert db.get_student_record(student["user_id"], student["user_id"])["student"]["user_id"] == student["user_id"]
    assert any(row["user_id"] == student["user_id"] for row in db.list_students(counselor["user_id"]))
    with pytest.raises(db.AuthorizationError):
        db.save_student_inputs(counselor["user_id"], student["user_id"], 89, {}, [3] * 30)
    with pytest.raises(db.AuthorizationError):
        db.get_student_record(student["user_id"], counselor["user_id"])
    with pytest.raises(auth.AuthenticationError):
        auth.login({}, db.DEMO_STUDENT, "deliberately-incorrect-password")
    auth.logout(student_state)
    assert student_state == {}


def test_registration_login_and_duplicate_in_rollback_transaction(monkeypatch):
    connection = db._connect()
    username = "test_" + uuid4().hex
    password = uuid4().hex
    class RollbackOnlyConnection:
        def cursor(self):
            return connection.cursor()
        def commit(self):
            pass  # Keep all registration writes uncommitted in this test.
        def rollback(self):
            connection.rollback()
        def close(self):
            pass
    try:
        with monkeypatch.context() as patch:
            patch.setattr(db, "_connect", RollbackOnlyConnection)
            app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
            app.text_input(key="register_username").set_value(username)
            app.text_input(key="register_password").set_value(password)
            app.text_input(key="register_confirmation").set_value(password)
            next(button for button in app.button if button.label == "Create student account").click().run()
            assert not app.exception
            assert "Student account created" in app.success[0].value
            user_id = db.get_login_record(username)["user_id"]
            app.text_input(key="login_username").set_value(username.upper())
            app.text_input(key="login_password").set_value(password)
            next(button for button in app.button if button.label == "Log in").click().run()
            assert not app.exception
            assert app.title[0].value == "Student home"
            identity = app.session_state[auth.IDENTITY_KEY]
            assert identity == {"user_id": user_id, "username": username, "role": db.STUDENT}
            assert password not in repr(app.session_state.to_dict())
            with pytest.raises(db.UsernameTakenError):
                auth.register_student(username, password, password)
    finally:
        connection.rollback()
        connection.close()
    assert db.get_login_record(username) is None

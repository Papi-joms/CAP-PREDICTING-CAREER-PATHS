"""Exercise real Streamlit forms/callbacks with an in-memory mock of the DB boundary."""

import bcrypt
import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from config import PROJECT_ROOT
from database import db


@pytest.fixture
def accounts(monkeypatch):
    password_hash = bcrypt.hashpw(b"test-private-password", bcrypt.gensalt(rounds=4)).decode()
    accounts = {
        "student_user": {"user_id": 1, "username": "student_user", "role": db.STUDENT, "password_hash": password_hash},
        "counselor_user": {"user_id": 2, "username": "counselor_user", "role": db.COUNSELOR, "password_hash": password_hash},
    }
    monkeypatch.setattr(db, "get_login_record", lambda username: accounts.get(username.lower()))
    def identity(user_id):
        return next(({key: row[key] for key in ("user_id", "username", "role")} for row in accounts.values() if row["user_id"] == user_id), None)
    monkeypatch.setattr(db, "get_user_identity", identity)
    def create(username, password_hash):
        if username.lower() in accounts:
            raise db.UsernameTakenError("That username is unavailable. Choose another username.")
        user_id = len(accounts) + 1
        accounts[username.lower()] = {"user_id": user_id, "username": username, "role": db.STUDENT, "password_hash": password_hash}
        return user_id
    monkeypatch.setattr(db, "create_student_account", create)
    monkeypatch.setattr(db, "get_student_record", lambda actor, target: {
        "student": {"user_id": target}, "profile": None, "riasec": None,
    })
    monkeypatch.setattr(db, "list_students", lambda actor: [])
    return accounts


def press(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


@pytest.mark.parametrize("username,title", [("student_user", "Student home"), ("counselor_user", "Counselor home")])
def test_login_navigation_and_logout(accounts, username, title):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    assert not app.exception
    app.text_input(key="login_username").set_value(username)
    app.text_input(key="login_password").set_value("test-private-password")
    press(app, "Log in")
    assert app.title[0].value == title
    assert "test-private-password" not in repr(app.session_state.to_dict())
    app.session_state["draft"] = "old private draft"
    press(app, "Log out")
    assert app.title[0].value == "CPP Career Guidance"
    assert auth.IDENTITY_KEY not in app.session_state
    assert "draft" not in app.session_state


def test_failed_login_and_registration_clear_password_widgets(accounts):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    app.text_input(key="login_username").set_value("student_user")
    app.text_input(key="login_password").set_value("incorrect-password")
    press(app, "Log in")
    assert app.error[0].value == auth.INVALID_LOGIN
    assert app.text_input(key="login_password").value == ""
    assert "incorrect-password" not in repr(app.session_state.to_dict())
    app.text_input(key="register_username").set_value("new_student")
    app.text_input(key="register_password").set_value("brand-new-password")
    app.text_input(key="register_confirmation").set_value("brand-new-password")
    press(app, "Create student account")
    assert "Student account created" in app.success[0].value
    assert app.session_state["account_tab"] == "Log in"
    assert app.text_input(key="login_username").value == "new_student"
    assert accounts["new_student"]["role"] == db.STUDENT
    assert "brand-new-password" not in repr(app.session_state.to_dict())
    assert not app.selectbox  # No role selector or counselor registration.
    # Follow registration with login in the same session, as a student would.
    app.text_input(key="login_username").set_value("new_student")
    app.text_input(key="login_password").set_value("brand-new-password")
    press(app, "Log in")
    assert app.title[0].value == "Student home"
    assert app.session_state[auth.IDENTITY_KEY]["username"] == "new_student"
    press(app, "Log out")
    app.text_input(key="login_username").set_value("NEW_STUDENT")
    app.text_input(key="login_password").set_value("brand-new-password")
    press(app, "Log in")
    assert app.title[0].value == "Student home"


def test_duplicate_registration_is_readable(accounts):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    app.text_input(key="register_username").set_value("STUDENT_USER")
    app.text_input(key="register_password").set_value("brand-new-password")
    app.text_input(key="register_confirmation").set_value("brand-new-password")
    press(app, "Create student account")
    assert "unavailable" in app.error[0].value
    assert app.session_state["account_tab"] == "Create student account"
    assert app.text_input(key="register_username").value == "STUDENT_USER"
    assert "brand-new-password" not in repr(app.session_state.to_dict())


@pytest.mark.parametrize("filename,wrong_role", [("1_Student_Dashboard.py", db.COUNSELOR), ("2_Counselor_Dashboard.py", db.STUDENT)])
def test_direct_page_execution_checks_role(accounts, filename, wrong_role):
    app = AppTest.from_file(str(PROJECT_ROOT / "pages" / filename), default_timeout=15)
    row = next(row for row in accounts.values() if row["role"] == wrong_role)
    app.session_state[auth.IDENTITY_KEY] = {key: row[key] for key in ("user_id", "username", "role")}
    app.run()
    assert not app.exception
    assert "cannot access" in app.error[0].value
    assert not app.title


def test_direct_page_without_login_stops(accounts):
    app = AppTest.from_file(str(PROJECT_ROOT / "pages/1_Student_Dashboard.py"), default_timeout=15).run()
    assert not app.exception
    assert "log in" in app.error[0].value
    assert not app.title


@pytest.mark.parametrize("password,confirmation,error_text", [
    ("short", "short", "12-72"),
    ("x" * 73, "x" * 73, "12-72"),
    ("é" * 37, "é" * 37, "12-72"),
    ("valid-long-password", "different-password", "do not match"),
])
def test_registration_error_keeps_creation_tab_and_allows_correction(accounts, password, confirmation, error_text):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    app.session_state["account_tab"] = "Create student account"
    app.run()
    app.text_input(key="register_username").set_value("new_registration")
    app.text_input(key="register_password").set_value(password)
    app.text_input(key="register_confirmation").set_value(confirmation)
    press(app, "Create student account")
    assert app.session_state["account_tab"] == "Create student account"
    assert "Account not created" in app.tabs[1].error[0].value
    assert error_text in app.tabs[1].error[0].value
    assert not app.tabs[0].error
    assert app.text_input(key="register_username").value == "new_registration"
    assert app.text_input(key="register_password").value == ""
    assert app.text_input(key="register_confirmation").value == ""
    assert "new_registration" not in accounts
    app.text_input(key="register_password").set_value("corrected-private-password")
    app.text_input(key="register_confirmation").set_value("corrected-private-password")
    press(app, "Create student account")
    assert app.session_state["account_tab"] == "Log in"
    assert "Student account created" in app.tabs[0].success[0].value
    assert app.text_input(key="login_username").value == "new_registration"

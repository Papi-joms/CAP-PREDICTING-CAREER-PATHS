"""Authentication and session invariants without database credentials."""

from unittest.mock import MagicMock

import bcrypt
import pytest

from ui import auth
from database import db


@pytest.fixture
def account():
    return {"user_id": 10, "username": "test_student", "role": db.STUDENT,
            "password_hash": bcrypt.hashpw(b"private-test-password", bcrypt.gensalt(rounds=4)).decode()}


@pytest.mark.parametrize("role", [db.STUDENT, db.COUNSELOR])
def test_correct_login_keeps_only_safe_identity(monkeypatch, account, role):
    account["role"] = role
    monkeypatch.setattr(db, "get_login_record", lambda username: account)
    state = {"old_draft": {"gwa": 90}, "selected_student": 7, "login_password": "private-test-password"}
    identity = auth.login(state, account["username"], "private-test-password")
    assert state == {auth.IDENTITY_KEY: identity}
    assert set(identity) == {"user_id", "username", "role"}
    assert "private-test-password" not in repr(state)
    assert account["password_hash"] not in repr(state)


@pytest.mark.parametrize("exists", [True, False])
def test_wrong_password_and_unknown_user_have_same_error(monkeypatch, account, exists):
    monkeypatch.setattr(db, "get_login_record", lambda username: account if exists else None)
    state = {auth.IDENTITY_KEY: {"user_id": 3}}
    with pytest.raises(auth.AuthenticationError, match=auth.INVALID_LOGIN):
        auth.login(state, "test_student", "incorrect-password")
    assert state == {}


def test_registration_hashes_password_and_has_no_role_argument(monkeypatch):
    create = MagicMock(return_value=15)
    monkeypatch.setattr(db, "create_student_account", create)
    assert auth.register_student(" new_student ", "new-private-password", "new-private-password") == 15
    username, password_hash = create.call_args.args
    assert username == "new_student"
    assert password_hash != "new-private-password"
    assert bcrypt.checkpw(b"new-private-password", password_hash.encode())
    assert not create.call_args.kwargs


@pytest.mark.parametrize("username,password,confirmation", [
    ("a", "new-private-password", "new-private-password"),
    ("name';--", "new-private-password", "new-private-password"),
    ("CPP_DEMO_student", "new-private-password", "new-private-password"),
    ("student", "short", "short"), ("student", "x" * 73, "x" * 73),
    ("student", "é" * 37, "é" * 37),
    ("student", "new-private-password", "different-password"),
])
def test_invalid_registration_never_calls_database(monkeypatch, username, password, confirmation):
    create = MagicMock()
    monkeypatch.setattr(db, "create_student_account", create)
    with pytest.raises(auth.AuthenticationError):
        auth.register_student(username, password, confirmation)
    create.assert_not_called()


def test_password_byte_limit_and_spaces_preserved():
    assert len(auth.validate_password("é" * 36)) == 72
    assert auth.validate_password(" a private password ") == b" a private password "


def test_logout_clears_identity_drafts_and_navigation():
    state = {auth.IDENTITY_KEY: {"user_id": 1}, "draft": [3] * 30, "selected_student": 8, "navigation": "student"}
    auth.logout(state)
    assert state == {}


@pytest.mark.parametrize("role,allowed", [(db.STUDENT, db.COUNSELOR), (db.COUNSELOR, db.STUDENT)])
def test_page_role_check(monkeypatch, role, allowed):
    identity = {"user_id": 1, "username": "someone", "role": role}
    monkeypatch.setattr(db, "get_user_identity", lambda user_id: dict(identity))
    with pytest.raises(db.AuthorizationError, match="cannot access"):
        auth.current_user({auth.IDENTITY_KEY: identity}, allowed_roles=(allowed,))


@pytest.mark.parametrize("actual", [None, {"user_id": 1, "username": "student", "role": db.COUNSELOR}])
def test_deleted_account_or_role_change_invalidates_session(monkeypatch, actual):
    state = {auth.IDENTITY_KEY: {"user_id": 1, "username": "student", "role": db.STUDENT}, "draft": "private"}
    monkeypatch.setattr(db, "get_user_identity", lambda user_id: actual)
    with pytest.raises(db.AuthorizationError):
        auth.current_user(state)
    assert state == {}


def test_database_failure_fails_closed(monkeypatch):
    state = {auth.IDENTITY_KEY: {"user_id": 1, "username": "student", "role": db.STUDENT}}
    monkeypatch.setattr(db, "get_user_identity", MagicMock(side_effect=db.DatabaseError("Unavailable")))
    with pytest.raises(db.DatabaseError):
        auth.current_user(state)
    assert state == {}

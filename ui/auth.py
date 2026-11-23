"""Authentication/session helpers. SQL belongs exclusively in db.py."""

from collections.abc import MutableMapping
import re

import bcrypt

from database import db
from config import ConfigurationError


IDENTITY_KEY = "_cpp_identity"
NOTICE_KEY = "_cpp_auth_notice"
INVALID_LOGIN = "Incorrect username or password."
# Non-secret timing fallback, never an application account or a usable credential.
_DUMMY_HASH = bcrypt.hashpw(b"CPP non-account verification value", bcrypt.gensalt(rounds=12))


class AuthenticationError(ValueError):
    """Login or registration input is invalid."""


def validate_username(username: str) -> str:
    """Normalize surrounding whitespace; database uniqueness is case-insensitive."""
    if not isinstance(username, str):
        raise AuthenticationError("Enter a username.")
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,64}", username):
        raise AuthenticationError("Username must contain 3-64 letters, digits, or underscores.")
    return username


def validate_password(password: str) -> bytes:
    """Preserve passwords exactly and reject bcrypt truncation instead of hiding it."""
    if not isinstance(password, str) or not password.strip():
        raise AuthenticationError("Enter a password.")
    encoded = password.encode("utf-8")
    if not 12 <= len(encoded) <= 72:
        raise AuthenticationError("Password must contain 12-72 UTF-8 bytes; non-English characters may use more than one byte.")
    return encoded


def register_student(username: str, password: str, confirmation: str) -> int:
    """Create Student accounts only. Counselor provisioning remains an offline task."""
    normalized = validate_username(username)
    encoded = validate_password(password)
    if password != confirmation:
        raise AuthenticationError("The passwords do not match.")
    if normalized.lower().startswith("cpp_demo_"):
        raise AuthenticationError("This username prefix is reserved for demo accounts.")
    password_hash = bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")
    return db.create_student_account(normalized, password_hash)


def logout(state: MutableMapping) -> None:
    """Discard identity, forms, drafts, selected students, and navigation together."""
    for key in list(state):
        del state[key]


def login(state: MutableMapping, username: str, password: str) -> dict:
    """Authenticate and retain only safe identity fields in the server-side session."""
    # Failed account-switch attempts must not preserve a previous user's identity.
    logout(state)
    try:
        normalized = validate_username(username)
        encoded = validate_password(password)
    except AuthenticationError:
        bcrypt.checkpw(b"invalid input", _DUMMY_HASH)
        raise AuthenticationError(INVALID_LOGIN) from None
    record = db.get_login_record(normalized)
    stored_hash = record["password_hash"].encode("ascii") if record else _DUMMY_HASH
    try:
        valid = bcrypt.checkpw(encoded, stored_hash)
    except (ValueError, TypeError):
        valid = False
    if not valid or not record or record["role"] not in (db.STUDENT, db.COUNSELOR):
        raise AuthenticationError(INVALID_LOGIN)
    identity = {key: record[key] for key in ("user_id", "username", "role")}
    state[IDENTITY_KEY] = identity
    return dict(identity)


def current_user(state: MutableMapping, *, allowed_roles: tuple[str, ...] | None = None) -> dict:
    """Fail closed for missing/deleted/changed identities and enforce the page's role."""
    stored = state.get(IDENTITY_KEY)
    if not isinstance(stored, dict) or set(stored) != {"user_id", "username", "role"}:
        logout(state)
        raise db.AuthorizationError("Please log in to continue.")
    try:
        actual = db.get_user_identity(stored["user_id"])
    except (db.DatabaseError, ConfigurationError):
        logout(state)
        raise
    if not actual or actual != stored or actual["role"] not in (db.STUDENT, db.COUNSELOR):
        logout(state)
        raise db.AuthorizationError("Your session is no longer valid. Please log in again.")
    if allowed_roles is not None and actual["role"] not in allowed_roles:
        raise db.AuthorizationError("Your account cannot access this page.")
    return dict(actual)


def require_page_user(role: str) -> dict:
    """Guard each page itself, independently of which links navigation displays."""
    import streamlit as st

    try:
        return current_user(st.session_state, allowed_roles=(role,))
    except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.error(str(error))
        st.stop()

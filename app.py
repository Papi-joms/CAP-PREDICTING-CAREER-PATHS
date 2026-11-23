"""Streamlit entry point: login, student registration, and protected navigation."""

import streamlit as st

from ui import auth
from database import db
from config import ConfigurationError, PROJECT_ROOT


def _submit_login() -> None:
    """Consume password widget values in the callback, then clear them immediately."""
    username = st.session_state.pop("login_username", "")
    password = st.session_state.pop("login_password", "")
    try:
        auth.login(st.session_state, username, password)
    except (auth.AuthenticationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[auth.NOTICE_KEY] = ("error", str(error))


def _submit_registration() -> None:
    """Keep unsuccessful registrations on their form while clearing password fields."""
    username = st.session_state.get("register_username", "")
    password = st.session_state.get("register_password", "")
    confirmation = st.session_state.get("register_confirmation", "")
    st.session_state["register_password"] = ""
    st.session_state["register_confirmation"] = ""
    try:
        auth.register_student(username, password, confirmation)
        st.session_state["register_username"] = ""
        st.session_state["login_username"] = username.strip()
        st.session_state["account_tab"] = "Log in"
        st.session_state[auth.NOTICE_KEY] = ("success", "Student account created. You can now log in.")
    except (ValueError, db.DatabaseError, ConfigurationError) as error:
        st.session_state["account_tab"] = "Create student account"
        st.session_state[auth.NOTICE_KEY] = ("error", f"Account not created. {error}")


def _show_notice(notice: tuple[str, str] | None) -> None:
    """Place submission feedback inside the active account tab."""
    if notice:
        kind, message = notice
        if kind == "success":
            st.success(message)
        else:
            st.error(message)


def account_page() -> None:
    """Show the two public forms; there is no public counselor-registration path."""
    st.html(PROJECT_ROOT / "ui" / "account_theme.css")
    with st.container(key="cpp_account_intro"):
        st.title("CPP Career Guidance", anchor=False)
        st.write("Explore career paths using your grades and interests.")
    notice = st.session_state.pop(auth.NOTICE_KEY, None)
    with st.container(key="cpp_account_forms", border=True):
        login_tab, register_tab = st.tabs(
            ["Log in", "Create student account"], key="account_tab", on_change="rerun",
        )
    with login_tab:
        if st.session_state["account_tab"] == "Log in":
            _show_notice(notice)
        with st.form("login_form", clear_on_submit=True, border=False):
            st.text_input("Username", key="login_username", max_chars=64)
            st.text_input("Password", type="password", key="login_password")
            st.form_submit_button("Log in", on_click=_submit_login, type="primary", width="stretch")
        st.caption("Students and guidance counselors use the same login form.")
    with register_tab:
        if st.session_state["account_tab"] == "Create student account":
            _show_notice(notice)
        with st.form("registration_form", clear_on_submit=False, border=False):
            st.text_input("Choose a username", key="register_username", max_chars=64,
                          help="3-64 letters, digits, or underscores. Usernames are not case-sensitive.")
            st.text_input("Choose a password", type="password", key="register_password",
                          help="12-72 UTF-8 bytes. Use a unique password; spaces are preserved.")
            st.caption("Use 12–72 characters for English letters, numbers, and symbols. Other characters may use more than one byte toward the 72-byte limit.")
            st.text_input("Confirm password", type="password", key="register_confirmation")
            st.form_submit_button("Create student account", on_click=_submit_registration, width="stretch")
        st.caption("Guidance counselor accounts are provided by the system administrator.")
    st.info("Recommendations use a synthetic training dataset and are guidance, not guarantees of career suitability or future success.")


def main() -> None:
    """Choose navigation from validated server identity, not URL parameters."""
    st.set_page_config(page_title="CPP Career Guidance", page_icon="🎓", layout="centered")
    user = None
    if auth.IDENTITY_KEY in st.session_state:
        try:
            user = auth.current_user(st.session_state)
        except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
            st.session_state[auth.NOTICE_KEY] = ("error", str(error))
    if user is None:
        pages = [st.Page(account_page, title="Account", default=True)]
    else:
        with st.sidebar:
            st.write(f"Signed in as **{user['username']}**")
            st.caption(user["role"])
            st.button("Log out", on_click=auth.logout, args=(st.session_state,))
        if user["role"] == db.STUDENT:
            pages = [st.Page("pages/1_Student_Dashboard.py", title="Student home", url_path="student", default=True),
                     st.Page("pages/3_Student_Report.py", title="My saved report", url_path="my_report")]
        else:
            pages = [st.Page("pages/2_Counselor_Dashboard.py", title="Counselor home", url_path="counselor", default=True)]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()

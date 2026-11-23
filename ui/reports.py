"""Read-only saved reports shared by Student and Counselor pages."""

import streamlit as st

from ui import auth
from database import db
from config import ConfigurationError
from ui.riasec import ASSESSMENT_LIMITATION, TYPE_NAMES, holland_summary
from ui.student_inputs import SUBJECT_LABELS, _show_review, render_recommendations
from validation import RIASEC_TYPES


def render_report(user: dict, target_user_id: int) -> None:
    """Recheck identity and load authorized records before displaying any data."""
    try:
        actor = auth.current_user(st.session_state)
        if actor["user_id"] != user["user_id"]:
            raise db.AuthorizationError("Please reopen your report after signing in.")
        record = db.get_student_record(actor["user_id"], target_user_id)
        runs = db.get_prediction_history(actor["user_id"], target_user_id)
    except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.error(f"Report could not be loaded. {error}")
        return

    st.subheader(f"Saved report: {record['student']['username']}")
    profile, response = record["profile"], record["riasec"]
    assessment_complete = response and response["is_complete"]
    with st.container(border=True):
        grades, assessment = st.columns(2)
        with grades:
            if profile:
                st.metric("Current GWA", f"{profile['gwa']:.2f}")
            else:
                st.info("No academic profile has been saved yet.")
        with assessment:
            if assessment_complete:
                st.markdown("**Assessment status**")
                st.write("Complete")
                st.caption("30 of 30 responses saved")
            else:
                st.info("Assessment status: Not completed. No completed interest results are available.")

    if profile:
        st.subheader("Current academic profile")
        st.table([{"Subject": label, "Grade": "Not provided" if profile[name] is None else f"{profile[name]:.2f}"}
                  for name, label in SUBJECT_LABELS.items()])

    if assessment_complete:
        st.subheader("Current interest assessment")
        summary = holland_summary(response["answers"])
        st.table([{"Type": TYPE_NAMES[kind], "Score (5–25)": summary["scores"][kind]} for kind in RIASEC_TYPES])
        names = ", ".join(TYPE_NAMES[kind] for kind in summary["dominant"])
        if len(summary["dominant"]) == 1:
            st.write(f"Dominant Holland type: **{names}**")
            secondary = ", ".join(TYPE_NAMES[kind] for kind in summary["secondary"])
            st.write(f"Secondary Holland type(s): **{secondary}**")
        else:
            st.write(f"Highest-scoring Holland types (tied): **{names}**")
            st.caption("There is no unique dominant/secondary ordering for these tied highest scores.")
    st.caption(ASSESSMENT_LIMITATION)

    st.subheader("Previous predictions")
    if not runs:
        st.info("No prediction runs have been saved yet.")
        return
    by_id = {run["prediction_run_id"]: run for run in runs}
    # Scope widget state to both viewer and student; never carry a different
    # student's selected history into this report. No user data is cached.
    key = f"report_run_{actor['user_id']}_{target_user_id}"
    if st.session_state.get(key) not in by_id:
        st.session_state[key] = runs[0]["prediction_run_id"]
    selected = st.selectbox(
        "Choose a prediction (newest first)", list(by_id), key=key,
        format_func=lambda run_id: f"{by_id[run_id]['created_at']:%b %d, %Y · %I:%M %p} · Run {run_id}",
    )
    run = by_id[selected]
    snapshot = run["input_snapshot"]
    st.caption(f"Saved {run['created_at']:%Y-%m-%d %H:%M:%S} Asia/Manila · Model {run['model_version']}")
    if (not profile or not response or float(profile["gwa"]) != snapshot["gwa"]
            or any((None if profile[name] is None else float(profile[name])) != snapshot["subjects"][name]
                   for name in SUBJECT_LABELS)
            or response["answers"] != snapshot["answers"]):
        st.warning("This prediction uses saved inputs that differ from the current profile shown above.")
    render_recommendations(run["recommendations"])
    with st.expander("Inputs saved with this prediction"):
        _show_review({"gwa": snapshot["gwa"], "subjects": snapshot["subjects"], "answers": snapshot["answers"]})


def render_counselor_reports(user: dict) -> None:
    """Offer only authorized student choices and read-only report controls."""
    try:
        actor = auth.current_user(st.session_state, allowed_roles=(db.COUNSELOR,))
        students = db.list_students(actor["user_id"])
    except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.error(f"Student list could not be loaded. {error}")
        return
    if not students:
        st.info("No student accounts are registered yet.")
        return
    choices = {row["user_id"]: row["username"] for row in students}
    key = "counselor_report_student"
    if st.session_state.get(key) not in choices:
        st.session_state[key] = next(iter(choices))
    target = st.selectbox("Select a student", list(choices), key=key, format_func=choices.get)
    st.caption("Read-only access: counselors can view reports but cannot edit students or generate predictions.")
    render_report(user, target)

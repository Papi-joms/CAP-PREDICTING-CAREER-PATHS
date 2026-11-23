"""Student input/review/edit UI. Persistence and authorization remain in db.py/auth.py."""

from collections.abc import MutableMapping

import streamlit as st

from ui import auth
from config import ConfigurationError
from database import db
from ml import predict
from ui.riasec import ASSESSMENT_LIMITATION, LIKERT_LABELS, QUESTIONS, TYPE_NAMES, holland_summary
from validation import RIASEC_TYPES, SUBJECTS, validate_academics, validate_answers


DRAFT_KEY = "_cpp_student_draft"
STAGE_KEY = "_cpp_student_stage"
NOTICE_KEY = "_cpp_student_notice"
RUN_KEY = "_cpp_selected_prediction_run"
SUBJECT_LABELS = dict(zip(SUBJECTS, (
    "General Biology 1", "General Biology 2", "Chemistry", "Physics",
    "Pre-Calculus", "Basic Calculus", "Statistics and Probability",
)))


def validate_draft(draft: dict, owner_user_id: int) -> dict:
    """Validate and round a complete draft without changing the database."""
    if not isinstance(draft, dict) or draft.get("owner_user_id") != owner_user_id:
        raise db.AuthorizationError("This draft does not belong to your account.")
    academics = validate_academics(draft.get("gwa"), draft.get("subjects", {}))
    answers = draft.get("answers")
    if isinstance(answers, list) and len(answers) == 30 and any(answer is None for answer in answers):
        raise ValueError(f"Please answer all 30 interest statements. {answers.count(None)} still need an answer.")
    answers = validate_answers(answers)
    return {"owner_user_id": owner_user_id, "gwa": float(academics["gwa"]),
            "subjects": {name: None if academics[name] is None else float(academics[name]) for name in SUBJECTS},
            "answers": answers}


def initialize_draft(state: MutableMapping, user_id: int) -> None:
    """Load the current student's own saved inputs once per session/draft owner."""
    if isinstance(state.get(DRAFT_KEY), dict) and state[DRAFT_KEY].get("owner_user_id") == user_id:
        return
    for key in list(state):
        if key.startswith("input_") or key in (DRAFT_KEY, STAGE_KEY, NOTICE_KEY, RUN_KEY):
            del state[key]
    record = db.get_student_record(user_id, user_id)
    profile = record["profile"]
    response = record["riasec"]
    state[DRAFT_KEY] = {
        "owner_user_id": user_id,
        "gwa": float(profile["gwa"]) if profile else None,
        "subjects": {name: float(profile[name]) if profile and profile[name] is not None else None for name in SUBJECTS},
        "answers": list(response["answers"]) if response else [None] * 30,
    }
    state[STAGE_KEY] = "saved" if profile and response and response["is_complete"] else "input"


def _review_submission() -> None:
    """Capture the submitted form; incomplete drafts stay in session state only."""
    try:
        user = auth.current_user(st.session_state, allowed_roles=(db.STUDENT,))
        draft = {"owner_user_id": user["user_id"], "gwa": st.session_state.get("input_gwa"),
                 "subjects": {name: st.session_state.get(f"input_{name}") for name in SUBJECTS},
                 "answers": [st.session_state.get(f"input_{question['id']}") for question in QUESTIONS]}
        st.session_state[DRAFT_KEY] = draft
        st.session_state[DRAFT_KEY] = validate_draft(draft, user["user_id"])
        st.session_state[STAGE_KEY] = "review"
        st.session_state.pop(NOTICE_KEY, None)
    except (ValueError, db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[NOTICE_KEY] = ("error", str(error))


def _edit_submission() -> None:
    """Return to the form, reconstructing widgets from the independent draft."""
    try:
        user = auth.current_user(st.session_state, allowed_roles=(db.STUDENT,))
        draft = st.session_state.get(DRAFT_KEY)
        if not draft or draft.get("owner_user_id") != user["user_id"]:
            raise db.AuthorizationError("Please reopen your own student profile.")
        # Hidden form widgets may still exist for one rerun. Restore explicitly
        # so the review-to-edit transition never resets validated values.
        _restore_widgets(draft)
        st.session_state[STAGE_KEY] = "input"
        st.session_state.pop(NOTICE_KEY, None)
    except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[NOTICE_KEY] = ("error", str(error))


def _save_submission() -> None:
    """Revalidate owner, role, and inputs at the commit boundary; preserve history."""
    try:
        user = auth.current_user(st.session_state, allowed_roles=(db.STUDENT,))
        if st.session_state.get(STAGE_KEY) != "review":
            raise ValueError("Review your information before saving.")
        draft = validate_draft(st.session_state.get(DRAFT_KEY), user["user_id"])
        db.save_student_inputs(user["user_id"], user["user_id"], draft["gwa"], draft["subjects"], draft["answers"])
        st.session_state[DRAFT_KEY] = draft
        st.session_state[STAGE_KEY] = "saved"
        st.session_state[NOTICE_KEY] = ("success", "Your academic profile and completed interest assessment have been saved.")
    except (ValueError, db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[NOTICE_KEY] = ("error", str(error))


def _review_saved_inputs() -> None:
    """Require an explicit review before generating from a previously saved profile."""
    try:
        user = auth.current_user(st.session_state, allowed_roles=(db.STUDENT,))
        draft = validate_draft(st.session_state.get(DRAFT_KEY), user["user_id"])
        st.session_state[DRAFT_KEY] = draft
        st.session_state[STAGE_KEY] = "review"
        st.session_state.pop(NOTICE_KEY, None)
    except (ValueError, db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[NOTICE_KEY] = ("error", str(error))


def _generate_submission() -> None:
    """Predict reviewed inputs and commit profile, survey, snapshot, and results once."""
    try:
        user = auth.current_user(st.session_state, allowed_roles=(db.STUDENT,))
        if st.session_state.get(STAGE_KEY) != "review":
            raise ValueError("Review your information before generating recommendations.")
        draft = validate_draft(st.session_state.get(DRAFT_KEY), user["user_id"])
        features = {"gwa": draft["gwa"], **draft["subjects"], "answers": draft["answers"]}
        model = predict.load_streamlit_model()
        recommendations = predict.predict_top3(features, model=model)
        # No save-only write occurs first. A model/DB failure must not create a
        # half-saved submission. The DB function owns the complete transaction.
        run_id = db.save_prediction_run(user["user_id"], user["user_id"], features,
                                        recommendations, model["model_version"])
        st.session_state[DRAFT_KEY] = draft
        st.session_state[RUN_KEY] = run_id
        st.session_state[STAGE_KEY] = "results"
        st.session_state[NOTICE_KEY] = ("success", "Your information and three recommendations have been saved as a new prediction run.")
    except (ValueError, OSError, db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.session_state[NOTICE_KEY] = ("error", f"Recommendations could not be generated and saved. {error}")


def _restore_widgets(draft: dict) -> None:
    """Rebuild transient input widget state from the saved server-side draft."""
    st.session_state["input_gwa"] = draft["gwa"]
    for name in SUBJECTS:
        st.session_state[f"input_{name}"] = draft["subjects"][name]
    for question, answer in zip(QUESTIONS, draft["answers"]):
        st.session_state[f"input_{question['id']}"] = answer


def _input_form(draft: dict) -> None:
    """Render required GWA, nullable subjects, and 30 explicitly answered items."""
    if "input_gwa" not in st.session_state:
        _restore_widgets(draft)
    st.subheader("Academic information and interests")
    st.write("Enter your GWA, add the subject grades you have, then answer each interest statement.")
    with st.form("student_inputs", clear_on_submit=False):
        with st.container(border=True):
            st.number_input("General Weighted Average (GWA) — required", min_value=75.0, max_value=100.0,
                            value=None, step=.01, format="%.2f", key="input_gwa", placeholder="Enter your GWA")
            st.caption("Grades must be between 75 and 100 and are saved to two decimal places.")
        with st.container(border=True):
            st.markdown("### Optional subject grades")
            st.caption("Leave unavailable grades blank.")
            columns = st.columns(2)
            for index, (name, label) in enumerate(SUBJECT_LABELS.items()):
                with columns[index % 2]:
                    st.number_input(label, min_value=75.0, max_value=100.0, value=None, step=.01,
                                    format="%.2f", key=f"input_{name}", placeholder="Not provided")
        st.subheader("Interest questionnaire")
        st.write("Rate how much you would enjoy each activity, regardless of your current skill or experience.")
        st.caption("1 = Strongly Dislike · 2 = Dislike · 3 = Neutral · 4 = Like · 5 = Strongly Like")
        st.info(ASSESSMENT_LIMITATION)
        for kind in RIASEC_TYPES:
            with st.container(border=True):
                st.markdown(f"### {TYPE_NAMES[kind]} interests")
                for index, question in enumerate(QUESTIONS):
                    if question["type"] == kind:
                        st.radio(f"{index + 1}. {question['text']}", options=[1, 2, 3, 4, 5], index=None,
                                 format_func=lambda value: f"{value} — {LIKERT_LABELS[value]}",
                                 horizontal=True, key=f"input_{question['id']}")
        st.form_submit_button("Review my information", type="primary", on_click=_review_submission)


def _show_review(draft: dict) -> None:
    """Show every input plus deterministic scores and explicit ties."""
    st.metric("GWA", f"{draft['gwa']:.2f}")
    st.table([{"Subject": label, "Grade": "Not provided" if draft["subjects"][name] is None else f"{draft['subjects'][name]:.2f}"}
              for name, label in SUBJECT_LABELS.items()])
    summary = holland_summary(draft["answers"])
    st.subheader("Your interest scores")
    st.table([{"Type": f"{kind} — {TYPE_NAMES[kind]}", "Score (5–25)": summary["scores"][kind]} for kind in RIASEC_TYPES])
    dominant = ", ".join(TYPE_NAMES[kind] for kind in summary["dominant"])
    if len(summary["dominant"]) == 1:
        st.write(f"Dominant Holland type: **{dominant}**")
        secondary = ", ".join(TYPE_NAMES[kind] for kind in summary["secondary"])
        label = "Secondary Holland types (tied)" if len(summary["secondary"]) > 1 else "Secondary Holland type"
        st.write(f"{label}: **{secondary}**")
    else:
        st.write(f"Highest-scoring Holland types (tied): **{dominant}**")
        st.caption("There is no unique dominant/secondary ordering for these tied highest scores.")
    st.caption(ASSESSMENT_LIMITATION)
    st.subheader("All 30 responses")
    responses = list(zip(QUESTIONS, draft["answers"]))
    for kind in RIASEC_TYPES:
        with st.container(border=True):
            st.markdown(f"### {TYPE_NAMES[kind]} interests")
            st.markdown("\n\n".join(
                f"**{question['id']}** {question['text']}  \n{answer} · {LIKERT_LABELS[answer]}"
                for question, answer in responses if question["type"] == kind
            ))


def render_recommendations(recommendations: list[dict]) -> None:
    """Display ranked results and explain their scores in both views."""
    for result in recommendations:
        with st.container(border=True, horizontal=True, horizontal_alignment="distribute",
                          vertical_alignment="center"):
            st.markdown(f"**{result['rank']}. {result['career']}**", width="content")
            st.markdown(f"{result['probability']:.2%} match score", width="content")
    st.info(predict.MATCH_SCORE_EXPLANATION)
    st.caption("Scores are shown for the top three of 12 categories, so they do not necessarily add up to 100%.")


def _show_prediction_history(user_id: int, current_draft: dict) -> None:
    """Read authorized persisted runs, never label current inputs as historical ones."""
    st.subheader("Recommendations and prediction history")
    try:
        runs = db.get_prediction_history(user_id, user_id)
    except (db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.error(f"Prediction history could not be loaded. {error}")
        return
    if not runs:
        st.info("No recommendations yet. Review your saved information to generate your first set.")
        return
    run_by_id = {run["prediction_run_id"]: run for run in runs}
    if st.session_state.get(RUN_KEY) not in run_by_id:
        st.session_state[RUN_KEY] = runs[0]["prediction_run_id"]
    selected = st.selectbox(
        "Choose a prediction run (newest first)", options=list(run_by_id), key=RUN_KEY,
        format_func=lambda run_id: f"Run {run_id} — {run_by_id[run_id]['created_at']:%Y-%m-%d %H:%M:%S}",
    )
    run = run_by_id[selected]
    snapshot = run["input_snapshot"]
    st.caption(f"Saved {run['created_at']:%Y-%m-%d %H:%M:%S} Asia/Manila · Model {run['model_version']}")
    snapshot_draft = {"owner_user_id": user_id, "gwa": snapshot["gwa"],
                      "subjects": snapshot["subjects"], "answers": snapshot["answers"]}
    if snapshot_draft != current_draft:
        st.warning("These results use this run's saved inputs, which differ from your current profile. Review your current information to generate updated results.")
    render_recommendations(run["recommendations"])
    with st.expander("View the inputs used for this prediction run"):
        _show_review(snapshot_draft)


def render_student_inputs(user: dict) -> None:
    """Run the input/review/saved flow for the authenticated student only."""
    try:
        initialize_draft(st.session_state, user["user_id"])
    except (ValueError, db.AuthorizationError, db.DatabaseError, ConfigurationError) as error:
        st.error(f"Your profile could not be loaded. {error}")
        st.stop()
    notice = st.session_state.pop(NOTICE_KEY, None)
    if notice:
        if notice[0] == "success":
            st.success(notice[1])
        else:
            st.error(notice[1])
    stage = st.session_state.get(STAGE_KEY, "input")
    draft = st.session_state[DRAFT_KEY]
    prediction_steps = {"input": "Enter information", "review": "Review", "results": "Results"}
    if stage in prediction_steps:
        st.caption(" → ".join(
            f"**{label}**" if step == stage else label
            for step, label in prediction_steps.items()
        ))
    if stage == "input":
        _input_form(draft)
    elif stage == "results":
        _show_prediction_history(user["user_id"], draft)
        st.button("Review and update my information", on_click=_edit_submission)
        st.button("Review current information for another prediction", on_click=_review_saved_inputs)
    else:
        try:
            draft = validate_draft(draft, user["user_id"])
        except (ValueError, db.AuthorizationError) as error:
            st.error(str(error))
            st.button("Return to editing", on_click=_edit_submission)
            st.stop()
        st.subheader("Review your information" if stage == "review" else "Your saved information")
        st.caption("Check your grades and all answers before saving or generating recommendations." if stage == "review" else "Assessment status: Complete (30 of 30 responses saved).")
        _show_review(draft)
        st.button("Back to edit" if stage == "review" else "Review and update my information", on_click=_edit_submission)
        if stage == "review":
            st.button("Generate recommendations", type="primary", on_click=_generate_submission)
            st.button("Save without generating", on_click=_save_submission,
                      help="Save your current inputs without generating a prediction run.")
        else:
            st.button("Review and generate recommendations", type="primary", on_click=_review_saved_inputs)
            _show_prediction_history(user["user_id"], draft)

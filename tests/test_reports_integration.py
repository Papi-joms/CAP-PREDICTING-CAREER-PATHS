"""Read-only real-MySQL report checks and database-level privacy enforcement."""

import os

import pytest
from streamlit.testing.v1 import AppTest

from ui import auth
from database import db
from config import PROJECT_ROOT


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("CPP_RUN_DB_TESTS") != "1", reason="Set CPP_RUN_DB_TESTS=1 for local MySQL checks.",
)]


def test_live_reports_preserve_data_and_enforce_privacy():
    student = db.get_user_identity(db.get_login_record(db.DEMO_STUDENT)["user_id"])
    counselor = db.get_user_identity(db.get_login_record(db.DEMO_COUNSELOR)["user_id"])
    sid, cid = student["user_id"], counselor["user_id"]
    before = db.get_student_record(sid, sid), db.get_prediction_history(sid, sid)
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30)
    app.session_state[auth.IDENTITY_KEY] = student
    app.run()
    app.switch_page("pages/3_Student_Report.py").run()
    assert not app.exception and not app.error
    assert app.title[0].value == "My saved report"
    assert app.metric[0].value == f"{before[0]['profile']['gwa']:.2f}"
    counselor_app = AppTest.from_file(str(PROJECT_ROOT / "pages/2_Counselor_Dashboard.py"), default_timeout=30)
    counselor_app.session_state[auth.IDENTITY_KEY] = counselor
    counselor_app.session_state["counselor_report_student"] = sid
    counselor_app.run()
    assert not counselor_app.exception and not counselor_app.error
    assert counselor_app.metric[0].value == app.metric[0].value
    assert not counselor_app.button and not counselor_app.number_input
    with pytest.raises(db.AuthorizationError):
        db.list_students(sid)
    for read in (db.get_student_record, db.get_prediction_history):
        with pytest.raises(db.AuthorizationError):
            read(sid, cid)
    with pytest.raises(db.AuthorizationError):
        db.save_student_inputs(cid, sid, 89, {}, [3] * 30)
    assert (db.get_student_record(sid, sid), db.get_prediction_history(sid, sid)) == before

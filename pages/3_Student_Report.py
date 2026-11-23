"""Student-only saved report; target identity always comes from authentication."""

import streamlit as st

from ui.auth import require_page_user
from database.db import STUDENT
from ui.reports import render_report


user = require_page_user(STUDENT)
st.title("My saved report")
st.caption("This report shows saved information. Unsaved edits remain on Student home.")
st.page_link("pages/1_Student_Dashboard.py", label="Review and update my information")
render_report(user, user["user_id"])

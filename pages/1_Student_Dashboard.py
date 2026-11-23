"""Protected Student academic input, interest assessment, and review/edit flow."""

import streamlit as st

from ui.auth import require_page_user
from database.db import STUDENT
from ui.student_inputs import render_student_inputs


user = require_page_user(STUDENT)
st.title("Student home")
st.success(f"Welcome, {user['username']}.")
st.caption("Your student account can access only your own records.")
render_student_inputs(user)

"""Protected, read-only Counselor student reports."""

import streamlit as st

from ui.auth import require_page_user
from database.db import COUNSELOR
from ui.reports import render_counselor_reports


user = require_page_user(COUNSELOR)
st.title("Counselor home")
render_counselor_reports(user)

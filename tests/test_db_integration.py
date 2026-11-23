"""Opt-in real MySQL checks; db.py rolls back all diagnostic account data."""

import os

import pytest

from database import db


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("CPP_RUN_DB_TESTS") != "1", reason="Set CPP_RUN_DB_TESTS=1 for local MySQL checks.",
)]


def test_live_schema_and_transaction_safety():
    assert db.check_connection()["database_name"]
    assert len(db.inspect_schema()["tables"]) == 5
    assert len(db.verify_foundation()) == 5


def test_live_saved_data_consistency():
    report = db.audit_saved_data()
    assert report["profiles"] == report["assessments"]
    assert report["recommendations"] == report["prediction_runs"] * 3

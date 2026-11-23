"""Validate immutable snapshots, atomic result writes, and safe demo reruns."""

from copy import deepcopy
import json
from unittest.mock import MagicMock

import pymysql
import pytest

from database import db


@pytest.fixture
def results():
    return [{"rank": 1, "career": "Civil Engineering", "match_score": .4},
            {"rank": 2, "career": "Mechanical Engineering", "match_score": .3},
            {"rank": 3, "career": "Electrical Engineering", "match_score": .2}]


@pytest.fixture
def connection(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"user_id": 1, "role": db.STUDENT}, {"role": db.STUDENT},
                                  {"username": db.DEMO_STUDENT, "is_demo": True}]
    cursor.lastrowid = 9
    monkeypatch.setattr(db, "_connect", lambda: connection)
    return connection


def test_complete_snapshot_and_all_three_results_commit(connection, results):
    assert db.save_prediction_run(1, 1, {"gwa": 89, "answers": [3] * 30}, results, "test-model") == 9
    cursor = connection.cursor.return_value
    insert_call = next(call for call in cursor.execute.call_args_list if call.args[0].startswith("INSERT INTO prediction_runs"))
    snapshot = json.loads(insert_call.args[1][2])
    assert snapshot["gwa"] == 89
    assert snapshot["subjects"]["physics"] is None
    assert snapshot["answers"] == [3] * 30
    assert snapshot["riasec_scores"] == dict.fromkeys("RIASEC", 15)
    assert len(cursor.executemany.call_args.args[1]) == 3
    connection.commit.assert_called_once()


def test_result_failure_rolls_back_profile_survey_and_run(connection, results):
    connection.cursor.return_value.executemany.side_effect = pymysql.IntegrityError(1062, "private")
    with pytest.raises(db.DatabaseError):
        db.save_prediction_run(1, 1, {"gwa": 89, "answers": [3] * 30}, results, "test-model")
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()


def test_demo_rerun_reuses_existing_snapshot_without_writing(connection, results):
    features = {"gwa": 89, "answers": [3] * 30}
    snapshot, _ = db._prediction_payload(features, results, "test-model")
    cursor = connection.cursor.return_value
    cursor.fetchall.return_value = [{"prediction_run_id": 5, "input_snapshot": json.dumps(snapshot)}]
    assert db.save_prediction_run(1, 1, features, results, "test-model", demo_only=True) == 5
    assert all(call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list)
    cursor.executemany.assert_not_called()


def test_non_demo_cannot_receive_demo_seed(connection, results):
    connection.cursor.return_value.fetchone.side_effect = [
        {"user_id": 1, "role": db.STUDENT}, {"role": db.STUDENT},
        {"username": db.DEMO_STUDENT, "is_demo": False},
    ]
    with pytest.raises(db.DemoConflictError):
        db.save_prediction_run(1, 1, {"gwa": 89, "answers": [3] * 30}, results, "test", demo_only=True)


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "ascending", "bad_rank", "bad_career", "too_few"])
def test_invalid_recommendations_rejected(results, mutation):
    broken = deepcopy(results)
    if mutation == "duplicate":
        broken[1]["career"] = broken[0]["career"]
    elif mutation == "nan":
        broken[0]["match_score"] = float("nan")
    elif mutation == "ascending":
        broken[2]["match_score"] = .9
    elif mutation == "bad_rank":
        broken[0]["rank"] = 4
    elif mutation == "bad_career":
        broken[0]["career"] = "Unknown"
    else:
        broken.pop()
    with pytest.raises(ValueError):
        db._prediction_payload({"gwa": 89, "answers": [3] * 30}, broken, "test")

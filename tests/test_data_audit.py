"""Stored-data audit detects corruption without writes or private error output."""

from unittest.mock import MagicMock
import json

import pytest

from database import db
from validation import SUBJECTS


@pytest.mark.parametrize("damage", [None, "answers", "scores", "missing_result", "owner", "unpaired"])
def test_saved_data_audit(monkeypatch, damage):
    profile = {"user_id": 1, "gwa": 89, **dict.fromkeys(SUBJECTS)}
    response = {"user_id": 1, "answers": json.dumps([3] * 30), "is_complete": True}
    results = [{"rank": 1, "career": "Computer Science", "match_score": .4},
               {"rank": 2, "career": "Information Technology", "match_score": .3},
               {"rank": 3, "career": "Mathematics", "match_score": .1}]
    snapshot, _ = db._prediction_payload({"gwa": 89, "answers": [3] * 30}, results, "test")
    if damage == "answers":
        response["answers"] = json.dumps([7] * 30)
    if damage == "scores":
        snapshot["riasec_scores"]["R"] = 25
    if damage == "missing_result":
        results.pop()
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [
        [{"user_id": 1, "role": db.COUNSELOR if damage == "owner" else db.STUDENT}],
        [profile], [] if damage == "unpaired" else [response],
        [{"prediction_run_id": 2, "user_id": 1, "model_version": "test", "input_snapshot": json.dumps(snapshot)}],
        [{"prediction_run_id": 2, "rank": row["rank"], "career": row["career"], "probability": row["match_score"]} for row in results],
    ]
    monkeypatch.setattr(db, "_connect", lambda: connection)
    if damage:
        with pytest.raises(db.DatabaseError, match="no records were changed"):
            db.audit_saved_data()
    else:
        assert db.audit_saved_data() == {"profiles": 1, "assessments": 1, "prediction_runs": 1, "recommendations": 3}
    assert all(call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list)
    cursor.executemany.assert_not_called()

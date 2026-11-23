"""Question ordering, ties, draft ownership, and validation before persistence."""

from collections import Counter

import pytest

from database import db
from ml.preprocessing import ANSWER_COLUMNS
from ui.riasec import QUESTIONS, holland_summary
from ui.student_inputs import DRAFT_KEY, initialize_draft, validate_draft


def test_question_order_matches_training_and_scoring():
    assert len(QUESTIONS) == 30
    assert tuple(question["id"] for question in QUESTIONS) == ANSWER_COLUMNS
    assert Counter(question["type"] for question in QUESTIONS) == dict.fromkeys("RIASEC", 5)
    assert len({question["text"] for question in QUESTIONS}) == 30


def test_holland_scores_unique_dominant_secondary_and_ties():
    summary = holland_summary([5] * 5 + [4] * 5 + [3] * 20)
    assert summary["dominant"] == ["R"]
    assert summary["secondary"] == ["I"]
    assert summary["scores"]["R"] == 25
    tied = holland_summary([3] * 30)
    assert tied["dominant"] == list("RIASEC")
    assert tied["secondary"] == []
    assert holland_summary([5] * 5 + [4] * 10 + [3] * 15)["secondary"] == ["I", "A"]


def test_draft_requires_owner_gwa_and_all_answers():
    draft = {"owner_user_id": 1, "gwa": "89.125", "subjects": {}, "answers": [3] * 30}
    assert validate_draft(draft, 1)["gwa"] == 89.13
    assert validate_draft(draft, 1)["subjects"]["physics"] is None
    with pytest.raises(db.AuthorizationError):
        validate_draft(draft, 2)
    for value in (None, 74.99, 100.01, float("nan")):
        with pytest.raises(ValueError):
            validate_draft(dict(draft, gwa=value), 1)
    with pytest.raises(ValueError, match="1 still"):
        validate_draft(dict(draft, answers=[3] * 29 + [None]), 1)


def test_switching_owner_discards_other_student_draft(monkeypatch):
    monkeypatch.setattr(db, "get_student_record", lambda actor, target: {"profile": None, "riasec": None})
    state = {DRAFT_KEY: {"owner_user_id": 1, "gwa": 99}, "input_gwa": 99}
    initialize_draft(state, 2)
    assert state[DRAFT_KEY]["owner_user_id"] == 2
    assert state[DRAFT_KEY]["gwa"] is None
    assert "input_gwa" not in state

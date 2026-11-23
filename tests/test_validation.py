"""Validation tests need no database or private credentials."""

from decimal import Decimal

import pytest

from validation import SUBJECTS, score_riasec, validate_academics, validate_answers, validate_grade


@pytest.mark.parametrize("value", [74.99, 100.001, float("nan"), float("inf"), True, [], "bad"])
def test_invalid_grade_rejected(value):
    with pytest.raises(ValueError):
        validate_grade(value)


def test_optional_grades_and_rounding():
    result = validate_academics("89.125", {"physics": 75, "chemistry": 100})
    assert result["gwa"] == Decimal("89.13")
    assert result["physics"] == 75
    assert result["chemistry"] == 100
    assert result["basic_calculus"] is None
    assert set(result) == {"gwa", *SUBJECTS}
    assert validate_grade("") is None


def test_gwa_required_and_unknown_subject_rejected():
    with pytest.raises(ValueError):
        validate_academics(None, {})
    with pytest.raises(ValueError):
        validate_academics(89, {"typo": 90})


@pytest.mark.parametrize("answers", [[3] * 29, [3] * 31, [True] * 30, [3.0] * 30, [0] * 30, [6] * 30, "3" * 30, None])
def test_invalid_answers_rejected(answers):
    with pytest.raises(ValueError):
        validate_answers(answers)


def test_riasec_order_and_totals():
    assert score_riasec([1] * 5 + [2] * 5 + [3] * 5 + [4] * 5 + [5] * 5 + [2] * 5) == {
        "R": 5, "I": 10, "A": 15, "S": 20, "E": 25, "C": 10,
    }

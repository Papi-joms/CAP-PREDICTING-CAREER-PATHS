"""Shared validation for academic inputs and the ordered RIASEC responses."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from numbers import Real
from typing import Mapping, Sequence


SUBJECTS = (
    "general_biology_1", "general_biology_2", "chemistry", "physics",
    "pre_calculus", "basic_calculus", "statistics_and_probability",
)
RIASEC_TYPES = ("R", "I", "A", "S", "E", "C")


def validate_grade(value: object, *, required: bool = False) -> Decimal | None:
    """Validate a grade before rounding to two decimal places; blank means missing."""
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("GWA is required.")
        return None
    if isinstance(value, bool) or not isinstance(value, (str, Real, Decimal)):
        raise ValueError("Grades must be numeric values from 75 to 100.")
    try:
        grade = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Grades must be numeric values from 75 to 100.") from None
    if not grade.is_finite() or not Decimal(75) <= grade <= Decimal(100):
        raise ValueError("Grades must be finite values from 75 to 100.")
    return grade.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_academics(gwa: object, subjects: Mapping[str, object]) -> dict:
    """Return GWA and all seven subject keys, retaining missing grades as None."""
    unknown = set(subjects) - set(SUBJECTS)
    if unknown:
        raise ValueError("Unrecognized subject name.")
    return {"gwa": validate_grade(gwa, required=True), **{
        name: validate_grade(subjects.get(name)) for name in SUBJECTS
    }}


def validate_answers(answers: Sequence[int]) -> list[int]:
    """Require 30 integers, ordered R1-R5, I1-I5, A1-A5, S1-S5, E1-E5, C1-C5."""
    if isinstance(answers, (str, bytes)) or not isinstance(answers, (list, tuple)):
        raise ValueError("RIASEC answers must be an ordered list of 30 integers.")
    if len(answers) != 30 or any(type(answer) is not int or not 1 <= answer <= 5 for answer in answers):
        raise ValueError("Complete all 30 RIASEC answers using integers from 1 to 5.")
    return list(answers)


def score_riasec(answers: Sequence[int]) -> dict[str, int]:
    """Calculate six scores from raw responses rather than storing invented scores."""
    valid = validate_answers(answers)
    return {kind: sum(valid[index * 5:index * 5 + 5]) for index, kind in enumerate(RIASEC_TYPES)}

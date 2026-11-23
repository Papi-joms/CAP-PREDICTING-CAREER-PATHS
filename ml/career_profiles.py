"""Editable simulation assumptions, not validated career-selection rules.

Strengths use SUBJECTS order and represent grade offsets before noise. Holland
codes follow the thesis brief; they must still be reviewed against appropriate
career-interest references. No real students or published empirical estimates
were used to set these values.
"""

from validation import SUBJECTS


CAREER_PROFILES = {
    "Civil Engineering": {"share": .09, "primary": "R", "secondary": "I", "strengths": (0, 0, .5, 3, 3, 2, 1)},
    "Electrical Engineering": {"share": .07, "primary": "R", "secondary": "I", "strengths": (0, 0, 1, 3, 2, 3, 1)},
    "Mechanical Engineering": {"share": .07, "primary": "R", "secondary": "I", "strengths": (0, 0, 1.5, 3.5, 2.5, 2, .5)},
    "Electronics Engineering": {"share": .06, "primary": "R", "secondary": "I", "strengths": (0, 0, .5, 2.5, 2, 3, 2)},
    "Computer Science": {"share": .13, "primary": "I", "secondary": "C", "strengths": (0, 0, .5, 1, 2, 2, 3)},
    "Information Technology": {"share": .14, "primary": "C", "secondary": "I", "strengths": (.5, .5, .5, 1, 1.5, 1.5, 2)},
    "Medicine and Health Sciences": {"share": .11, "primary": "I", "secondary": "S", "strengths": (3, 3, 3, .5, 0, 0, 1)},
    "Biology and Biological Sciences": {"share": .06, "primary": "I", "secondary": "R", "strengths": (3.5, 3.5, 2, 0, 0, 0, 1)},
    "Environmental Science": {"share": .04, "primary": "I", "secondary": "R", "strengths": (2, 2, 2, 1, .5, .5, 2)},
    "Mathematics": {"share": .04, "primary": "I", "secondary": "C", "strengths": (0, 0, 0, 1, 4, 4, 4)},
    "Architecture": {"share": .05, "primary": "A", "secondary": "I", "strengths": (.5, .5, .5, 2, 2.5, 1.5, 1)},
    "Nursing": {"share": .14, "primary": "S", "secondary": "I", "strengths": (3, 3, 2, 0, 0, 0, 1)},
}
CAREERS = tuple(CAREER_PROFILES)
NOISE_LEVEL = .15  # Chosen using validation only; higher = more overlap.
STEM_GWA_WEIGHT = .70  # Simulation only; not an official school GWA formula.
ATYPICAL_SHARE = .08
MISSING_GRADE_SHARE = .12

assert all(len(profile["strengths"]) == len(SUBJECTS) for profile in CAREER_PROFILES.values())

"""Check synthetic assumptions and invariants without enforcing desired accuracy."""

import numpy as np
import pandas as pd
import pytest

from ml.career_profiles import CAREERS, CAREER_PROFILES
from ml.generate_data import class_counts, generate_students, validate_dataset
from ml.preprocessing import ANSWER_COLUMNS, SCORE_COLUMNS
from validation import SUBJECTS


@pytest.fixture(scope="module")
def data():
    return generate_students(600)


def test_seed_reproducibility_and_size(data):
    pd.testing.assert_frame_equal(data, generate_students(600))
    assert len(data) == 600
    assert not data.equals(generate_students(600, seed=43))


@pytest.mark.parametrize("size", [1, 13, 101, 4000])
def test_exact_class_allocation(size):
    counts = class_counts(size)
    assert sum(counts.values()) == size
    assert all(abs(counts[name] - size * CAREER_PROFILES[name]["share"]) <= 1 for name in CAREERS)


def test_ranges_scores_labels_and_missingness(data):
    validate_dataset(data, 600)
    assert set(data.career) == set(CAREERS)
    assert data.gwa.between(75, 100).all()
    for name in SUBJECTS:
        assert data[name].dropna().between(75, 100).all()
        assert data[name].isna().any()
        assert data[name].notna().any()
        assert data.gwa.corr(data[name]) > .5
    assert np.isclose(data.is_atypical.mean(), .08)
    for index, score in enumerate(SCORE_COLUMNS):
        assert (data[score] == data[list(ANSWER_COLUMNS[index * 5:index * 5 + 5])].sum(axis=1)).all()
        assert data[score].between(5, 25).all()


def test_csv_preserves_blank_subjects(data, tmp_path):
    path = tmp_path / "students.csv"
    data.to_csv(path, index=False, na_rep="")
    loaded = pd.read_csv(path)
    pd.testing.assert_frame_equal(data[list(SUBJECTS)].isna(), loaded[list(SUBJECTS)].isna())
    validate_dataset(loaded)


@pytest.mark.parametrize("kwargs", [{"n_rows": 0}, {"seed": -1}, {"noise_level": -1}, {"noise_level": float("nan")}])
def test_bad_generation_parameters(kwargs):
    with pytest.raises(ValueError):
        generate_students(**kwargs)

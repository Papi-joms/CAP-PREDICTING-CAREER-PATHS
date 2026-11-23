"""Generate assumption-based SYNTHETIC students; never actual school records."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.career_profiles import (
    ATYPICAL_SHARE, CAREERS, CAREER_PROFILES, MISSING_GRADE_SHARE, NOISE_LEVEL, STEM_GWA_WEIGHT,
)
from config import PROJECT_ROOT
from ml.preprocessing import ANSWER_COLUMNS, SCORE_COLUMNS, prepare_dataset
from validation import RIASEC_TYPES, SUBJECTS


DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "synthetic_students.csv"


def class_counts(n_rows: int) -> dict[str, int]:
    """Largest-remainder allocation preserves the exact requested row count."""
    shares = np.array([CAREER_PROFILES[name]["share"] for name in CAREERS])
    if not np.isclose(shares.sum(), 1) or (shares <= 0).any():
        raise ValueError("Career shares must be positive and sum to one.")
    expected = shares * n_rows
    counts = np.floor(expected).astype(int)
    for index in np.argsort(-(expected - counts), kind="stable")[:n_rows - counts.sum()]:
        counts[index] += 1
    return dict(zip(CAREERS, map(int, counts)))


def generate_students(n_rows: int = 4000, seed: int = 42, noise_level: float = NOISE_LEVEL) -> pd.DataFrame:
    """Generate correlated grades and profile-influenced Likert responses.

    Atypical students retain assigned labels but follow a different observed
    profile. Missingness is applied AFTER GWA generation, preserving the complete
    STEM component used in the assumed 70/30 blend.
    """
    if type(n_rows) is not int or n_rows < 1:
        raise ValueError("n_rows must be a positive integer.")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer.")
    if isinstance(noise_level, bool) or not np.isfinite(noise_level) or not 0 <= noise_level <= 2:
        raise ValueError("NOISE_LEVEL must be between 0 and 2.")
    rng = np.random.default_rng(seed)
    labels = np.concatenate([np.repeat(name, count) for name, count in class_counts(n_rows).items()])
    rng.shuffle(labels)
    atypical = np.zeros(n_rows, dtype=bool)
    atypical[rng.choice(n_rows, size=round(n_rows * ATYPICAL_SHARE), replace=False)] = True
    records = []
    for index, label in enumerate(labels):
        observed = rng.choice([name for name in CAREERS if name != label]) if atypical[index] else label
        profile = CAREER_PROFILES[observed]
        ability = rng.normal(86, 3.6)
        # Correlated subject grades share a latent academic ability. Profile
        # offsets are modest; related careers deliberately overlap.
        strength_scale = 1.6 / (1 + .4 * noise_level)
        complete_grades = np.round(np.clip(
            ability + np.array(profile["strengths"]) * strength_scale
            + rng.normal(0, .9 + 2 * noise_level, len(SUBJECTS)), 75, 100), 2)
        non_stem = float(np.clip(ability + rng.normal(0, 2), 75, 100))
        gwa = round(float(STEM_GWA_WEIGHT * complete_grades.mean() + (1 - STEM_GWA_WEIGHT) * non_stem), 2)
        # A shared response tendency and dimension variation yield correlated
        # answers within a dimension; scores are sums, not generated separately.
        response_tendency = rng.normal(0, .25)
        raw = []
        for kind in RIASEC_TYPES:
            tendency = 4.25 if kind == profile["primary"] else 3.65 if kind == profile["secondary"] else 2.55
            tendency = 3 + (tendency - 3) / (1 + .35 * noise_level)
            dimension = tendency + response_tendency + rng.normal(0, .25 + .45 * noise_level)
            raw.extend(np.clip(np.rint(rng.normal(dimension, .45 + .35 * noise_level, 5)), 1, 5).astype(int).tolist())
        observed_grades = complete_grades.copy()
        observed_grades[rng.random(len(SUBJECTS)) < MISSING_GRADE_SHARE] = np.nan
        records.append({
            "student_id": index + 1, "gwa": gwa,
            **dict(zip(SUBJECTS, observed_grades)), **dict(zip(ANSWER_COLUMNS, raw)),
            **{f"riasec_{kind}": sum(raw[i * 5:i * 5 + 5]) for i, kind in enumerate(RIASEC_TYPES)},
            "career": str(label), "is_atypical": bool(atypical[index]),
        })
    return pd.DataFrame.from_records(records)


def validate_dataset(frame: pd.DataFrame, expected_rows: int | None = None) -> None:
    """Reject corrupt inputs/labels and inconsistent derived scores before training."""
    if expected_rows is not None and len(frame) != expected_rows:
        raise ValueError("Dataset size does not match n_rows.")
    if "student_id" not in frame or frame["student_id"].isna().any() or frame["student_id"].duplicated().any():
        raise ValueError("Student IDs must be present and unique.")
    if "career" not in frame or not frame["career"].isin(CAREERS).all():
        raise ValueError("Dataset has missing or unknown career labels.")
    prepare_dataset(frame)


def sanity_report(frame: pd.DataFrame) -> str:
    """Return descriptive checks without presenting them as empirical findings."""
    counts = frame["career"].value_counts().reindex(CAREERS, fill_value=0)
    numeric = frame.select_dtypes(include="number")
    parts = ["SYNTHETIC, assumption-based data — not real student records.",
             f"Total records: {len(frame)}",
             "Class counts and actual percentages:\n" + pd.DataFrame({"count": counts, "percent": counts / len(frame) * 100}).to_string(),
             "Mean GWA per career:\n" + frame.groupby("career")["gwa"].mean().to_string(),
             "Mean RIASEC scores per career:\n" + frame.groupby("career")[list(SCORE_COLUMNS)].mean().to_string(),
             "GWA/subject correlations:\n" + frame[["gwa", *SUBJECTS]].corr()["gwa"].drop("gwa").to_string(),
             "Numeric minima and maxima:\n" + numeric.agg(["min", "max"]).T.to_string(),
             "Missing optional grades:\n" + frame[list(SUBJECTS)].isna().sum().to_string(),
             f"Atypical profiles: {frame['is_atypical'].mean():.2%}"]
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--noise-level", type=float, default=NOISE_LEVEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA_PATH)
    args = parser.parse_args()
    try:
        frame = generate_students(args.rows, args.seed, args.noise_level)
        validate_dataset(frame, args.rows)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        csv_text = frame.to_csv(index=False, na_rep="", lineterminator="\n")
        # Avoid silently replacing a different dataset after a completed run.
        if args.output.exists() and args.output.read_text(encoding="utf-8") != csv_text:
            raise ValueError("Output already contains a different dataset. Choose a new --output path for a new experiment.")
        args.output.write_text(csv_text, encoding="utf-8", newline="")
        metadata = {"synthetic": True, "generator_version": "1.0", "n_rows": args.rows,
                    "seed": args.seed, "noise_level": args.noise_level,
                    "stem_gwa_weight": STEM_GWA_WEIGHT, "atypical_share": ATYPICAL_SHARE,
                    "missing_grade_share": MISSING_GRADE_SHARE, "profiles": CAREER_PROFILES,
                    "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
        args.output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        report = sanity_report(frame)
        args.output.with_suffix(".checks.txt").write_text(report, encoding="utf-8")
        print(report)
        print(f"\nSaved: {args.output}")
    except (ValueError, OSError) as error:
        print(f"Generation failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

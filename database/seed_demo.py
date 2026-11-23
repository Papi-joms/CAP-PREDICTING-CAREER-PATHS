"""Safely provision demos; optionally add predictions from the actual trained model."""

import argparse
import os

import bcrypt

from config import ConfigurationError, load_config
from database.db import (
    DatabaseError, create_tables, inspect_schema, seed_demo_accounts,
    verify_demo_passwords,
    DEMO_STUDENT, get_student_record, save_prediction_run,
)


def read_demo_passwords() -> tuple[str, str]:
    """Read local environment secrets and validate bcrypt's UTF-8 byte limit."""
    load_config()
    passwords = []
    for name in ("DEMO_STUDENT_PASSWORD", "DEMO_COUNSELOR_PASSWORD"):
        password = os.environ.get(name, "")
        if not password.strip() or not 12 <= len(password.encode("utf-8")) <= 72:
            raise ValueError(f"Set {name} in your private .env to a password of 12-72 UTF-8 bytes.")
        passwords.append(password)
    if passwords[0] == passwords[1]:
        raise ValueError("Use different passwords for the two demo accounts.")
    return passwords[0], passwords[1]


def main() -> int:
    """Hash privately, seed transactionally, and verify without printing credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-predictions", action="store_true", help="Use the trained model; preserve existing runs.")
    args = parser.parse_args()
    try:
        student_password, counselor_password = read_demo_passwords()
        student_hash = bcrypt.hashpw(student_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")
        counselor_hash = bcrypt.hashpw(counselor_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")
        create_tables()
        inspect_schema()
        ids = seed_demo_accounts(student_hash, counselor_hash)
        if not verify_demo_passwords(student_password, counselor_password):
            raise DatabaseError("Existing demo passwords differ from .env. Existing accounts were preserved; use their original passwords.")
        if args.with_predictions:
            from ml.predict import load_model, predict_top3
            from validation import SUBJECTS

            model = load_model()
            student_id = ids[DEMO_STUDENT]
            record = get_student_record(student_id, student_id)
            if not record["profile"] or not record["riasec"]:
                raise ValueError("Existing demo student has incomplete inputs; no prediction was created.")
            features = {"gwa": record["profile"]["gwa"],
                        **{name: record["profile"][name] for name in SUBJECTS},
                        "answers": record["riasec"]["answers"]}
            results = predict_top3(features, model=model)
            run_id = save_prediction_run(student_id, student_id, features, results, model["model_version"], demo_only=True)
    except (ValueError, ConfigurationError, DatabaseError) as error:
        print(f"Demo setup failed: {error}")
        return 1
    print("Demo accounts ready: cpp_demo_student (Student), cpp_demo_counselor (Guidance Counselor).")
    print("Existing demo records were preserved. Demo passwords verified.")
    if args.with_predictions:
        print(f"Demo prediction run ready: {run_id}. Three actual model scores saved; identical seed reruns reuse this run.")
    else:
        print("Prediction history unchanged. Use --with-predictions after Step 1C training to seed model results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""All CPP SQL and connections. Caller IDs must come from authenticated server state.

Never pass an actor ID from a form, query string, or a selected student. Each
protected operation reloads the actor's role from MySQL. auth.py supplies the
authenticated session boundary; these functions are not public HTTP endpoints.
"""

import argparse
from contextlib import contextmanager
import json
import math
import re
from uuid import uuid4
from typing import Iterator, Sequence

import bcrypt
import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from config import ConfigurationError, load_config
from validation import SUBJECTS, score_riasec, validate_academics, validate_answers


STUDENT = "Student"
COUNSELOR = "Guidance Counselor"
DEMO_STUDENT = "cpp_demo_student"
DEMO_COUNSELOR = "cpp_demo_counselor"


class DatabaseError(RuntimeError):
    """A safe database error suitable for display without SQL or credentials."""


class AuthorizationError(PermissionError):
    """The authenticated actor cannot perform this operation."""


class DemoConflictError(DatabaseError):
    """A designated demo username belongs to a non-demo or wrong-role account."""


class UsernameTakenError(DatabaseError):
    """Registration cannot use an existing username."""


def _connect() -> Connection:
    """Open a short-lived connection; do not cache across Streamlit users."""
    settings = load_config()
    return pymysql.connect(
        host=settings.host, port=settings.port, user=settings.user,
        password=settings.password, database=settings.database,
        charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
        connect_timeout=5, read_timeout=15, write_timeout=15,
        init_command="SET time_zone = '+08:00'",  # Display TIMESTAMP values in Asia/Manila.
    )


@contextmanager
def _transaction() -> Iterator[Connection]:
    """Commit only on success, roll back on all failures, and always close."""
    connection = None
    try:
        connection = _connect()
        yield connection
        connection.commit()
    except Exception as error:
        if connection is not None:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                pass  # Preserve the original failure; the connection is closed below.
        if isinstance(error, pymysql.MySQLError):
            code = error.args[0] if error.args and isinstance(error.args[0], int) else "unknown"
            raise DatabaseError(
                f"MySQL operation failed (code {code}). Check the server, local configuration, "
                "account permissions, and input constraints. Data transactions are rolled back; "
                "schema creation may already have committed."
            ) from None
        if isinstance(error, RuntimeError) and "cryptography" in str(error):
            raise DatabaseError("MySQL authentication needs RSA support. Install requirements.txt and retry.") from None
        raise
    finally:
        if connection is not None:
            connection.close()


_GRADE_COLUMNS = ",\n".join(
    f"{name} DECIMAL(5,2) NULL, CONSTRAINT chk_{name} CHECK ({name} BETWEEN 75 AND 100)"
    for name in SUBJECTS
)

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(64) NOT NULL,
        password_hash VARCHAR(60) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        role VARCHAR(18) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        is_demo BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        CONSTRAINT uq_users_username UNIQUE (username),
        CONSTRAINT chk_users_role CHECK (role IN ('Student', 'Guidance Counselor')),
        CONSTRAINT chk_users_demo CHECK (is_demo IN (0, 1)),
        INDEX idx_users_role (role)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    f"""CREATE TABLE IF NOT EXISTS student_profiles (
        user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        gwa DECIMAL(5,2) NOT NULL,
        {_GRADE_COLUMNS},
        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        CONSTRAINT chk_gwa CHECK (gwa BETWEEN 75 AND 100),
        CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(user_id)
            ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS riasec_responses (
        user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        answers JSON NOT NULL,
        is_complete BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        CONSTRAINT chk_riasec_complete CHECK (is_complete = 1),
        CONSTRAINT chk_riasec_answers CHECK (
            JSON_TYPE(answers) = 'ARRAY' AND JSON_LENGTH(answers) = 30),
        CONSTRAINT fk_riasec_user FOREIGN KEY (user_id) REFERENCES users(user_id)
            ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS prediction_runs (
        prediction_run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNSIGNED NOT NULL,
        model_version VARCHAR(100) NOT NULL,
        input_snapshot JSON NOT NULL,
        created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        CONSTRAINT chk_snapshot_object CHECK (JSON_TYPE(input_snapshot) = 'OBJECT'),
        CONSTRAINT fk_runs_user FOREIGN KEY (user_id) REFERENCES users(user_id)
            ON DELETE RESTRICT,
        INDEX idx_runs_user_date (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS predictions (
        prediction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        prediction_run_id BIGINT UNSIGNED NOT NULL,
        `rank` TINYINT UNSIGNED NOT NULL,
        career VARCHAR(100) NOT NULL,
        probability DOUBLE NOT NULL,
        created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        CONSTRAINT chk_prediction_rank CHECK (`rank` BETWEEN 1 AND 3),
        CONSTRAINT chk_prediction_score CHECK (probability BETWEEN 0 AND 1),
        CONSTRAINT uq_run_rank UNIQUE (prediction_run_id, `rank`),
        CONSTRAINT uq_run_career UNIQUE (prediction_run_id, career),
        CONSTRAINT fk_predictions_run FOREIGN KEY (prediction_run_id)
            REFERENCES prediction_runs(prediction_run_id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
)


def check_connection() -> dict:
    """Return non-secret connection details for the setup command."""
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE() AS database_name, CURRENT_USER() AS account, VERSION() AS version")
        return cursor.fetchone()


def create_tables() -> None:
    """Create missing tables only. MySQL DDL auto-commits; this is not a migration."""
    with _transaction() as connection, connection.cursor() as cursor:
        for statement in SCHEMA:
            cursor.execute(statement)


def inspect_schema() -> dict:
    """Read schema metadata; report mismatches rather than silently modifying tables."""
    expected = {
        "users": {"user_id", "username", "password_hash", "role", "is_demo", "created_at"},
        "student_profiles": {"user_id", "gwa", *SUBJECTS, "updated_at"},
        "riasec_responses": {"user_id", "answers", "is_complete", "updated_at"},
        "prediction_runs": {"prediction_run_id", "user_id", "model_version", "input_snapshot", "created_at"},
        "predictions": {"prediction_id", "prediction_run_id", "rank", "career", "probability", "created_at"},
    }
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")
        engines = {row["TABLE_NAME"]: row["ENGINE"] for row in cursor.fetchall()}
        cursor.execute("SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()")
        columns: dict[str, set] = {}
        for row in cursor.fetchall():
            columns.setdefault(row["TABLE_NAME"], set()).add(row["COLUMN_NAME"])
        cursor.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE()")
        constraints = {row["CONSTRAINT_NAME"] for row in cursor.fetchall()}
    required_constraints = {
        "uq_users_username", "chk_users_role", "chk_users_demo", "chk_gwa",
        "fk_profiles_user", "fk_riasec_user", "chk_riasec_complete", "chk_riasec_answers",
        "fk_runs_user", "chk_snapshot_object", "fk_predictions_run", "chk_prediction_rank",
        "chk_prediction_score", "uq_run_rank", "uq_run_career",
        *(f"chk_{name}" for name in SUBJECTS),
    }
    if any(engines.get(table) != "InnoDB" or columns.get(table) != names for table, names in expected.items()):
        raise DatabaseError("Schema is missing tables/columns or has incompatible tables. Do not reset existing data; review the schema.")
    if not required_constraints <= constraints:
        raise DatabaseError("Required database constraints are missing. Review the existing schema before continuing.")
    return {"tables": sorted(expected), "required_constraints": len(required_constraints)}


def _authorize(cursor: DictCursor, actor_user_id: int, target_user_id: int | None = None, *, write: bool = False) -> dict:
    """Reload roles and enforce ownership. Actor ID must be server-authenticated."""
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise AuthorizationError("Authentication is required.")
    cursor.execute("SELECT user_id, username, role FROM users WHERE user_id = %s FOR SHARE", (actor_user_id,))
    actor = cursor.fetchone()
    if not actor or actor["role"] not in (STUDENT, COUNSELOR):
        raise AuthorizationError("Authentication is required.")
    if actor["role"] == STUDENT and target_user_id != actor_user_id:
        raise AuthorizationError("Students may access only their own records.")
    if write and (actor["role"] != STUDENT or target_user_id != actor_user_id):
        raise AuthorizationError("Counselor access is read-only.")
    if target_user_id is not None:
        if type(target_user_id) is not int or target_user_id <= 0:
            raise AuthorizationError("A valid student is required.")
        cursor.execute("SELECT role FROM users WHERE user_id = %s FOR SHARE", (target_user_id,))
        target = cursor.fetchone()
        if not target or target["role"] != STUDENT:
            raise AuthorizationError("A valid student is required.")
    return actor


def _save_inputs(cursor: DictCursor, user_id: int, academics: dict, answers: list[int]) -> None:
    """Save two related records inside the caller's transaction."""
    columns = ("gwa", *SUBJECTS)
    # Identifiers are fixed application constants, never user-provided strings.
    cursor.execute(
        f"INSERT INTO student_profiles (user_id, {', '.join(columns)}) VALUES ({', '.join(['%s'] * 9)}) "
        "ON DUPLICATE KEY UPDATE " + ", ".join(f"{column} = %s" for column in columns),
        (user_id, *(academics[column] for column in columns), *(academics[column] for column in columns)),
    )
    encoded = json.dumps(answers)
    cursor.execute(
        "INSERT INTO riasec_responses (user_id, answers, is_complete) VALUES (%s, %s, 1) "
        "ON DUPLICATE KEY UPDATE answers = %s, is_complete = 1", (user_id, encoded, encoded),
    )


def save_student_inputs(actor_user_id: int, target_user_id: int, gwa: object, subjects: dict, answers: Sequence[int]) -> None:
    """Validate and atomically save a complete profile; leave prediction history intact."""
    academics = validate_academics(gwa, subjects)
    raw_answers = validate_answers(answers)
    with _transaction() as connection, connection.cursor() as cursor:
        _authorize(cursor, actor_user_id, target_user_id, write=True)
        _save_inputs(cursor, target_user_id, academics, raw_answers)


def list_students(actor_user_id: int) -> list[dict]:
    """Return minimal student choices for a counselor; students cannot enumerate users."""
    with _transaction() as connection, connection.cursor() as cursor:
        _authorize(cursor, actor_user_id)
        cursor.execute("SELECT user_id, username, is_demo FROM users WHERE role = %s ORDER BY username", (STUDENT,))
        return list(cursor.fetchall())


def get_student_record(actor_user_id: int, target_user_id: int) -> dict:
    """Read a student's current inputs and derived scores without authentication fields."""
    with _transaction() as connection, connection.cursor() as cursor:
        _authorize(cursor, actor_user_id, target_user_id)
        cursor.execute("SELECT user_id, username, is_demo FROM users WHERE user_id = %s", (target_user_id,))
        student = cursor.fetchone()
        cursor.execute("SELECT * FROM student_profiles WHERE user_id = %s", (target_user_id,))
        profile = cursor.fetchone()
        cursor.execute("SELECT answers, is_complete, updated_at FROM riasec_responses WHERE user_id = %s", (target_user_id,))
        response = cursor.fetchone()
        if response:
            response["answers"] = json.loads(response["answers"])
            response["scores"] = score_riasec(response["answers"])
        return {"student": student, "profile": profile, "riasec": response}


def get_prediction_history(actor_user_id: int, target_user_id: int) -> list[dict]:
    """Read immutable run snapshots and ranked results, newest run first."""
    with _transaction() as connection, connection.cursor() as cursor:
        _authorize(cursor, actor_user_id, target_user_id)
        cursor.execute(
            "SELECT prediction_run_id, model_version, input_snapshot, created_at FROM prediction_runs "
            "WHERE user_id = %s ORDER BY created_at DESC, prediction_run_id DESC", (target_user_id,),
        )
        runs = list(cursor.fetchall())
        for run in runs:
            run["input_snapshot"] = json.loads(run["input_snapshot"])
            cursor.execute("SELECT `rank`, career, probability FROM predictions WHERE prediction_run_id = %s ORDER BY `rank`", (run["prediction_run_id"],))
            run["recommendations"] = list(cursor.fetchall())
        return runs


def _validate_password_hash(password_hash: str) -> None:
    """Accept bcrypt hashes only; plaintext must never reach an account insert."""
    if not isinstance(password_hash, str) or not re.fullmatch(r"\$2[aby]\$(?:0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{53}", password_hash):
        raise ValueError("A valid bcrypt password hash is required.")


def create_student_account(username: str, password_hash: str) -> int:
    """Registration primitive; callers cannot choose counselor role or demo status."""
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,64}", username):
        raise ValueError("Username must contain 3-64 letters, digits, or underscores.")
    if username.lower().startswith("cpp_demo_"):
        raise ValueError("This username prefix is reserved for demo accounts.")
    _validate_password_hash(password_hash)
    with _transaction() as connection, connection.cursor() as cursor:
        try:
            cursor.execute("INSERT INTO users (username, password_hash, role, is_demo) VALUES (%s, %s, %s, 0)", (username, password_hash, STUDENT))
        except pymysql.IntegrityError as error:
            if error.args[0] == 1062:
                raise UsernameTakenError("That username is unavailable. Choose another username.") from None
            raise
        return int(cursor.lastrowid)


def get_login_record(username: str) -> dict | None:
    """Authentication-only lookup. Never pass this record to UI or session state."""
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id, username, password_hash, role FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def get_user_identity(user_id: int) -> dict | None:
    """Reload a trusted session's identity without retrieving its password hash."""
    if type(user_id) is not int or user_id <= 0:
        return None
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id, username, role FROM users WHERE user_id = %s", (user_id,))
        return cursor.fetchone()


def seed_demo_accounts(student_hash: str, counselor_hash: str) -> dict[str, int]:
    """CLI-only provisioning. Preserve existing demos; rollback on any account conflict."""
    _validate_password_hash(student_hash)
    _validate_password_hash(counselor_hash)
    specs = ((DEMO_STUDENT, STUDENT, student_hash), (DEMO_COUNSELOR, COUNSELOR, counselor_hash))
    academics = validate_academics(89, {
        "general_biology_1": 90, "general_biology_2": 89, "chemistry": 88,
        "physics": 91, "pre_calculus": 90, "basic_calculus": None,
        "statistics_and_probability": 88,
    })
    answers = validate_answers([4, 4, 3, 5, 4, 5, 4, 5, 4, 4, 2, 3, 2, 3, 3,
                                4, 3, 4, 3, 4, 3, 3, 4, 3, 3, 4, 4, 3, 4, 4])
    with _transaction() as connection, connection.cursor() as cursor:
        existing = {}
        for username, role, _ in specs:
            cursor.execute("SELECT user_id, role, is_demo, password_hash FROM users WHERE username = %s FOR UPDATE", (username,))
            row = cursor.fetchone()
            if row and (not row["is_demo"] or row["role"] != role):
                raise DemoConflictError("A designated demo username conflicts with an existing account. No accounts were changed.")
            existing[username] = row
        ids = {}
        for username, role, password_hash in specs:
            row = existing[username]
            if row:
                ids[username] = row["user_id"]
            else:
                cursor.execute("INSERT INTO users (username, password_hash, role, is_demo) VALUES (%s, %s, %s, 1)", (username, password_hash, role))
                ids[username] = int(cursor.lastrowid)
        # Seed inputs only when creating the student. Never reset edited demo data or history.
        if existing[DEMO_STUDENT] is None:
            _save_inputs(cursor, ids[DEMO_STUDENT], academics, answers)
        return ids


def verify_demo_passwords(student_password: str, counselor_password: str) -> bool:
    """CLI-only check; return no password hashes and never log either password."""
    with _transaction() as connection, connection.cursor() as cursor:
        for username, role, password in ((DEMO_STUDENT, STUDENT, student_password), (DEMO_COUNSELOR, COUNSELOR, counselor_password)):
            cursor.execute("SELECT role, is_demo, password_hash FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()
            if not row or not row["is_demo"] or row["role"] != role:
                return False
            if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("ascii")):
                return False
    return True


def _prediction_payload(features: dict, recommendations: list[dict], model_version: str) -> tuple[dict, list[dict]]:
    """Validate and canonicalize a complete immutable prediction snapshot."""
    from ml.career_profiles import CAREERS
    from ml.preprocessing import prepare_features

    prepare_features(features)
    answers = validate_answers(features.get("answers"))
    academics = validate_academics(features["gwa"], {name: features.get(name) for name in SUBJECTS})
    if not isinstance(model_version, str) or not model_version.strip() or len(model_version) > 100:
        raise ValueError("A model version of 1-100 characters is required.")
    if not isinstance(recommendations, list) or len(recommendations) != 3:
        raise ValueError("Exactly three model recommendations are required.")
    seen = set()
    previous_score = 1.0
    for rank, result in enumerate(recommendations, start=1):
        if not isinstance(result, dict) or set(result) != {"rank", "career", "match_score"}:
            raise ValueError("Recommendation fields are invalid.")
        if type(result["rank"]) is not int or result["rank"] != rank or result["career"] not in CAREERS or result["career"] in seen:
            raise ValueError("Recommendation ranks/careers are invalid or duplicated.")
        score = result["match_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= previous_score:
            raise ValueError("Match scores must be finite, descending numbers from 0 to 1.")
        previous_score = score
        seen.add(result["career"])
    if sum(row["match_score"] for row in recommendations) > 1.00000001:
        raise ValueError("Top-three class scores cannot sum to more than one.")
    snapshot = {"gwa": float(academics["gwa"]),
                "subjects": {name: None if academics[name] is None else float(academics[name]) for name in SUBJECTS},
                "answers": answers, "riasec_scores": score_riasec(answers)}
    return snapshot, recommendations


def save_prediction_run(actor_user_id: int, target_user_id: int, features: dict,
                        recommendations: list[dict], model_version: str, *, demo_only: bool = False) -> int:
    """Atomically save inputs plus a NEW historical run and three real model scores.

    Only the CLI demo path uses demo_only: identical model/input combinations
    are reused there. Normal student resubmissions always create new runs.
    Caller must obtain scores/model_version from the trusted prediction module.
    """
    snapshot, results = _prediction_payload(features, recommendations, model_version)
    with _transaction() as connection, connection.cursor() as cursor:
        _authorize(cursor, actor_user_id, target_user_id, write=True)
        cursor.execute("SELECT username, is_demo FROM users WHERE user_id = %s FOR UPDATE", (target_user_id,))
        owner = cursor.fetchone()
        if demo_only:
            if not owner or not owner["is_demo"] or owner["username"] != DEMO_STUDENT:
                raise DemoConflictError("Prediction seeding requires the designated demo Student account.")
            cursor.execute("SELECT prediction_run_id, input_snapshot FROM prediction_runs WHERE user_id = %s AND model_version = %s ORDER BY prediction_run_id", (target_user_id, model_version))
            for run in cursor.fetchall():
                if json.loads(run["input_snapshot"]) == snapshot:
                    return int(run["prediction_run_id"])
            # The seed read inputs before predicting. Refuse a stale snapshot
            # rather than overwrite a concurrent edit to an existing demo.
            cursor.execute("SELECT * FROM student_profiles WHERE user_id = %s FOR UPDATE", (target_user_id,))
            current_profile = cursor.fetchone()
            cursor.execute("SELECT answers FROM riasec_responses WHERE user_id = %s FOR UPDATE", (target_user_id,))
            current_response = cursor.fetchone()
            if (not current_profile or not current_response
                    or float(current_profile["gwa"]) != snapshot["gwa"]
                    or any((None if current_profile[name] is None else float(current_profile[name]))
                           != snapshot["subjects"][name] for name in SUBJECTS)
                    or json.loads(current_response["answers"]) != snapshot["answers"]):
                raise DatabaseError("Demo inputs changed while predicting. Rerun seeding; existing data was preserved.")
        else:
            academics = validate_academics(snapshot["gwa"], snapshot["subjects"])
            _save_inputs(cursor, target_user_id, academics, snapshot["answers"])
        cursor.execute("INSERT INTO prediction_runs (user_id, model_version, input_snapshot) VALUES (%s, %s, %s)",
                       (target_user_id, model_version, json.dumps(snapshot, sort_keys=True)))
        run_id = int(cursor.lastrowid)
        cursor.executemany("INSERT INTO predictions (prediction_run_id, `rank`, career, probability) VALUES (%s, %s, %s, %s)",
                           [(run_id, result["rank"], result["career"], result["match_score"]) for result in results])
        return run_id


def audit_saved_data() -> dict:
    """Local CLI-only, read-only consistency check; return counts, never private data.

    Validates stored inputs and prediction structure, not career suitability or
    equivalence to a possibly newer model. Do not expose this across-user audit
    as a page action. New accounts without inputs are valid.
    """
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id, role FROM users")
        roles = {row["user_id"]: row["role"] for row in cursor.fetchall()}
        cursor.execute("SELECT * FROM student_profiles")
        profiles = {row["user_id"]: row for row in cursor.fetchall()}
        cursor.execute("SELECT user_id, answers, is_complete FROM riasec_responses")
        responses = {row["user_id"]: row for row in cursor.fetchall()}
        cursor.execute("SELECT prediction_run_id, user_id, model_version, input_snapshot FROM prediction_runs")
        runs = list(cursor.fetchall())
        cursor.execute("SELECT prediction_run_id, `rank`, career, probability FROM predictions ORDER BY prediction_run_id, `rank`")
        results = list(cursor.fetchall())
    try:
        if set(profiles) != set(responses):
            raise ValueError("Unpaired inputs")
        for user_id, profile in profiles.items():
            if roles.get(user_id) != STUDENT or not responses[user_id]["is_complete"]:
                raise ValueError("Invalid input owner or completion")
            validate_academics(profile["gwa"], {name: profile[name] for name in SUBJECTS})
            validate_answers(json.loads(responses[user_id]["answers"]))
        by_run = {run["prediction_run_id"]: [] for run in runs}
        for result in results:
            by_run[result["prediction_run_id"]].append({
                "rank": result["rank"], "career": result["career"], "match_score": result["probability"]})
        for run in runs:
            if roles.get(run["user_id"]) != STUDENT or run["user_id"] not in profiles:
                raise ValueError("Invalid prediction owner")
            snapshot = json.loads(run["input_snapshot"])
            features = {"gwa": snapshot["gwa"], **snapshot["subjects"], "answers": snapshot["answers"]}
            canonical, _ = _prediction_payload(features, by_run[run["prediction_run_id"]], run["model_version"])
            if canonical != snapshot:
                raise ValueError("Invalid snapshot or derived scores")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise DatabaseError("Saved-data consistency check failed. Review profiles, complete responses, prediction snapshots, and ranked results locally; no records were changed.") from None
    return {"profiles": len(profiles), "assessments": len(responses),
            "prediction_runs": len(runs), "recommendations": len(results)}


def verify_foundation() -> list[str]:
    """Exercise real constraints/authorization using temporary rows, then roll back.

    Does not seed, delete, or change existing users. Auto-increment gaps are normal
    after rollback. This is an explicit local setup diagnostic, not a UI endpoint.
    """
    checks = []

    class RollbackProbe(Exception):
        pass

    marker = "probe_" + uuid4().hex
    try:
        with _transaction() as connection, connection.cursor() as cursor:
            password_hash = bcrypt.hashpw(uuid4().hex.encode(), bcrypt.gensalt(rounds=4)).decode()
            ids = []
            for suffix, role in (("_student", STUDENT), ("_other", STUDENT), ("_counselor", COUNSELOR)):
                cursor.execute("INSERT INTO users (username, password_hash, role, is_demo) VALUES (%s, %s, %s, 1)", (marker + suffix, password_hash, role))
                ids.append(int(cursor.lastrowid))
            student, other, counselor = ids
            _authorize(cursor, student, student, write=True)
            _authorize(cursor, counselor, student)
            for actor, target, write in ((student, other, False), (counselor, student, True), (student, None, False)):
                try:
                    _authorize(cursor, actor, target, write=write)
                except AuthorizationError:
                    pass
                else:
                    raise DatabaseError("Authorization diagnostic failed.")
            checks.append("student ownership and counselor read-only restrictions")
            _save_inputs(cursor, student, validate_academics(89, {"physics": 91}), [3] * 30)
            cursor.execute("SELECT gwa, physics, basic_calculus FROM student_profiles WHERE user_id = %s", (student,))
            profile = cursor.fetchone()
            if float(profile["gwa"]) != 89 or float(profile["physics"]) != 91 or profile["basic_calculus"] is not None:
                raise DatabaseError("Academic profile round-trip failed.")
            cursor.execute("SELECT answers FROM riasec_responses WHERE user_id = %s", (student,))
            if score_riasec(json.loads(cursor.fetchone()["answers"])) != dict.fromkeys("RIASEC", 15):
                raise DatabaseError("RIASEC round-trip failed.")
            checks.append("academic grades, missing grades, raw answers, and derived scores")

            snapshot = json.dumps({"diagnostic": True})
            cursor.execute("INSERT INTO prediction_runs (user_id, model_version, input_snapshot) VALUES (%s, %s, %s)", (student, "rollback-diagnostic", snapshot))
            run_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO predictions (prediction_run_id, `rank`, career, probability) VALUES (%s, 1, %s, 0.5)", (run_id, "Civil Engineering"))
            invalid_statements = (
                ("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (marker + "_student", password_hash, STUDENT), {1062}),
                ("UPDATE users SET role = %s WHERE user_id = %s", ("Administrator", student), {3819}),
                ("UPDATE student_profiles SET gwa = 74 WHERE user_id = %s", (student,), {3819}),
                ("UPDATE student_profiles SET physics = 101 WHERE user_id = %s", (student,), {3819}),
                ("UPDATE riasec_responses SET answers = %s WHERE user_id = %s", ("[3]", student), {3819}),
                ("INSERT INTO predictions (prediction_run_id, `rank`, career, probability) VALUES (%s, 1, %s, 0.4)", (run_id, "Nursing"), {1062}),
                ("INSERT INTO predictions (prediction_run_id, `rank`, career, probability) VALUES (%s, 4, %s, 0.4)", (run_id, "Nursing"), {3819}),
                ("INSERT INTO predictions (prediction_run_id, `rank`, career, probability) VALUES (%s, 2, %s, 1.1)", (run_id, "Nursing"), {3819}),
                ("INSERT INTO student_profiles (user_id, gwa) VALUES (0, 89)", (), {1452}),
            )
            for statement, parameters, expected_codes in invalid_statements:
                try:
                    cursor.execute(statement, parameters)
                except pymysql.MySQLError as error:
                    if error.args[0] not in expected_codes:
                        raise
                else:
                    raise DatabaseError("A required database constraint was not enforced.")
            checks.append("unique usernames, roles, grades, JSON length, foreign keys, ranks, and scores")
            _save_inputs(cursor, student, validate_academics(90, {}), [4] * 30)
            cursor.execute("SELECT input_snapshot FROM prediction_runs WHERE prediction_run_id = %s", (run_id,))
            if json.loads(cursor.fetchone()["input_snapshot"]) != json.loads(snapshot):
                raise DatabaseError("Profile update changed historical input snapshot.")
            checks.append("profile updates preserve prediction snapshots")
            raise RollbackProbe()
    except RollbackProbe:
        pass
    with _transaction() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE username IN (%s, %s, %s)", (marker + "_student", marker + "_other", marker + "_counselor"))
        if cursor.fetchone()["total"] != 0:
            raise DatabaseError("Rollback diagnostic failed.")
    checks.append("transaction rollback leaves no diagnostic accounts or predictions")
    return checks


def main() -> int:
    """Expose safe, explicit setup commands without printing profile data or secrets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "init", "schema", "verify", "audit"))
    args = parser.parse_args()
    try:
        if args.command == "check":
            info = check_connection()
            print(f"MySQL connection successful: {info['database_name']} as {info['account']}.")
        elif args.command == "audit":
            inspect_schema()
            report = audit_saved_data()
            print("Saved-data consistency passed: " + ", ".join(f"{count} {name}" for name, count in report.items()) + ". No records changed.")
        elif args.command == "verify":
            inspect_schema()
            for check in verify_foundation():
                print(f"PASS: {check}")
        else:
            if args.command == "init":
                create_tables()
            report = inspect_schema()
            print(f"Schema verified: {len(report['tables'])} InnoDB tables, {report['required_constraints']} required named constraints.")
    except (ConfigurationError, DatabaseError) as error:
        print(f"Setup failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

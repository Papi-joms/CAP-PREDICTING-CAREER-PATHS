"""Verify transaction handling, caller authorization, and non-destructive seeding."""

from unittest.mock import MagicMock

import bcrypt
import pymysql
import pytest

from database import db


@pytest.fixture
def connection(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = connection.cursor.return_value
    monkeypatch.setattr(db, "_connect", lambda: connection)
    return connection


def test_transaction_commits_and_closes(connection):
    with db._transaction():
        pass
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_transaction_rolls_back_and_redacts_database_error(connection):
    with pytest.raises(db.DatabaseError) as caught:
        with db._transaction():
            raise pymysql.IntegrityError(1062, "private details")
    assert "1062" in str(caught.value)
    assert "private details" not in str(caught.value)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize("actor,target,write,role", [(1, 2, False, db.STUDENT), (1, 2, True, db.COUNSELOR), (1, None, False, db.STUDENT)])
def test_protected_operations_reject_wrong_actor(connection, actor, target, write, role):
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"user_id": actor, "role": role}
    with pytest.raises(db.AuthorizationError):
        db._authorize(cursor, actor, target, write=write)


@pytest.mark.parametrize("role", [db.STUDENT, db.COUNSELOR])
def test_allowed_reads_reload_actor_and_target(connection, role):
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [{"user_id": 1, "role": role}, {"role": db.STUDENT}]
    db._authorize(cursor, 1, 1)
    assert cursor.execute.call_count == 2


def test_profile_and_answers_failure_rolls_back_together(connection):
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [{"user_id": 1, "role": db.STUDENT}, {"role": db.STUDENT}]
    cursor.execute.side_effect = [None, None, None, pymysql.OperationalError(1205, "private")]
    with pytest.raises(db.DatabaseError):
        db.save_student_inputs(1, 1, 89, {}, [3] * 30)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


@pytest.fixture
def password_hash():
    return bcrypt.hashpw(b"test-only-password", bcrypt.gensalt(rounds=4)).decode()


@pytest.mark.parametrize("conflict", [{"user_id": 2, "role": db.COUNSELOR, "is_demo": 0}, {"user_id": 2, "role": db.STUDENT, "is_demo": 1}])
def test_demo_conflict_checked_before_any_insert(connection, password_hash, conflict):
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [None, conflict]
    with pytest.raises(db.DemoConflictError):
        db.seed_demo_accounts(password_hash, password_hash)
    assert all(call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list)
    connection.rollback.assert_called_once()


def test_repeated_seed_preserves_existing_demo_data(connection, password_hash):
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {"user_id": 1, "role": db.STUDENT, "is_demo": 1},
        {"user_id": 2, "role": db.COUNSELOR, "is_demo": 1},
    ]
    assert db.seed_demo_accounts(password_hash, password_hash) == {db.DEMO_STUDENT: 1, db.DEMO_COUNSELOR: 2}
    assert all(call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list)


def test_seed_new_accounts_saves_raw_answers(connection, password_hash):
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [None, None]
    cursor.lastrowid = 1
    db.seed_demo_accounts(password_hash, password_hash)
    assert cursor.execute.call_count == 6
    sql, params = cursor.execute.call_args.args
    assert "riasec_responses" in sql
    assert db.score_riasec(db.json.loads(params[1]))["R"] == 20


def test_registration_restricts_role_and_parameterizes_username(connection, password_hash):
    cursor = connection.cursor.return_value
    cursor.lastrowid = 7
    assert db.create_student_account("valid_student", password_hash) == 7
    statement, parameters = cursor.execute.call_args.args
    assert "valid_student" not in statement
    assert parameters == ("valid_student", password_hash, db.STUDENT)
    with pytest.raises(ValueError):
        db.create_student_account("cpp_demo_student", password_hash)
    with pytest.raises(ValueError):
        db.create_student_account("valid_student", "plaintext")


def test_invalid_input_never_opens_connection(connection):
    with pytest.raises(ValueError):
        db.save_student_inputs(1, 1, 74, {}, [3] * 30)
    connection.cursor.assert_not_called()

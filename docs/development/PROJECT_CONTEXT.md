# CPP project continuity — Step 6

Updated: 2026-11-23 (Asia/Manila).

## Objective and workflow

Build **CPP: Machine Learning-Based Career Path Prediction System for Senior High School STEM Strand Students**, an undergraduate thesis application for Grade 12 STEM students in the Philippines and Guidance Counselors. Use the user's `thesis prompt JM.docx` as the project requirements. Work one roadmap step at a time and wait for the user's pass confirmation before advancing. The original document describes copy/paste-only chat, but this session has authorized direct local workspace access; do not claim unperformed tests.

Workspace: `C:\Users\USER\Documents\CPP_System`. Windows PowerShell; existing `.venv` uses Python 3.12.10. Use `python` with the environment activated or `.\.venv\Scripts\python.exe` otherwise. No need to recreate the environment. Do not display `.env`, passwords, or hashes. The user prefers beginner-friendly, step-by-step verification.

## Architecture and stack

Python, Streamlit, MySQL, PyMySQL, Pandas, NumPy, scikit-learn RandomForestClassifier, imbalanced-learn SMOTENC pipeline, Joblib, python-dotenv, bcrypt, pytest. Direct versions are pinned in `requirements.txt`; PyMySQL RSA support uses cryptography. No Flask, React, SQLite, or alternative classifiers.

All application SQL and database connections live in `database/db.py`. Input values use parameterized queries. Related writes use InnoDB transactions and rollback. MySQL schema creation auto-commits and is not a migration system. Actor IDs for protected database functions come from authenticated server-controlled session state, not user input; role and ownership are checked against MySQL. `ui/auth.py` now establishes the login/session boundary and rechecks the account on each protected page.

Connection address is `127.0.0.1:3306`; actual account is `cpp_app@localhost`; database is `cpp_system`. The user resolved password/login issues and confirmed both CLI login and `config.py`. The CLI executable is `C:\Program Files\MySQL\MySQL Server 26.10\bin\mysql.exe`. Do not reset the database/account. Do not request passwords in chat.

## Current structure

```text
CPP_System/
  .venv/
  .env                         private, ignored
  .env.example
  .gitignore
  requirements.txt
  config.py
  app.py
  pages/
    1_Student_Dashboard.py
    2_Counselor_Dashboard.py
    3_Student_Report.py
  validation.py
  ui/
    auth.py
    reports.py
    riasec.py
    student_inputs.py
  database/
    db.py
    seed_demo.py
  ml/
    career_profiles.py
    generate_data.py
    predict.py
    preprocessing.py
    train_model.py
  pytest.ini
  README.md
  docs/
    DEMO_GUIDE.md
    development/
      PROJECT_CONTEXT.md
      DEVELOPMENT_HISTORY.md
  data/
    synthetic_students.csv
    synthetic_students.metadata.json
    synthetic_students.checks.txt
    experiments/               baseline055 and noise015 data and reports
  artifacts/
    cpp_model.joblib
    cpp_model.validation.json
    cpp_model.validation.txt
    cpp_model.test.json
    cpp_model.test.txt
    calibration.json
    experiments/               preserved baseline/candidate models and validation
  tests/
    conftest.py
    test_auth.py
    test_auth_ui.py
    test_auth_integration.py
    test_student_inputs.py
    test_student_ui.py
    test_student_integration.py
    test_prediction_ui.py
    test_prediction_step4_integration.py
    test_reports.py
    test_reports_integration.py
    test_data_audit.py
    test_validation.py
    test_db.py
    test_db_integration.py
    test_seed_demo.py
    test_data_generation.py
    test_preprocessing.py
    test_prediction.py
    test_prediction_storage.py
```

`app.py` and `ui/auth.py` provide authentication. The protected Student home includes academic/interest input, review/edit, saving, model recommendations, and historical-run viewing. Step 5 adds `ui/reports.py`, `pages/3_Student_Report.py`, and the Counselor report selector. Students can open My saved report from navigation; counselors can select any registered student for read-only reporting.

## Completed work and current step

- Step 1A: project/environment/configuration complete; user verified MySQL login.
- Step 1B: five tables, foreign keys/indexes/checks, authorized data operations, atomic transactions, bcrypt demo accounts, raw survey answers, safe idempotent seeding. User explicitly confirmed **Step 1B passed**. At that checkpoint 38 tests passed; the Windows pytest-cache warning was harmless. Use `-p no:cacheprovider` to avoid it.
- Step 1C: dataset generation, preprocessing, training/evaluation/artifact, top-three predictions, and real model demo seeding complete. User explicitly confirmed **Step 1C passed**.
- Step 2: registration, both-role login, bcrypt verification, session cleanup/logout, protected navigation/page guards, and failed-registration tab correction complete. User explicitly confirmed **Step 2 passed**.
- Step 3: required GWA, seven optional grades, 30 RIASEC items, scoring, review/edit, and atomic profile/assessment saving complete. User explicitly confirmed **Step 3 passed**.
- Step 4: reviewed prediction generation, shared model/preprocessing, atomic prediction-run saving, top-three match scores, history selection, and new submissions after editing complete. User explicitly confirmed **Step 4 passed**. Next: Step 5 student/counselor reports.
- Step 5: shared saved reports, Student report navigation, Counselor student selection, current academics, assessment completion/scores/Holland types, and historical prediction snapshots complete. **136 tests passed with MySQL integration enabled. User explicitly confirmed Step 5 passed.** Next: Step 6 polish, testing, and finalization.
- Step 6: final review, model-load error handling, read-only stored-data audit, current README, archived development notes, and demonstration/safe-reset guide complete. **145 tests passed with MySQL integration enabled. Awaiting the user's final browser checklist and Step 6 passed confirmation.** No further roadmap features are pending.

## Step 2 authentication and testing details

`ui/auth.py` stores only user_id/username/role in `_cpp_identity`. Password widgets are transient and cleared by form callbacks after success or failure; no hashes or plaintext passwords enter persistent identity. Student registration is fixed-role and validates usernames plus a 12–72 UTF-8-byte password limit. Wrong credentials receive a generic error, including unknown usernames. Counselors are still provisioned only through the seed workflow.

`app.py` uses `st.navigation` based on a freshly fetched database identity. Both page files independently call `require_page_user`; role changes, deleted accounts, and database lookup failures invalidate sessions. Existing protected database operations retain their own ownership/write checks. Logout clears all session keys, including private drafts. No remember-me cookie or completed student-report interface is implemented.

Run the app with `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1`, then open its printed local URL (normally port 8501). The server must remain running while the browser is used. A temporary server on port 8507 was used for HTTP readiness checks and stopped after verification; it is not the user's development server.

`tests/conftest.py` now chooses a fresh `cpp-pytest-<uuid>` temporary directory for each run unless `--basetemp` is explicitly supplied. `pytest.ini` disables the optional cache. This fixes the recurring Windows permission errors without deleting existing temp folders or changing permissions. Plain `python -m pytest -q` now needs no manual temp-directory workaround.

Initial Step 2 verification: 26 authentication/UI tests and **107 total tests** with MySQL passed. Live authentication tests verify demo logins and a real temporary registration/login/duplicate attempt; registration writes are rolled back, leaving no test account.

Subsequent registration fix: untracked tabs could return a failed registration to Log in. `app.py` now uses keyed, state-tracking tabs. Failed registration stays on Create student account, displays its error inside that tab, retains the username, and clears passwords. Successful registration alone switches to Log in and prefills the username. The password requirement is visibly explained below the field. Step 2 has since been confirmed passed.

After the fix, all 11 UI tests and the live registration-to-login integration test passed. Four new regression cases cover short/long/multibyte passwords and mismatched confirmation, then corrected resubmission. Expected current suite size: 111 with integration enabled, or 108 passed/3 skipped without it; the last full-suite run before these four additions was 107 passed. The real-database test rolls back its temporary account.

## Step 3 student inputs

`ui/riasec.py` contains 30 original editable statements, Likert labels, Holland names, and tie-aware scoring summaries. These are not a validated psychological assessment. Keep the five-item R/I/A/S/E/C block order stable to preserve stored answer meaning and compatibility with training data. No actual research validation is claimed.

`ui/student_inputs.py` manages session-only input/review/saved stages and an owner-tagged draft. A new account sees GWA and seven optional numeric inputs plus 30 initially unanswered radios. GWA is required, grades are 75–100 and rounded to two decimals, absent optional grades remain None/SQL NULL, and all answers must be integers 1–5. Incomplete forms stay open without saving and retain entered values. Review displays all inputs, all six scores, and explicit ties; Back to edit restores the complete draft. Save without generating revalidates identity/ownership and calls the existing atomic database save. Save errors retain review state for retry.

Saved accounts open on their saved information with a Review and update my information button. New sessions reload the user's own database inputs; logout clears drafts. The save-only action does not generate a prediction or change history. Step 4 adds a separate reviewed prediction action as described below. Step 5 provides the full saved reports.

Step 3 tests: 8 database-free tests for question/scoring/draft invariants and the actual Streamlit form flow, plus an opt-in real-MySQL review/save/reload test using a temporary account whose writes are rolled back. The Step 3 full suite passed 120 tests. Manual acceptance steps are in [README.md](../../README.md).

## Step 4 prediction integration

`ui/student_inputs.py` now offers Generate recommendations only from the review stage. Saved profiles have a Review and generate recommendations button. The callback revalidates Student identity/ownership, validates the complete draft, loads the shared model through `ml.predict.load_streamlit_model`, calls `predict_top3`, then invokes one atomic `database.db.save_prediction_run`. No profile-only save is performed before inference. A missing/incompatible model or DB failure leaves the review available for correction/retry.

Results are read back from authorized persisted history, with three descending raw class scores shown as match percentages. `_cpp_selected_prediction_run` selects a run belonging to the current Student; it is cleared on logout/owner changes. The saved-input expander uses that run's immutable snapshot, not the current profile. A notice distinguishes old results when current inputs differ. Every explicit reviewed Student submission creates a new run, even with identical inputs; ordinary UI reruns/history selection do not. Only CLI demo seeding remains idempotent for identical inputs/model.

Save without generating remains a save-only option. Editing and saving without predicting preserves previous runs and warns that their inputs differ when applicable. After receiving results, Review and update my information returns to the current draft; another reviewed submission creates a new run while preserving earlier inputs/scores. Counselor prediction generation remains prohibited.

`database.db._connect` now sets the session time zone to `+08:00`, so MySQL TIMESTAMP values are displayed in Asia/Manila without changing the UTC-stored instants. No schema or dependency change, model retraining, or final-test reevaluation was needed.

New tests: six prediction UI cases (including parameterized failures) and three opt-in integration checks for actual-model new-student resubmission/history, existing demo-score reproducibility, and model resource-cache reuse. The ten combined Student/prediction UI tests passed. Current expected full suite: **129 with integration enabled**, or **122 passed/7 skipped** otherwise. Live new-student records roll back; the demo check is read-only. [README.md](../../README.md) contains the review/generate/edit/history manual checklist.

Verification outcome: the full Step 4 suite initially had 128 passed and one failure because the local `.env` had malformed text and was missing the recognized demo-password assignments. Both original passwords were recovered from existing local text and verified against their bcrypt hashes without displaying them. Malformed lines were preserved as comments, the two recognized environment keys were restored, and the previously failing demo-login/access test then passed. No account passwords, profiles, model, or prediction data were reset. Thus all 129 checks are covered by the full run plus the successful targeted retest; no claim of a separate clean 129-test run is intended.

## Database and demo invariants

Tables: `users`, `student_profiles`, `riasec_responses`, `prediction_runs`, `predictions`. Unique usernames and ranks; rank limited to 1–3; grades 75–100; GWA required; seven optional grades; JSON answer array of length 30 plus Python integer/range checks. Foreign keys use RESTRICT to prevent accidental cascading loss.

Demo usernames: `cpp_demo_student` and `cpp_demo_counselor`. Their distinct private passwords are in `.env` under `DEMO_STUDENT_PASSWORD` and `DEMO_COUNSELOR_PASSWORD`; read privately only if needed. Demo seed rejects non-demo/wrong-role username conflicts and preserves existing passwords/profiles/responses/history. It never truncates or deletes records. Passwords are bcrypt-hashed, validated for a maximum of 72 UTF-8 bytes.

`python -m database.seed_demo --with-predictions` uses the actual model, stores complete academic/answer/score snapshots, and reuses a run only for an identical demo input/model combination. Ordinary `save_prediction_run` calls always create a new run, with the profile, survey, run, and three results committed atomically. Counselor access is read-only. Scores are stored under the schema's `probability` column but are exposed as model-generated match scores, not probabilities of career success.

## Synthetic data and preprocessing

Exactly 12 career labels and shares are defined in `ml/career_profiles.py`; retain their spelling. Default 4,000 records, seed 42, selected NOISE_LEVEL 0.15. Correlated grades use latent ability and editable subject offsets. GWA uses 70% complete STEM grades and 30% simulated non-STEM performance. Missing grades (~12%) are introduced afterward and preserved as blank CSV cells. Exactly 8% atypical profiles retain original labels while observations follow a different profile.

Raw answer order: R1–R5, I1–I5, A1–A5, S1–S5, E1–E5, C1–C5; integers 1–5, dimension sums 5–25. These are unvalidated simulation assumptions; the original questionnaire wording is in ui/riasec.py. `prepare_features` handles both raw answers and validated scores, checking consistency when both are supplied. For persisted predictions raw answers are mandatory.

Feature order: GWA, six RIASEC scores, seven subject grades, seven missing flags (21 numeric columns). Optional missing grades use that student's GWA. `prepare_dataset` calls the same per-student function as inference. Career, student_id, and is_atypical never enter the feature matrix.

## Model and evaluation record

Split: 2,800 train / 600 validation / 600 final test, stratified before SMOTENC. SMOTENC uses binary indicator columns 14–20 as categorical and k_neighbors=5; each training class needs at least six records. Random Forest: 200 trees, min_samples_leaf=2, max_features=sqrt, unlimited depth, random_state=42.

Validation-only calibration: noise 0.55 gave top-1 43.50%, top-3 78.33%; noise 0.15 gave top-1 63.83%, top-3 88.50%. The latter was chosen; all other profiles, class shares, atypical/missing rates, split seed, and forest parameters were unchanged. Both experiments are preserved. `artifacts/calibration.json` records the decision made before the final test. This is diagnostic simulation calibration, not empirical proof of realism.

Selected model version: `cpp-rf-v1-9dde8b6b453254c3`.

| Metric | Validation | Final test |
|---|---:|---:|
| Top-1 | 63.83% | 65.00% |
| Top-3 | 88.50% | 89.17% |
| Macro F1 | 0.6114 | 0.6269 |
| Balanced accuracy | 61.86% | 62.70% |

Final-test evaluation was performed once after selection; `--finalize` reuses the existing result instead of evaluating again. Do not tune using the observed final test. Full per-class precision/recall/F1/support, confusion matrices, and feature importances are in artifact sidecars. Minority recalls: Mathematics 58.33%, Environmental Science 70.83% (24 examples each); Electrical/Mechanical recall remains weaker (35.71%/38.10%).

The saved artifact includes exact feature/class metadata, preprocessing config, generator provenance and data hash, dependency versions, split positions, seed, validation metrics, and fitted pipeline. Metadata mismatches fail closed. `load_streamlit_model` uses `st.cache_resource` only for the model, never user data. Joblib artifacts must be trusted local files.

## Verification and known limitations

Step 1C checkpoint: 79 tests with integration enabled. Step 2 expands this to 107 tests (see authentication details above). Coverage includes generation, missingness, identical preprocessing, split/oversampling boundaries, model loading and prediction, artifact/report safeguards, authorization, transaction rollback, seed safety, and the new authentication/UI flows. Additional live checks confirmed exact 4,000-row regeneration, three stored scores equal to inference, identical seed reruns reusing the run, and preservation of profile timestamps/history.

Verification commands (Windows PowerShell):

```powershell
python -m ml.predict
python -m database.seed_demo --with-predictions
$env:CPP_RUN_DB_TESTS = '1'
python -m pytest -q -p no:cacheprovider
Remove-Item Env:CPP_RUN_DB_TESTS
```

All reported ML performance concerns assigned synthetic labels only. It does not establish real-world career suitability, psychological validity, calibrated probabilities, or future success. Choosing a lower generator noise to meet diagnostic ranges must be disclosed in thesis documentation. No actual student research data is used. No classifier comparisons or deployment have been performed.

## Remaining roadmap

Steps 1–5 are confirmed passed. Step 6 implementation and automated verification are complete; await the user's final manual acceptance in [DEMO_GUIDE.md](../DEMO_GUIDE.md). The counselor must never edit students or generate their predictions through the UI. No public deployment, real-student research validation, or new feature work is included.

## Step 5 report views

Verification: full suite **136 passed in 41.31 seconds**, including real MySQL and Streamlit AppTest navigation/report checks. The first targeted run hit the new test's default three-second cold-start timeout; using the existing project's longer AppTest timeout resolved it. Manual browser acceptance remains with the user; checklist is in [README.md](../../README.md).

`ui/reports.py` reads through existing authorized `database/db.py` functions, rechecks the authenticated viewer, and never caches user records. It shows current saved grades and assessment results separately from selected immutable prediction snapshots. A mismatch warning explains when historical inputs differ from the current profile. Empty student lists, absent profiles/assessments/predictions, removed selection IDs, and database/access errors have explicit messages. Tied Holland scores and synthetic-data limitations remain visible.

`pages/3_Student_Report.py` always uses the authenticated student's own ID and links to Student home for review/edit. The Counselor page selects only from the authorized student list and offers no write or inference controls. `tests/test_reports.py` covers switching students, empty reports, selection reset, denied access, and Student ownership despite unrelated selection state. `tests/test_reports_integration.py` opens both roles' real reports, checks navigation and access restrictions, and verifies that viewing does not change the demo's saved inputs/history. No schema changes, model retraining, dependencies, or account changes are required.

## Step 6 finalization and verification

`ml.predict.load_model` now turns common damaged/truncated artifact and missing dependency load failures into an actionable ValueError handled by the UI, rather than exposing an unhandled deserialization traceback. Metadata validation remains enforced. Regression tests cover empty/invalid files; load only trusted joblib artifacts.

`python -m database.db audit` is a local CLI-only read-only consistency check, not a web action. It checks paired student profiles/complete answers, student ownership, validated snapshot academics/answers/derived RIASEC scores, and exactly three ordered valid career scores per run. New accounts with no profile are valid. It returns aggregate counts, not identifying data. It does not recompute historical inference or certify career validity. Six unit cases exercise corruption and read-only behavior; an integration test audits real saved data.

README.md was consolidated into current operating/setup/test/architecture/evaluation instructions. Previous checkpoint text was preserved in [DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md), explicitly marked historical. [DEMO_GUIDE.md](../DEMO_GUIDE.md) provides the presentation sequence, safe demo-reset checklist (no destructive reset), and final browser acceptance steps.

Verified on 2026-11-23: pip check passed; schema confirmed 5 InnoDB tables/22 constraints; full integration suite **145 passed in 36.46 seconds**. The read-only audit passed before and after checks: 3 profiles, 3 assessments, 3 runs, 9 recommendations. CLI inference returned three ordered scores. Two seed runs reused demo prediction run 7 and verified existing passwords. Temporary local Streamlit server health/home HTTP endpoints passed on port 8519; the helper was stopped afterward. HTTP checks are not a manual browser acceptance test. No model retraining or selected final-test reevaluation was performed.

Security scope remains a local thesis prototype: bcrypt, parameterized SQL, role/owner checks, logout cleanup, redacted DB errors, and transaction protections are implemented and tested. No rate limiting, password recovery, MFA, production hosting review, load-test certification, or formal penetration testing is claimed. User acceptance remains pending; do not mark the full project accepted until the user confirms.

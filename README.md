# CPP — Career Path Prediction

Local Streamlit/MySQL thesis application for Grade 12 STEM students in the Philippines
and Guidance Counselors. Students register, enter grades and 30 interest responses,
review/edit inputs, and generate three ranked career/course categories. Counselors
can select students and read their reports, without modifying or predicting for them.

**Research limitation:** training/evaluation uses synthetic, assumption-based data.
Class scores are not probabilities of career success. The original questionnaire is
not a validated psychological assessment. Results support exploration and discussion.

Steps 1–5 were accepted by the user; Step 6 is awaiting final manual acceptance.
See [DEMO_GUIDE.md](docs/DEMO_GUIDE.md) for presentation and safe demo preparation,
[PROJECT_CONTEXT.md](docs/development/PROJECT_CONTEXT.md) for continuity, and
[DEVELOPMENT_HISTORY.md](docs/development/DEVELOPMENT_HISTORY.md) for archived checkpoint details.

## Start the configured installation

Windows PowerShell in `C:\Users\USER\Documents\CPP_System`:

```powershell
.\.venv\Scripts\python.exe config.py
.\.venv\Scripts\python.exe -m database.db check
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Expected: configuration valid, MySQL connected, then a local URL (normally
`http://127.0.0.1:8501`). Keep the terminal running; stop with Ctrl+C. Do not recreate
the working database or environment. Configuration validation alone does not connect.

Demo usernames: `cpp_demo_student`, `cpp_demo_counselor`. Their private application
passwords are in `.env` under `DEMO_STUDENT_PASSWORD` and `DEMO_COUNSELOR_PASSWORD`.
These are different from the database password, `MYSQL_PASSWORD`.

## Use the application

1. Register a Student using a username and matching password confirmation. Passwords
   must contain 12–72 UTF-8 bytes (12–72 ordinary ASCII characters). Registration
   errors remain on the creation tab; password fields clear for re-entry.
2. Enter required GWA and available optional grades (75–100, two decimals). Leave
   unavailable subjects blank. Answer all 30 interest statements using 1–5 values.
3. **Review my information** shows grades, answers, scores, and Holland types.
   **Back to edit** preserves the draft. Incomplete assessments are not saved.
4. **Generate recommendations** atomically saves inputs, snapshot, and three results.
   **Save without generating** saves inputs only. Each explicit Generate creates a new run,
   even for unchanged inputs; ordinary page reruns do not.
5. Open **My saved report** for saved information/history. Old runs retain their
   original inputs; a warning distinguishes them from a changed current profile.
   Use **Review and update my information** to return to Student home.
6. Counselors use the same login form and select a student on Counselor home.
   Counselor registration is not public. Reports have no edit/generate controls.
7. Log out before switching accounts. Logout clears identity, drafts, and selections.

## New installation only

Developed with Python 3.12.10 and MySQL server 26.10.0. Use InnoDB and enforced CHECK
constraints. Other server versions are not claimed as tested. Workbench is an optional
administration client, not the server. Inspect an existing environment before installing.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Expected: `No broken requirements found.` Versions pin direct dependencies, not all
transitive packages. Run this SQL as administrator only if resources do not exist,
replacing the password placeholder privately:

```sql
CREATE DATABASE cpp_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cpp_app'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_UNIQUE_LOCAL_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES
ON cpp_system.* TO 'cpp_app'@'localhost';
```

Inspect existing resources on creation errors; do not reset accounts or grant global
administrator privileges. The configured TCP host is `127.0.0.1:3306`; the matched
MySQL account is `cpp_app@localhost`.

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Edit `.env` privately: enter database credentials and two distinct demo passwords.
Process environment variables override `.env`. Never share credentials, hashes, or
database exports. Then run:

```powershell
.\.venv\Scripts\python.exe config.py
.\.venv\Scripts\python.exe -m database.db check
.\.venv\Scripts\python.exe -m database.db init
.\.venv\Scripts\python.exe -m database.seed_demo
```

Expected: configuration valid, connection successful, 5 InnoDB tables/22 required
named constraints, demo accounts ready. Initialization creates missing tables and
validates the schema; it does not migrate incompatible tables. DDL may auto-commit.

The repository includes the selected model at `artifacts/cpp_model.joblib`, its
evaluation reports, and the selected synthetic dataset. Other generated CSVs and
experimental Joblib files stay local. Load Joblib artifacts only from trusted sources.
To reproduce development on a fresh copy without an artifact:

```powershell
.\.venv\Scripts\python.exe -m ml.generate_data
.\.venv\Scripts\python.exe -m ml.train_model
```

Training evaluates validation only. Freeze decisions before `python -m ml.train_model --finalize`
evaluates the final holdout once; existing final reports are reused. Do not tune on
final results. For new experiments use separate generator `--output`, trainer `--data`
and `--model` paths. Conflicting existing datasets/models are protected from overwrite.

```powershell
.\.venv\Scripts\python.exe -m ml.predict
.\.venv\Scripts\python.exe -m database.seed_demo --with-predictions
```

Expected: three ranked results and a synthetic-data explanation; actual model demo
predictions. Identical demo inputs/model reuse a run. Seeding preserves existing
passwords/profiles/history and rejects non-demo conflicts. It is not a reset command.

## Hosted deployment

Use Python 3.12 and `app.py` as the Streamlit entry point. Install `requirements.txt`
and start the app with `python -m streamlit run app.py`, or select `app.py` as the
main file on a managed Streamlit host. The selected model is ready for inference.

Provide a separate MySQL database that the app host can reach. `127.0.0.1` on a
hosted app refers to that host. Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`,
`MYSQL_USER`, and `MYSQL_PASSWORD` through the host's private environment settings.
On Streamlit Community Cloud, put the values at the top level in the app's
[Secrets settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
Keep credentials out of Git.

From a trusted environment with those database variables set, run
`python -m database.db init` to create the schema and `python -m database.db check`
to verify connectivity before opening the app. For a private demo, optionally set
the two demo password variables and run `python -m database.seed_demo --with-predictions`.

## Verification

Step 6 verification (2026-11-23): **145 tests passed with MySQL integration enabled**;
dependency/schema checks, read-only data audit, CLI prediction, repeated demo seeding,
and temporary local HTTP readiness checks also passed. No selected-model retraining
or final holdout reevaluation was performed. Final browser acceptance is pending.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m database.db schema
.\.venv\Scripts\python.exe -m database.db audit
.\.venv\Scripts\python.exe -m pytest -q
```

`schema` checks tables/constraints. `audit` checks paired current inputs, completed
responses, original snapshot grades/answers/derived scores, and exactly three valid
ranked results per run. It prints aggregate counts only and changes no records.
It does not establish career suitability or recompute scores using a newer model.

Default pytest skips MySQL integration. Include integration on the local development
database with:

```powershell
$env:CPP_RUN_DB_TESTS = '1'
try { .\.venv\Scripts\python.exe -m pytest -q } finally { Remove-Item Env:CPP_RUN_DB_TESTS -ErrorAction SilentlyContinue }
```

Integration includes temporary registration/input/prediction writes rolled back and
read-only demo checks. ID gaps after rollback are normal. `python -m database.db verify` separately
checks constraints and rollback with temporary records. Pytest cache is disabled and
temporary directories are unique to avoid Windows permission conflicts.

Tests cover authentication/authorization, registration UX, validation, transactions,
seed safety, leakage-safe preprocessing/training, model corruption/compatibility,
failed prediction handling, history preservation, reports, and saved-data consistency.
Small isolated test models do not alter the selected model or reevaluate its holdout.
Streamlit AppTest exercises UI behavior; manual browser acceptance remains necessary.

## Architecture

| Files | Responsibility |
|---|---|
| `app.py`, `ui/auth.py`, `pages/` | Authentication, session identity, guarded navigation |
| `ui/student_inputs.py`, `ui/riasec.py`, `validation.py` | Form/review/edit, questionnaire, scoring, validation |
| `ui/reports.py` | Shared saved student/counselor reports |
| `database/db.py`, `config.py`, `database/seed_demo.py` | All SQL/connections, private configuration, safe seeding |
| `ml/career_profiles.py`, `ml/generate_data.py` | Editable simulation assumptions and generation |
| `ml/preprocessing.py`, `ml/train_model.py`, `ml/predict.py` | Shared features, training/evaluation, inference |
| `data/`, `artifacts/`, `tests/` | Dataset/provenance, model/reports/experiments, automated checks |

The five tables are `users`, `student_profiles`, `riasec_responses`, `prediction_runs`,
and `predictions`. Current inputs are separate from immutable historical snapshots.
All application SQL lives in `database/db.py`; values use parameters. Protected operations
reload roles and enforce ownership. Never accept an actor ID from a form/URL. Local
CLI audit/schema/seed tools are not page actions. Transactions commit related writes
together; foreign keys use RESTRICT. MySQL timestamps display in Asia/Manila (+08:00).
Only the shared model is globally cached, never user records. Passwords use bcrypt.

RIASEC order is R1–R5, I1–I5, A1–A5, S1–S5, E1–E5, C1–C5. Each score sums five
answers (5–25); ties are explicit. Seven optional subjects: General Biology 1/2,
Chemistry, Physics, Pre-Calculus, Basic Calculus, Statistics and Probability.
Missing grades remain SQL NULL and use the student's GWA only in preprocessing,
with separate missing indicators.

## Evaluation and limitations

4,000 synthetic rows; seed 42; 12 classes; stratified 2,800/600/600 train/validation/test.
Features: GWA + six RIASEC scores + seven grades + seven missing flags = 21.
Training-only SMOTENC uses flags 14–20 as categorical, k=5; Random Forest uses 200
trees. Target, student ID, and atypical flag never enter the features.

| Metric | Validation | Final test |
|---|---:|---:|
| Top-1 accuracy | 63.83% | 65.00% |
| Top-3 accuracy | 88.50% | 89.17% |
| Macro F1 | 0.6114 | 0.6269 |
| Balanced accuracy | 61.86% | 62.70% |

Model `cpp-rf-v1-9dde8b6b453254c3`. These metrics concern assigned synthetic labels.
Per-student match percentages are different from evaluation accuracy. Top-3 accepts
the label anywhere in three guesses; macro F1/balanced accuracy weight classes equally.

Assumptions include correlated grades, 70% STEM/30% non-STEM GWA blending, 8% atypical
profiles, and about 12% missing optional grades. Generator noise changed from .55 to
.15 using validation only, improving separability. This is simulation calibration,
not proof of realism; disclose it in the thesis. Both experiments and the decision
are preserved in experiment directories and `artifacts/calibration.json`. The final
holdout was evaluated after selection; no further tuning against it is appropriate.

## Troubleshooting and scope

- **1045/access denied:** check local MySQL credentials, matched host, and process
  environment overrides. Do not repeatedly recreate accounts.
- **Incorrect username/password:** use application credentials, not MySQL credentials.
  Editing `.env` does not change an existing demo user's password.
- **Missing/damaged model or version mismatch:** restore the trusted matching model
  and environment. Saved reports remain available without running inference.
- **No recommendations:** complete/review inputs and choose Generate; saving alone
  does not predict. Historical results may differ from the current profile.
- **Schema/audit failure:** preserve data and inspect locally; never drop/truncate
  tables to silence the problem.
- **Unavailable app:** keep MySQL and the Streamlit terminal running, then refresh.

This local thesis prototype has no password recovery, rate limiting, MFA, public
deployment, or load-test certification. Keep the loopback binding for demonstrations.
A public deployment needs separate security/privacy and operational review. No
real-world career validity, validated psychological assessment, or production security
certification is claimed. Application functionality and model evaluation are separate.

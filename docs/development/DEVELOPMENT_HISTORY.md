# CPP historical development checkpoints

Archived in Step 6. Instructions and test counts below describe earlier checkpoints.
Use README.md for current operation and PROJECT_CONTEXT.md for current status.

CPP is a Streamlit and MySQL career guidance application in development for Grade 12 STEM students in the Philippines. Steps 1A–1C provide the environment, database, synthetic data, and trained model. Step 2 adds authentication and protected navigation. Step 3 adds academic inputs and assessment review/edit. Step 4 integrates model recommendations, atomic prediction submissions, and historical results. Full student/counselor report dashboards remain Step 5 work.

The eventual model will use assumption-based synthetic data. Its classification scores will not establish real-world career suitability or probabilities of professional success.

## Files and structure

```text
CPP_System/
  .venv/            existing Python environment
  requirements.txt
  .gitignore
  .env.example
  config.py
  app.py
  auth.py
  pages/
    1_Student_Dashboard.py
    2_Counselor_Dashboard.py
  db.py
  validation.py
  seed_demo.py
  pytest.ini
  tests/
    test_validation.py
    test_db.py
    test_seed_demo.py
    test_db_integration.py
  README.md
```

`requirements.txt` pins direct dependencies to versions already installed in this environment, avoiding unnecessary upgrades. Scikit-learn and imbalanced-learn must remain compatible; verify both dependency metadata and a small SMOTENC/Random Forest fit before model development. Bcrypt 5 rejects passwords longer than 72 bytes, which later authentication validation must handle explicitly.

`.gitignore` excludes credentials, the virtual environment, caches, and generated datasets/models. `.env.example` lists configuration keys without a real password; copy it locally before entering your credentials.

`config.py` loads settings relative to the project directory and validates required values, port range, and a conservative database-name format. It preserves the password exactly, excludes it from the configuration object's representation, and never connects to MySQL; all later application SQL and connection code will live in `db.py`.

`README.md` records the setup commands, expected results, and acceptance checklist. Future directories `pages/`, `data/`, and `artifacts/` will be created when their first files are needed; future Python modules are deliberately deferred.

## 1. Verify the existing environment

Windows PowerShell, in the project folder with the existing environment activated:

```powershell
python --version
python -m pip list
python -m pip check
```

Expected: `Python 3.12.10`, the dependencies pinned in `requirements.txt`, and `No broken requirements found.` If opening a new terminal without activation, use `.\.venv\Scripts\Activate.ps1` first. Do not recreate the existing environment.

Only if dependencies are missing or differ from the pins:

```powershell
python -m pip install -r requirements.txt
python -m pip check
```

Expected: successful installation (or `Requirement already satisfied`) and no broken requirements. These are direct dependency pins, not a complete transitive lock file.

## 2. Create the database and dedicated account

Open MySQL Workbench or your MySQL administrator console on the local server. The `mysql` executable was not found on PATH during the initial inspection; Workbench's SQL editor can run these same statements.

Run this SQL as an administrator. Replace the password placeholder locally with a unique password; do not paste the real password into chat. This snippet is for initial setup and intentionally fails if the account/database already exists: inspect existing resources instead of resetting them.

```sql
CREATE DATABASE cpp_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cpp_app'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_UNIQUE_LOCAL_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES
ON cpp_system.* TO 'cpp_app'@'localhost';
SHOW GRANTS FOR 'cpp_app'@'localhost';
```

Expected: statements succeed and grants are restricted to `cpp_system.*`, without administrator privileges. The app will use TCP host `127.0.0.1` and port `3306`; use the server's actual port if different. MySQL account matching may depend on local host resolution: if login fails, inspect the matched host/account rather than granting access from `%`.

Create a NEW Workbench connection using hostname `127.0.0.1`, port `3306`, and username `cpp_app`. Enter the password privately and run:

```sql
SELECT CURRENT_USER(), DATABASE(), VERSION();
USE cpp_system;
SELECT DATABASE(), 1 AS connection_ok;
```

Expected: the dedicated account is authenticated, then `cpp_system` and `1`. This tests actual login separately from Python configuration validation. No application tables are created in Step 1A.

Alternatively, if the MySQL client becomes available on PATH, Windows PowerShell:

```powershell
mysql --host=127.0.0.1 --port=3306 --user=cpp_app --password --database=cpp_system --execute="SELECT DATABASE(), 1 AS connection_ok;"
```

Enter the password at the prompt, never as a command argument. Expected: `cpp_system` and `1`. PyMySQL connectivity and any server authentication plugin requirements will be tested in Step 1B, when `db.py` is introduced.

## 3. Configure Python

Windows PowerShell (this preserves an existing .env):

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
```

Set `MYSQL_PASSWORD` to the password chosen above, and save locally. Use a single-quoted dotenv value when the password contains spaces or `#`; never commit or share this file. Existing process environment variables take precedence over `.env`, so remove stale overrides if configuration differs unexpectedly.

```powershell
python config.py
```

Expected: `Configuration valid. MySQL connectivity has not been tested.` Missing settings or an invalid port/name produce a clear error and exit code 1, without printing credentials.

## Pass/fail checklist

- Python is 3.12.10 and `python -m pip check` passes.
- Required imports and a small SMOTENC/Random Forest pipeline run successfully.
- The dedicated MySQL account can connect and select `cpp_system`.
- Local `.env` contains the matching settings and `python config.py` succeeds.
- Credentials remain private and `.env` is ignored.
- No future application modules or database tables have been created.

Step 1A passed: the user confirmed a successful `cpp_app@localhost` login to `cpp_system` and configuration validation. The connection address remains `127.0.0.1`; account host and connection address are different settings. Do not rerun account creation on this configured installation.

## Step 1B — Database foundation

### Objective and files

Create all five tables and reusable database operations, then safely seed one demo Student and one demo Guidance Counselor. No persistent prediction records are created until Step 1C has trained a real model.

- `db.py` owns every application SQL statement and connection. It provides connection/schema commands, registration storage, authorized profile reads/writes, counselor student selection, history reads, and transaction-safe demo provisioning.
- `validation.py` is an additional shared module so later forms and preprocessing can reuse grade and RIASEC validation. It preserves missing subjects and calculates scores only from the original 30 answers.
- `seed_demo.py` reads private demo passwords from the environment, hashes them with bcrypt, and delegates all storage to `db.py`. Reruns preserve existing demo passwords, edited profiles, responses, and history; non-demo or wrong-role name conflicts cause rollback before any account insert.
- `.env.example` documents the two new demo password settings; actual values stay in `.env`. The configured workspace has locally generated, distinct demo passwords already saved there; view them privately only when needed for the future login UI.
- `requirements.txt` adds PyMySQL's RSA extra and pins `cryptography==50.0.2`. The existing `caching_sha2_password` login can succeed from MySQL's cache without this package, but fresh authentication after a server restart may require RSA support.
- `tests/` contains database-free validation, transaction, permission, and seeding tests plus an opt-in real MySQL check. `pytest.ini` declares the integration marker; normal test runs do not need database access.

The full runnable source is saved in these files; no copying from chat is needed in this workspace.

### Schema and invariants

| Table | Purpose | Key rules |
|---|---|---|
| `users` | Account identity and bcrypt hashes | Unique case-insensitive username; Student or Guidance Counselor role; explicit demo flag |
| `student_profiles` | Current academic inputs | One row per user; GWA required; seven nullable grades, all present grades 75–100 |
| `riasec_responses` | Original ordered answers | One completed 30-answer JSON array per user; incomplete drafts stay out of this table |
| `prediction_runs` | Historical model version and input snapshot | Student foreign key; independent snapshot for each future submission |
| `predictions` | Ranked results belonging to a run | Rank 1–3 and unique within a run; unique career per run; score 0–1 |

All tables use InnoDB, foreign keys, and appropriate indexes. `ON DELETE RESTRICT` protects related records from accidental deletion. Grade values are validated before rounding to two decimal places; SQL constraints also enforce their range. RIASEC item type/range is validated in Python; MySQL additionally checks JSON array shape and length. The database does not store independently fabricated RIASEC scores.

Subject keys are `general_biology_1`, `general_biology_2`, `chemistry`, `physics`, `pre_calculus`, `basic_calculus`, and `statistics_and_probability`. Raw answers are ordered R1–R5, I1–I5, A1–A5, S1–S5, E1–E5, C1–C5. Each score is the sum of its five integer answers, for a range of 5–25. Questionnaire wording is deferred to the input-system step; this is not a validated psychological assessment.

Database operations accept an **actor user ID from authenticated, server-controlled session state**, never an ID supplied by a form or URL. They reload that actor's role from MySQL and check the target student's role/ownership before accessing protected data. Counselors may read profiles/history and enumerate students but cannot save student inputs. Step 2 establishes the trusted session boundary; these storage functions alone are not a complete authentication system. CLI-only schema and seeding functions must never be exposed as page actions.

Profile and survey updates commit together or roll back together. Updating these current records does not touch history. Step 1C adds prediction-writing operations and complete snapshots from actual model outputs, using the tables established in Step 1B.

MySQL table creation auto-commits, so schema initialization is not an atomic data transaction. Repeating it creates missing tables without dropping anything; `schema` reports incompatible existing structures rather than pretending to migrate them. If initialization fails, fix the reported issue and rerun it; never reset production tables.

### Commands and expected outputs

Use Windows PowerShell in the project directory, with the existing environment activated. If it is not active, substitute `.\.venv\Scripts\python.exe` for `python`.

```powershell
python -m pip check
python db.py check
python db.py init
```

Expected:

```text
No broken requirements found.
MySQL connection successful: cpp_system as cpp_app@localhost.
Schema verified: 5 InnoDB tables, 22 required named constraints.
```

The needed RSA dependency has already been installed in this workspace. On another machine, inspect `python -m pip list` first; install `requirements.txt` only if packages are missing or differ.

For a new installation only, privately add distinct `DEMO_STUDENT_PASSWORD` and `DEMO_COUNSELOR_PASSWORD` values to `.env` (12–72 UTF-8 bytes). These are application login passwords, not the MySQL database password. Do not overwrite your working database credentials. Do not paste secrets into source files or chat.

```powershell
python seed_demo.py
python seed_demo.py
```

Expected on both runs:

```text
Demo accounts ready: cpp_demo_student (Student), cpp_demo_counselor (Guidance Counselor).
Existing demo records were preserved. Demo passwords verified.
Prediction records are deferred until the trained model exists in Step 1C.
```

The first creation inserts a sample GWA, optional grades including one missing value, and all 30 raw answers. Existing demo accounts are not reset on subsequent runs. Changing a demo password in `.env` alone does not reset a stored password: the script reports a mismatch rather than silently replacing credentials. Non-demo accounts are never modified. There is no `TRUNCATE`, broad deletion, or demo reset command.

Run the database-free tests and the live diagnostic:

```powershell
python -m pytest -q
python db.py verify
```

Expected: `37 passed, 1 skipped` for normal tests. The live diagnostic prints five PASS lines covering access restrictions, academic/RIASEC round-trips, SQL constraints, history preservation, and rollback. It inserts only temporary diagnostic records and rolls them all back, including temporary constraint-check prediction rows; these are not seeded recommendations. Auto-increment ID gaps after rollback are normal.

To include the same live check in pytest:

```powershell
$env:CPP_RUN_DB_TESTS = '1'
python -m pytest -q
Remove-Item Env:CPP_RUN_DB_TESTS
```

Expected: `38 passed`. The integration check requires the five tables already initialized. Only run it against the local development database.

### Step 1B pass/fail checklist

- PyMySQL connects using `.env`, and all five InnoDB tables have the expected named constraints.
- The demo accounts use bcrypt hashes and their private environment passwords verify.
- The demo student has a GWA, optional subject grades, and 30 raw answers; no invented model predictions are persisted.
- Rerunning seeding preserves existing demo data and creates no duplicate accounts.
- Unit tests reject non-demo username conflicts, student cross-account access, counselor writes, invalid grades, and incomplete answers.
- Live checks verify constraints, complete rollback, and preservation of historical snapshots during profile edits.
- No production/non-demo records are reset or deleted.

Step 1B was confirmed passed by the user. The test counts above describe the Step 1B checkpoint; the suite has expanded in Step 1C. Account-only seeding now ends with `Prediction history unchanged. Use --with-predictions after Step 1C training to seed model results.`

## Step 1C — Synthetic data and model foundation

### Objective and complete source files

Generate reproducible, assumption-based simulated student profiles; train and evaluate a Random Forest using a leakage-safe SMOTENC pipeline; return three ranked outputs; and seed actual model results without resetting demo data. Source files are complete and saved locally, so they do not need to be copied from chat.

| File | Purpose |
|---|---|
| `career_profiles.py` | Editable career names, class shares, subject strengths, and Holland-code assumptions. These are simulation choices, not validated research findings. |
| `generate_data.py` | Correlated academic grades, derived GWA, original Likert answers, missing grades, and 8% atypical profiles. Produces CSV, provenance metadata, and a full sanity report. |
| `preprocessing.py` | Additional shared module used by every training and prediction input. Fills missing subjects with the student's GWA and adds seven binary indicators in a fixed 21-feature order. |
| `train_model.py` | Stratified splitting, SMOTENC/Random Forest fitting, validation reporting, model metadata, and a separate final-test command. Protects existing experiments from accidental overwrite. |
| `predict.py` | Validates saved metadata and inputs, loads the trained artifact, and returns `predict_top3(features_dict)`. Provides a Streamlit resource-cache loader for the later UI and the required match-score explanation. |
| `db.py` | Adds atomic profile/survey/run/result writes with complete historical snapshots. Normal submissions create new runs; identical demo seed submissions reuse an existing run. |
| `seed_demo.py` | Adds `--with-predictions`, which reads the current demo inputs and uses the actual model. Checks demo ownership and preserves existing profiles and historical results. |
| `tests/test_data_generation.py` | Verifies reproducibility, ranges, labels, scores, proportions, and CSV missingness. |
| `tests/test_preprocessing.py` | Checks GWA substitution, missing indicators, feature ordering, training/inference equality, and invalid-input rejection. |
| `tests/test_prediction.py` | Tests isolated small-model training/loading, top-three scores, split separation, minority counts, artifact compatibility, and final-report reuse. Never evaluates the final experiment's holdout during ordinary tests. |
| `tests/test_prediction_storage.py` | Checks complete snapshots, atomic rollback, demo idempotence, and invalid recommendations. |
| `PROJECT_CONTEXT.md` | Current project status, architecture, results, limitations, and the next development step for a new conversation. |

### Data and model choices

The selected CSV has exactly **4,000 synthetic records**, using seed **42**. Its class counts match the requested shares: IT 560, Nursing 560, Computer Science 520, Medicine/Health Sciences 440, Civil 360, Electrical 280, Mechanical 280, Electronics 240, Biology 240, Architecture 200, Environmental Science 160, Mathematics 160. Raw answers are generated first and their six scores are then summed.

Each simulated student's grades share a latent general academic ability, with editable career subject offsets and noise. GWA is a 70% blend of the complete seven-subject average and 30% simulated non-STEM performance; this is not a universal school grading formula. Optional grades are removed only after GWA is computed. The original CSV retains blank cells; approximately 12% of optional grades are missing. Exactly 320 students (8%) retain their assigned label while their observed features follow another profile. The label, student ID, and atypical flag are excluded from model features.

The processed feature order is GWA, R/I/A/S/E/C scores, seven subject grades, and seven corresponding missing flags. Missing grades use the student's GWA, while the flag differentiates imputed from actually reported grades. Validation and test sets do not contribute fitted preprocessing statistics.

Splits contain 2,800 training, 600 validation, and 600 final-test rows. Splitting precedes oversampling. SMOTENC treats columns 14–20 as categorical binary indicators and uses five neighbors; each training class must have at least six records. The pipeline oversamples only during `fit`, not during validation/test/prediction. The Random Forest has 200 trees, minimum leaf size 2, square-root feature selection, unlimited depth, and random seed 42. There is no algorithm comparison or broad hyperparameter search.

Two generator noise settings were compared using **validation only**. Initial noise 0.55 produced 43.50% top-1 and 78.33% top-3 validation accuracy; noise 0.15 produced 63.83% and 88.50%. The second setting was selected and frozen before final-test evaluation. The initial experiment is retained under `data/experiments/baseline055.*` and `artifacts/experiments/baseline055.*`; the candidate is retained under `noise015.*`. The decision is recorded in `artifacts/calibration.json`. Selecting simulation noise to reach a diagnostic difficulty does not establish that the assumptions are empirically realistic.

### Actual recorded evaluation

| Metric | Validation (600 rows) | Final test (600 rows) |
|---|---:|---:|
| Top-1 accuracy | 63.83% | 65.00% |
| Top-3 accuracy | 88.50% | 89.17% |
| Macro F1 | 0.6114 | 0.6269 |
| Balanced accuracy | 61.86% | 62.70% |

Top-1 checks the highest-ranked assigned label; top-3 checks whether that label appears among three outputs. Macro F1 and balanced accuracy give each career equal weight, exposing minority-class weaknesses that overall accuracy can hide. Final-test recall is 58.33% for Mathematics and 70.83% for Environmental Science (24 test examples each). Engineering remains challenging: Electrical recall is 35.71% and Mechanical is 38.10%, consistent with intentionally overlapping profiles. These are small synthetic class samples, not evidence about real students.

Full precision, recall, F1, support, confusion matrices, and impurity-based feature importances are saved in:

- `artifacts/cpp_model.validation.txt` and `.validation.json`.
- `artifacts/cpp_model.test.txt` and `.test.json`.

Feature importance describes this fitted classifier, not causal effects on career suitability. The top-three match scores are the original class outputs, not renormalized to sum to 100%, and are not calibrated probabilities of success. Required explanation:

> The displayed match scores represent the model's relative classification outputs based on the information provided. They are generated using a synthetic training dataset and should be treated as guidance, not as a guarantee of career suitability or future success.

### Artifacts and metadata

- `data/synthetic_students.csv`: selected training dataset, with raw answers and blank optional grades.
- `data/synthetic_students.metadata.json`: generation assumptions and CSV SHA-256 digest.
- `data/synthetic_students.checks.txt`: counts, percentages, mean GWA/scores, correlations, numeric ranges, missingness, and atypical percentage.
- `artifacts/cpp_model.joblib`: trusted local fitted pipeline plus feature order, class labels, preprocessing configuration, seed, library versions, generator provenance, dataset digest, exact split indices, validation metrics, and feature importance.
- Model version: `cpp-rf-v1-9dde8b6b453254c3`.

Load joblib files only from a trusted source: deserialization can execute code. Incompatible feature/class metadata or library versions produce an error instead of silent reordering. `load_streamlit_model()` uses `st.cache_resource` for the shared model only; no student records are globally cached.

### Verify the completed Step 1C

The dataset/model are already generated. No packages were added in this step. Use Windows PowerShell in the project directory:

```powershell
python predict.py
```

Expected: three ranked career names with match scores and the synthetic-data explanation. This CLI uses a documented example with GWA 89, all 30 responses equal to 3, and all optional grades missing; it does not use the demo student's inputs.

```powershell
python seed_demo.py --with-predictions
python seed_demo.py --with-predictions
```

Expected: the same demo prediction run ID on both runs, with three actual model scores saved. The numeric run ID depends on earlier rollback diagnostics; gaps are normal. Current demo inputs, passwords, and previous results are preserved. Normal student prediction submissions use a separate mode that always creates a new run, even for repeated identical inputs.

```powershell
$env:CPP_RUN_DB_TESTS = '1'
python -m pytest -q -p no:cacheprovider
Remove-Item Env:CPP_RUN_DB_TESTS
```

Expected: **79 passed** including the live database checks. Without `CPP_RUN_DB_TESTS`, the MySQL test is skipped; the remaining tests need no database credentials. Disabling pytest's optional cache avoids the Windows cache-access warning seen earlier.

```powershell
python train_model.py --finalize
```

Expected: the recorded final-test summary (65.00% top-1, 89.17% top-3). Since the report exists, this command re-displays it and does **not** evaluate the holdout again. Do not use these final-test results to tune further settings.

### Reproduce a fresh experiment only when needed

Default data generation is reproducible and refuses to overwrite a different dataset. Default training also refuses to overwrite an existing model. To independently reproduce using new files, the commands are:

```powershell
python generate_data.py --rows 4000 --seed 42 --noise-level 0.15 --output data/reproduction/students.csv
python train_model.py --data data/reproduction/students.csv --model artifacts/reproduction/model.joblib
```

The first command prints all data checks. The second fits only the training partition, reports validation, and saves the model without evaluating the final test. Freeze the experiment before explicitly finalizing; creating new paths is not a way to justify repeated tuning against an already observed holdout. The existing selected artifacts already satisfy this step, so these commands are not required for acceptance.

### Step 1C pass/fail checklist

- Exactly 4,000 rows, requested class shares, valid grades/answers/scores, raw missing grades, 8% atypical records, and reproducible seed-42 generation.
- One shared 21-feature transformation, seven binary indicators, and no target/ID/atypical feature leakage.
- Stratified 70/15/15 split before training-only SMOTENC; clear error for insufficient minority counts.
- Validation and final-test metrics reported separately; full per-class metrics, confusion matrices, and feature importance saved.
- Saved artifact reloads, validates metadata, and predicts three ordered valid careers even when all optional grades are missing.
- Actual model scores and complete input snapshots are saved transactionally for the demo student; repeated seeding preserves profile timestamps and history.
- Unit and live checks pass. No unsupported psychological or real-world career-validity claim is made.

Step 1C was confirmed passed by the user. The current authentication step is described below; the 79-test count above is the historical Step 1C checkpoint.

## Step 2 — Authentication and role-based access

### Objective and files

Provide Student registration, Student/Counselor login, password hashing and verification, authenticated session state, logout, role-protected navigation, and page-level authorization.

| File | What changed |
|---|---|
| `app.py` | Streamlit entry point with separate login and Student registration forms. Navigation is built from a freshly verified database identity, never a URL role or student ID. |
| `auth.py` | Reusable username/password validation, bcrypt authentication, Student-only registration, identity refresh, role guards, and complete logout cleanup. Password hashes are never returned to the page or retained in authenticated session state. |
| `db.py` | Adds parameterized authentication-only lookups and safe identity refresh. Duplicate registrations produce an understandable username-unavailable error, while the existing database constraints enforce uniqueness. |
| `pages/1_Student_Dashboard.py` | Student-only page, guarded before displaying content. Step 3 extends this page with the input/review/edit flow described below. |
| `pages/2_Counselor_Dashboard.py` | Counselor-only landing page with read-only access explained. There are no student-editing or prediction-generation controls. |
| `tests/test_auth.py` | Tests password checks/hashing, safe session identity, wrong-password rejection, registration limits, role/session revalidation, and logout cleanup. |
| `tests/test_auth_ui.py` | Uses Streamlit AppTest to operate the actual forms and callbacks, verify both roles' navigation, clear passwords, and reject direct access to the wrong page. Database calls are mocked for these tests. |
| `tests/test_auth_integration.py` | Opt-in live MySQL verification of demo-role login, access restrictions, registration, case-insensitive login, and duplicate usernames. Temporary registration writes are always rolled back; no test account is retained. |
| `tests/conftest.py`, `pytest.ini` | Each test run uses a unique temporary directory, and the optional pytest cache is disabled. This avoids the inaccessible `pytest-of-USER` directory and `.pytest_cache` warning without altering Windows permissions. An explicitly supplied `--basetemp` still takes precedence. |

No new dependencies or database tables were needed. No existing student data, model, or final-test evaluation was reset.

### Authentication behavior

Usernames are 3–64 ASCII letters, digits, or underscores; surrounding whitespace is trimmed. MySQL's username collation makes uniqueness and login case-insensitive. The `cpp_demo_` prefix is reserved for safe demo seeding. Registration always creates a Student; there is no caller-controlled role argument or public counselor registration. Existing counselor provisioning remains through `seed_demo.py`.

Passwords are 12–72 UTF-8 bytes, hashed with bcrypt cost 12, and never silently truncated or stripped. Non-ASCII characters may use more than one byte. The login page gives the same incorrect-username-or-password message for nonexistent accounts and incorrect passwords. An unknown account still performs a dummy bcrypt check.

Streamlit's password widget necessarily receives the submitted value transiently. Callbacks consume and remove password/confirmation widget values on both success and failure; plaintext is never copied into persistent application identity or logged. Authenticated session state contains only `user_id`, `username`, and `role`. Logout clears all session keys, including form drafts and selected-student/navigation state.

Each protected page re-fetches the identity from MySQL and checks its required role. Deleted accounts, changed roles, or failed identity lookups invalidate the session. Database operations separately enforce ownership and counselor read-only access. Hiding navigation links is not the authorization boundary. A browser refresh/new tab may require logging in again because authentication uses the Streamlit server session, not a persistent remember-me cookie. Deployment-wide rate limiting, account recovery, and production hosting are not part of this local thesis checkpoint.

### Launch and test manually

Windows PowerShell in `CPP_System`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Expected: Streamlit starts and prints a local URL, normally `http://127.0.0.1:8501`. Open that address if a browser does not open automatically. Keep the terminal running; Ctrl+C stops the app. Binding to localhost limits this development run to your computer.

1. Open the **Log in** tab. Try an incorrect password for `cpp_demo_student`; expect `Incorrect username or password.` and an empty password field afterward.
2. Log in as `cpp_demo_student` using the private `DEMO_STUDENT_PASSWORD` from `.env`; expect **Student home**, your username, and a **Log out** button. View `.env` privately (for example with Notepad), never paste it or share a screenshot.
3. Click **Log out**; expect the account screen with cleared credentials. Browser navigation must not restore protected content without a valid session.
4. Log in as `cpp_demo_counselor` using `DEMO_COUNSELOR_PASSWORD`; expect **Counselor home**. No student-editing or prediction controls should be available. Log out.
5. Open **Create student account**, choose a non-demo username and unique password, confirm the password, and submit. Expect `Student account created. You can now log in.` This deliberately creates a persistent account you can use in later steps.
6. Log in with that account; expect **Student home**. After logging out, try registering the same username again; expect an unavailable-username message. Short passwords or mismatched confirmation must be rejected.

The counselor page remains an authentication landing page. The student page now contains academic inputs, assessment review/edit, recommendations, and history. The full student/counselor reporting workflow remains Step 5 work.

### Automated verification

Authentication and UI tests without MySQL:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_auth_ui.py -q
```

Expected: **30 passed**. The suite uses a fresh temporary folder automatically, so the earlier `--basetemp` workaround is no longer needed.

Complete suite including local MySQL checks:

```powershell
$env:CPP_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:CPP_RUN_DB_TESTS
```

At the Step 2 checkpoint: **111 tests** including integration. Step 3 expands the suite as described below. Test runs create temporary fixtures and isolated small models, not replacements for the selected trained model or its final-test results.

### Step 2 acceptance checklist

Registration correction: the active account tab is tracked in session state. Invalid passwords, mismatched confirmation, duplicate usernames, or other registration errors stay on **Create student account**, with the username retained and the error shown inside that tab. Password fields clear for re-entry. Only successful creation switches to **Log in**, displays success, and prefills the registered username. The password-length rule is visible below the password field.

Verification after this correction: all 11 UI tests and the live MySQL registration-to-login test passed. Four regression cases cover too-short, too-long ASCII, too-long multibyte passwords, and mismatched confirmation, including correction and successful resubmission.

- Students can register and log in; duplicate usernames and invalid passwords are handled clearly.
- Both demo roles can log in with their own private passwords; wrong passwords are rejected.
- Each role sees its own landing page, with independent page and database authorization checks.
- Student operations cannot read another student's records, and counselors cannot write student data.
- Password/hash values are absent from persistent identity state; password fields clear after submission.
- Logout clears identity and private drafts; stale/deleted/changed identities fail closed.
- Automated tests pass, and the local Streamlit server responds successfully.

The user confirmed **Step 2 passed**, including the corrected registration flow. Do not share passwords or `.env` contents.

## Step 3 — Academic input, interest assessment, and review/edit

### Objective and files

Students can enter required GWA and seven optional grades, answer all 30 interest statements, review every value and their derived scores, return to edit, and explicitly confirm saving. Saving updates the current profile and completed assessment together; it does not create or overwrite predictions.

| File | Purpose |
|---|---|
| `riasec.py` | Additional editable question-definition module containing 30 original statements (five each for R/I/A/S/E/C), Likert labels, type names, and tie-aware Holland summaries. It explicitly identifies this prototype as an unvalidated questionnaire. |
| `student_inputs.py` | Additional module keeping the page small and the input/review/saved state transitions reusable. Captures incomplete drafts in session state only, validates before review and save, and calls the existing protected database operations. |
| `pages/1_Student_Dashboard.py` | Replaces the placeholder with the authenticated student's academic/interest workflow. The counselor page remains read-only and cannot enter this page. |
| `tests/test_student_inputs.py` | Tests stable question order, five items per type, score/tie handling, grade validation, required answers, and draft-owner isolation. |
| `tests/test_student_ui.py` | Exercises empty inputs, incomplete submissions, review without saving, return-to-edit, saving, later editing, and database-failure retries using Streamlit AppTest. |
| `tests/test_student_integration.py` | Tests the real form against MySQL: incomplete input writes nothing, review writes nothing, confirmation persists the full profile/answers, and a reopened session loads them. All temporary test-account writes are rolled back. |

No dependencies or schema changes are needed. All SQL remains in `db.py`; no duplicate persistence logic was introduced. Existing `validation.py` supplies the same 75–100 bounds, two-decimal rounding, and raw-answer scoring used elsewhere.

### Input and scoring rules

- **GWA is required** and appears first. Optional subjects can be left blank and are stored as SQL NULL, not zero or an invented grade.
- All grades must be within 75–100 before rounding to two decimal places.
- A new questionnaire has no preselected answers, including Neutral. Students explicitly select each response from 1 (Strongly Dislike) through 5 (Strongly Like).
- Question order is R1–R5, I1–I5, A1–A5, S1–S5, E1–E5, C1–C5, matching training/preprocessing and persisted answer arrays.
- Each type's score is the sum of its five raw answers, ranging from 5 to 25. Scores are derived rather than stored independently.
- A unique highest score is displayed as the dominant Holland type; the next score level supplies the secondary type or tied secondary types. Tied highest scores are named together, with no arbitrary primary/secondary ordering.
- These original editable questions are not a validated psychological instrument. Do not silently change question order or reinterpret already stored responses.

Incomplete drafts live only in the student's Streamlit session. Validation errors stay on the input form with entered values retained. Review shows GWA, all seven subject grades, all 30 activity/answer pairs, all six scores, and dominant/secondary or tied results. **Back to edit** restores the draft, and **Confirm and save** is the only action that writes it to MySQL. A database failure keeps the review available for retry.

The save callback rechecks the authenticated Student role and draft owner; it never accepts a target student ID from a widget or URL. Profile and raw answers save atomically through `save_student_inputs`. Logout clears drafts; switching draft owners discards the prior student's temporary inputs. Saved records reload on a new login. Saving revised inputs leaves historical prediction snapshots unchanged, and no new predictions are generated in Step 3.

### Manual verification

If Streamlit is already running, refresh the browser. Otherwise start it in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

1. Log in as a Student. A new account starts with the blank input form. An account with saved inputs (such as the demo Student) shows **Your saved information**; click **Review and update my information** to edit.
2. For a new account, click **Review my information** with GWA blank. Expect `GWA is required.` and no database write.
3. Enter a valid GWA, such as `89.50`, and leave some optional grades blank. Answer only one statement and review; expect a message counting unanswered statements, with your entered data preserved.
4. Answer all 30 and review. Expect all grades, six scores, Holland-type summary, and a table of all 30 answers. Data is still not saved at this point.
5. Click **Back to edit**. Confirm your previous inputs are present. Change one answer or grade, then review again and confirm that the summary changes accordingly.
6. Click **Confirm and save**. Expect `Your academic profile and completed interest assessment have been saved.` and **Assessment status: Complete**.
7. Log out and back in. Expect the saved values to reload. Click **Review and update my information** to make later changes.
8. A counselor should still see only the counselor landing page, with no student-editing controls.

Use your development account for manual data changes. The automated integration test uses a temporary account and rolls it back; your manual profile saves intentionally persist.

### Automated verification and acceptance

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_inputs.py tests/test_student_ui.py -q
```

Expected: **8 passed**. These checks do not need a database connection.

```powershell
$env:CPP_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:CPP_RUN_DB_TESTS
```

At the Step 3 checkpoint: **120 passed** with MySQL enabled, or **116 passed, 4 skipped** without it. The unique temporary-directory workaround remains automatic; see Step 4 for current counts.

The user confirmed **Step 3 passed**: incomplete inputs cannot be saved, review/edit preserve values, saved raw answers yield the displayed scores, optional grades remain missing, and saved data reloads with role/ownership checks intact.

## Step 4 — Prediction integration and historical submissions

### Objective and changes

The Student review screen now offers **Generate recommendations**. It loads the trusted saved model with `st.cache_resource`, passes the reviewed raw inputs through the same preprocessing used in training, and gets three ranked outputs. Only after inference succeeds does one database transaction save the current profile, raw survey answers, immutable input snapshot, model version, and three ranked scores.

| File | Step 4 change |
|---|---|
| `student_inputs.py` | Adds reviewed prediction submission, results display, historical-run selection, and the ability to edit and submit again. Errors keep review available without a separate preliminary profile write. |
| `predict.py` | Existing `load_streamlit_model` and `predict_top3` are now called by the Student UI. No model retraining or final-test reevaluation is performed. |
| `db.py` | Existing atomic `save_prediction_run` and authorized history reads are reused. Connections now set session time zone to UTC+08:00 so MySQL TIMESTAMP results display consistently as Asia/Manila. |
| `tests/test_prediction_ui.py` | Checks review gates, ordered score display, ordinary reruns without duplicate writes, explicit resubmissions, historical snapshots, save-only edits, failures, and role-change rejection. |
| `tests/test_prediction_step4_integration.py` | Uses the real trained model and MySQL for new-student submissions, editing/resubmission, reloaded history, unchanged-input resubmission, demo-score reproducibility, and model-resource reuse. Temporary new-student data is rolled back. |

No package or schema changes were needed. The selected model, dataset, and recorded evaluation remain unchanged.

### Review, prediction, and history behavior

- New inputs: complete the form, click **Review my information**, inspect all values, then **Generate recommendations**.
- Existing saved inputs: click **Review and generate recommendations** first. Predictions always require the review stage.
- **Confirm and save** remains available for saving inputs without predictions. This does not create a run; older results are explicitly identified if their inputs differ from the current profile.
- A successful prediction moves to results and stores a new run. An ordinary rerun or history selection never generates a prediction or writes a new run.
- **Review and update my information** returns to editing. A subsequent reviewed submission creates another run, preserving all previous input snapshots and recommendations. Explicitly resubmitting identical inputs also creates a new run; this differs from the deliberately idempotent CLI demo seed.
- **Choose a prediction run (newest first)** selects from the authenticated student's persisted history. The results show the saved date/time in Asia/Manila, model version, and the three original class scores as percentages.
- **View the inputs used for this prediction run** shows the historical GWA, subject grades (including missing values), original 30 answers, and derived scores. It never substitutes the current profile for an old run's inputs.
- If a selected run differs from the current profile, an explicit notice explains the difference. Different inputs can still produce the same top-three career names; the new run and snapshot are what demonstrate a new submission.
- Model-loading/prediction or database errors leave the review in place. Database write failures roll back the full run and related updates. Authorization is rechecked inside the callback and again by the database operation.

The UI displays the synthetic-data match-score explanation next to results. Top-three outputs are not renormalized to 100%, not overall model accuracy, and not probabilities of future career success. These are the 12 course/career group labels specified in the thesis brief, not guaranteed admissions or professional outcomes.

### Manual verification

Refresh the running app, or start it from Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

1. Log in as a Student with completed inputs. Click **Review and generate recommendations**. For a new Student, complete the form and click **Review my information** instead.
2. Inspect your GWA, optional grades, and questionnaire answers. Click **Generate recommendations** once.
3. Expect a success message and three ordered career categories with match scores. Note the selected run number and open its saved-input section.
4. Click **Review and update my information**. Change a grade or answer, review again, and generate another set of recommendations.
5. Expect a new run number. Choose the older run and verify it still shows the original inputs/results; the newer run should contain the edited inputs.
6. Refresh or log out/back in. Saved history should remain available. Refreshing alone must not add a run.
7. Optionally edit and choose **Confirm and save** only. No new run should appear, and old results should be identified as using different inputs if appropriate.

Use your development account when deliberately changing stored inputs. Counselor UI remains read-only and has no prediction-generation controls.

### Automated verification

Windows PowerShell, without database access:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_prediction_ui.py tests/test_student_ui.py -q
```

Expected: **10 passed**. These exercise the real Streamlit callbacks/UI with controlled database/model boundaries.

Full suite with the actual local database and saved model:

```powershell
$env:CPP_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:CPP_RUN_DB_TESTS
```

Expected: **129 passed**, or **122 passed, 7 skipped** without the integration flag. The live prediction test uses temporary accounts/records and rolls them back. The demo-data check reads existing runs and reproduces their scores without adding or changing records. No training/test-set evaluation occurs in these integration checks.

Step 4 passes when generation uses reviewed valid inputs, saved results match model outputs, old snapshots remain intact after edits, new submissions create new runs, history reloads, and counselor/ownership restrictions remain enforced. Stop and report **Step 4 passed** or a sanitized error before Step 5.
# Step 5: Student and Counselor report views

Students now have **My saved report** in the sidebar. It shows current saved GWA,
optional grades, assessment completion, all six RIASEC scores and Holland types,
plus top-three career match scores and prediction history. Unsaved form edits
remain on Student home. Use **Review and update my information** to return there.

Guidance Counselors can select any registered student on Counselor home and view
the same information with read-only controls. Historical predictions show their
original input snapshots, with a warning if those inputs differ from the current
profile. Empty accounts show clear messages rather than invented results.

Manual acceptance checklist:

1. Refresh the running app, log in as a Student, and open **My saved report**.
2. Check GWA, blank optional grades, assessment status, six scores, and Holland types.
3. Select an older prediction run. Expand its saved inputs and verify its scores
   and inputs have not changed after subsequent edits.
4. Follow **Review and update my information** back to Student home.
5. Log out, log in as the demo Counselor, and select a student. Check their report.
6. Switch to another student, including an account without saved inputs if available.
   The prior student's grades and recommendations must disappear.
7. Confirm there are no Counselor edit/save/generate controls and that a Student
   has no student selector or access to Counselor home.

Windows PowerShell, from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_reports.py -q
$env:CPP_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:CPP_RUN_DB_TESTS
```

The report integration check reads existing demo data and verifies it is unchanged.
Other existing integration tests use their established rollback checks. Confirm
**Step 5 passed** after the manual checklist; Step 6 remains separate.


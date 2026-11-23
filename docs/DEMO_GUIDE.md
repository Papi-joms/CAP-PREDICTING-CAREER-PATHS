# CPP demonstration and final acceptance

## Preparation

1. Start MySQL and open the project. Use the existing `.venv` interpreter.
2. Run `python -m pip check`, `python -m database.db schema`, `python -m database.db audit`, and
   `python -m ml.predict`. Resolve errors before presenting.
3. Start `python -m streamlit run app.py --server.address=127.0.0.1`.
4. Verify demo Student/Counselor logins privately. Close `.env`, account administration
   screens, and unrelated private windows before screen sharing.
5. Keep a private backup of the database, source, trusted model/reports, and matching
   dependencies before deliberate demo changes. Do not commit database exports.

## Suggested 5–8 minute presentation

1. **Purpose:** supports academic/career exploration using grades and interests;
   does not guarantee suitability or success.
2. **Student input:** log in, show required GWA, seven optional grades (one blank),
   and 30 answers rated 1–5. Demonstrate that incomplete review is blocked.
3. **Review/predict:** show grades, original responses, six scores, and Holland types.
   Generate three recommendations. Explain relative match scores and why the top
   three need not total 100%.
4. **Edit/history:** edit a grade/answer, review, generate again. Select the earlier
   run and show its unchanged snapshot.
5. **Counselor:** log out, sign in as Counselor, select a student and view reports.
   Show that edit/save/generate controls are absent.
6. **Evaluation:** explain training/practice-validation/final-test separation,
   recorded 65.00% top-1 and 89.17% top-3 on synthetic labels, and the distinction
   from functionality tests. Disclose generator calibration and the unvalidated
   questionnaire. Real-student validation is separate future research.

## Safe demo reset checklist

There is intentionally no destructive reset command.

- Log out/in to clear unsaved drafts and selections without deleting records.
- `python -m database.seed_demo --with-predictions` prepares designated demo data and real
  inference. Identical demo inputs/model reuse a run. It preserves edited demo
  inputs; it does not restore the original example grades/answers.
- To test idempotence, run seeding twice: the same input/model should return the
  same run ID. Normal Student Generate submissions always create new runs.
- Changing `.env` passwords does not reset existing demo passwords. A mismatch
  stops seeding and preserves the accounts.
- For a fresh scenario, register a separate Student through the app using example
  inputs. This deliberately creates persistent records and does not clear others.
- Never use TRUNCATE, broad DELETE, or DROP DATABASE for demo preparation. Any later
  removal should be a separately authorized, scoped operation with a private backup.

## Final browser pass/fail checklist

- Invalid registration passwords stay on the creation tab; valid registration can
  log in. Incorrect login passwords receive a generic error.
- An unanswered assessment item blocks review and retains entered values.
- Completed review can return to editing with inputs preserved.
- Generate shows exactly three ordered careers with the limitation text.
- A subsequent edit/submission preserves the earlier run and its original inputs.
- My saved report works and links back to Student home.
- Counselor switching shows only the selected student's report, including clear
  empty-account states; no password/hash or edit/save/generate control is shown.
- Logout removes authenticated navigation and prior drafts/selections.
- Full integration tests and saved-data audit pass using [README instructions](../README.md).

Automated tests cover Streamlit UI and MySQL; this checklist verifies the actual
browser experience. Report **Step 6 passed** when it succeeds, or provide the exact
sanitized error and triggering action. Never share passwords.

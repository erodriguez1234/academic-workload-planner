# Academic Workload Planner

## Project goal

Build a semester-scale Python prototype that imports Canvas assignments,
estimates their required completion time, and schedules study sessions
before their deadlines.

## Technology stack

- Python
- Streamlit
- SQLite and SQLAlchemy
- pandas
- pytest
- Canvas REST API
- Google Calendar API
- scikit-learn later in development

## Development priorities

1. Build and test the scheduling logic using sample JSON data.
2. Add a simple Streamlit interface.
3. Add SQLite storage.
4. Integrate the Canvas API.
5. Integrate Google Calendar.
6. Experiment with prediction models only after collecting data.

## Coding guidelines

- Keep API, database, scheduling, and interface logic in separate modules.
- Use type hints and clear function names.
- Write tests for scheduling behavior.
- Never commit API keys, tokens, or OAuth credentials.
- Explain significant architectural changes before implementing them.
- Prefer small, focused changes that can be tested independently.
- Do not add a new dependency unless it is necessary.
- Do not replace working code without explaining the reason.

## Learning requirement

This is a student capstone. Explain important code and design decisions
so that the student can understand and present the work independently.
Do not implement large features without breaking them into understandable
steps.

- Eric understands object-oriented programming but is learning Python syntax.
- Explain new syntax, design choices, and test results in beginner-friendly language.
- Follow the scope of the current requested step; do not implement later milestones
  merely because they appear in the plan.
- Prefer tests that describe expected behavior before implementing a new component.

## Session continuity

At the start of a new task, read this file, `README.md`, the current-status and
next-task sections of `docs/project-plan.md`, and recent entries in
`docs/development-journal.md`. Inspect the relevant source, tests, and Git status;
verify documented status against the code. Preserve existing user changes.

Keep stable working instructions here, setup and usage in the README, design and
remaining milestones in the project plan, and dated outcomes in the journal.
Record decisions separately from exploratory ideas. Update these documents at
milestone boundaries when requested; do not rely on previous chat history alone.

## Current checkpoint — November 9, 2026

- Completed: validated `Assignment` dataclass, four synthetic JSON records,
  `load_assignments()`, and model/loader tests.
- Completed: `DurationEstimate`, `rule_based_v1` type-based estimation, and tests
  (79 total passing cases).
- Completed: frozen scheduling input/output models and per-assignment minute accounting
  (173 total passing cases).
- Completed: `build_schedule()` earliest-deadline-first baseline, session splitting,
  dated availability, daily limits, explicit remaining work (194 total passing cases).
- Completed: step 6 failure messages and independent constraint audit
  (219 total passing cases).
- Completed: first local Streamlit page, weekly availability expansion, session-local
  duration adjustments, preferences, session tables, and warnings (253 passing cases).
- Standalone pipeline demo deferred by user request; the page now connects the core modules.
- Completed: read-only Canvas client, all-page retrieval, conversion, status display,
  course/assignment selection, and explicit local import controls (347 passing cases).
- Completed: readable dates/AM-PM controls and optional token persistence in native
  macOS Keychain via keyring (376 passing cases). Never prefill saved tokens in widgets.
- User showed a real Canvas import; agent tests use synthetic records and mocked storage.
  Enter replacement tokens privately in the local app. Never copy tokens into source or tools.
- Completed: step 3 Canvas scheduling path, current editable Canvas planning dates,
  separate historical sample dates, and locally saved duration edits (401 passing cases).
- Canvas minute preferences live in Git-ignored `.local/duration_adjustments.json`;
  no credentials or assignment content belongs in that file. No full database added.
- Completed in code/tests: step 4 local Google OAuth, Keychain renewal/reconnection,
  and explicit dedicated-calendar creation/access (444 passing cases). First live Google authorization remains
  a user action; the user subsequently reported local connection working.
- Google uses a Desktop client at ignored `.local/google_oauth_client.json`, the
  calendar.app.created, calendar.calendarlist.readonly, calendar.events.freebusy scopes,
  and OpenID identity to preserve the calendar only for the
  same verified account. Do not print client configuration, tokens, or callback URLs.
- Completed in code/tests: calendar-aware scheduling and explicit preview/approval export
  (484 total passing cases; mocked Google verification).
  Busy time is subtracted before calling the unchanged scheduler. Future owned bookings count
  toward assignment and daily minutes. Primary/planner plus selected extra calendars are checked.
- Stable event IDs, ownership markers, and ignored owner-only `.local/calendar_exports.json`
  protect retries/restarts. Uncertain attempts require explicit recovery; no automatic retry.
- Old Google consent requires Authorize Google again for new calendar-list/freebusy scopes.
  No personal event titles are read. Normal Calendar events only; Google Tasks is out of scope.
- Completed: local reload preferences for last mode, Canvas site/current class IDs,
  automatic saved Canvas reconnection/fresh import, and noninteractive saved Google resume
  (499 total passing cases). Ignored owner-only .local/planner_preferences.json has no secrets.
  Tests must isolate this path; never exercise real saved connections in automated checks.
- Disconnect disables automatic reconnection; class choices remain saved. First connection
  after upgrading enables resume. Google auto-resume must never launch browser OAuth.
  Plans and export approvals are not persisted. No automatic calendar writes on page load.
- Completed: undated assignment review (manual student deadlines or week-based lower
  priority), saved module-week mapping, and Roll Call filtering (531 passing cases).
  Module lookup is read-only/all-page; refresh configured mappings on re-import. Never
  infer a week from module names/unlock dates. Real Canvas dates override student targets.
- The user clarified end of week means after dated work for that reference week, not a
  hard Sunday due date. Weekly work waits until the last related dated-work day/session,
  can spill to later available dates within the planning horizon, and does not displace
  dated work. Exact accounting/busy/daily limits apply across both passes. Core scheduler
  and estimator unchanged. Preserve the user's Select Classes to Import label.
- Next: user live rehearsal of new consent, busy-aware generation, preview/export, and retries.
  Automatic moving/deleting and changed-schedule reconciliation remain a later milestone.
- No full database exists; database work remains deferred.
- Local Qwen/Ollama estimation was discussed only as a possible later comparison.
- Use the project's `.venv`; avoid installing dependencies into Anaconda/global Python.
- Run tests from the repository root with `.venv/bin/python -m pytest -v`.
- Do not run test files directly through Code Runner; use pytest or VS Code Testing.

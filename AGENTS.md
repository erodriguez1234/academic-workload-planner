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

## Current checkpoint — October 20, 2026

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
- Next: review step 6, then demonstrate the loaded/estimated/scheduled pipeline
  with fitting and overloaded workloads before starting the interface.
- No interface, database, or external integration exists yet.
- Local Qwen/Ollama estimation was discussed only as a possible later comparison.
- Use the project's `.venv`; avoid installing dependencies into Anaconda/global Python.
- Run tests from the repository root with `.venv/bin/python -m pytest -v`.
- Do not run test files directly through Code Runner; use pytest or VS Code Testing.

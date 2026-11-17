# LLM Estimation Handoff — November 16, 2026

## Objective and working style

Eric's next requested milestone is LLM-assisted assignment-duration estimation for the local
Academic Workload Planner. No LLM integration is implemented yet. Work in small increments:
explain significant files/interfaces and Python syntax before implementing, write meaningful
mocked tests first, and stop after the first focused tested increment for review. Eric knows
object-oriented programming and is learning Python. Do not expand into unrelated milestones.

Repository: `/Users/ericrodriguez/Capstone/academic-workload-planner`.
Read AGENTS.md, README.md, project-plan.md sections 11–13 and 21–22, recent journal entries,
and relevant source/tests. Inspect Git before editing and preserve all existing changes.
Use `.venv/bin/python`; never global/Anaconda Python. Verify the documented 533 passing tests
with `.venv/bin/python -m pytest -v`. Verify the latest commit/remote state rather than assuming
that the preceding chat's push succeeded. Do not commit/push without a new request.

## What currently works

- Validated Assignment and DurationEstimate models; synthetic JSON loader and sample mode.
- Rule-based estimates, distinct student-adjusted minutes, and exact requested-minute accounting.
- Greedy earliest-deadline-first scheduling with assignment-ID tie breaks, session splitting,
  availability, student-local daily limits, and timezone-aware deadlines. Google busy intervals
  and retained verified study bookings are handled by a separate adapter.
- Canvas personal-token connection, all-page course/assignment retrieval, conservative type
  conversion, submission status, selected courses/assignments, Roll Call filtering, and reload
  restoration. Credentials stay in native macOS Keychain. Canvas requests are GET only.
- Undated assignments offer Manual deadline or Do not schedule. Real Canvas deadlines win;
  manual dates are separate scheduling inputs. Selected skipped minutes remain unscheduled;
  deselection removes them from requested totals. Module/week inference was removed by request.
- Local Google Desktop OAuth, verified account binding, renewal/reconnection, dedicated planner
  calendar, primary/planner/selected-extra busy-time checks, explicit preview/approval export.
- Generate/Preview automatically detect missing/cancelled confirmed exports and retire old local
  IDs. Free future sessions can be exported again with new deterministic, retry-stable IDs.
  Already-present events are not duplicated; failed reads fail closed. Existing moved/changed
  events remain protected. No Google event update/delete operation is implemented.
- Review unfinished exports handles uncertain/pending attempts. The separate Review deleted
  planner sessions UI and its manual service are removed. Do not restore them.
- Readable dates and AM/PM controls. Current editable Canvas planning dates are separate from
  the intentionally historical October 10–17, 2026 sample demo (390 scheduled + 60 undated minutes).
- The owner reported real export/re-export working. Automated tests use synthetic data/mocks;
  agent verification does not establish every live-account workflow.

A reported scheduling issue was not an algorithm bug: November 16 9:06PM planning start plus
6–8PM daily availability leaves no time before November 17 3PM deadlines. The reproduced
810 requested / 180 scheduled / 630 unscheduled result was correct; the owner confirmed this.
Do not weaken deadline constraints to schedule late work or change sample dates silently.

## Estimator contract and relevant files

- models.py: Assignment fields are assignment_id, course, title, assignment_type, due_at,
  points_possible, description. Description can contain Canvas HTML. DurationEstimate contains
  assignment_id, estimated_minutes (positive integer; bool rejected), method, explanation.
- estimator.py: estimate_duration(assignment) -> DurationEstimate, method rule_based_v1.
  Type defaults: quiz 30, discussion 45, reading 60, homework 90, essay/programming 180.
  Unknown types fall back to 90 active minutes. Only normalized type affects the baseline;
  title/description/points/course/deadline do not currently influence estimates.
- Canvas conversion reliably recognizes only explicit quiz/discussion metadata. Many imported
  assignments are unknown. Do not invent reliable essay/programming categories from Canvas.
- streamlit_app.py: original estimates and Plan with minutes are separate. Duration overrides
  survive reruns/import changes; Canvas adjustments persist by stable assignment ID. LLM results
  must not silently overwrite these user edits or run repeatedly on every Streamlit rerun.
- deadline_planning.py/deadline_ui.py: explicit manual targets or skipped undated work.
- scheduler.py, scheduling_models.py, availability.py, calendar_planning.py: scheduling and
  constraints. They should receive reviewed active-minute inputs, not call an LLM themselves.
- canvas_client.py, canvas_import.py, canvas_ui.py: acquisition, conversion, and interface
  remain separate.
- google_auth.py, google_calendar.py, google_ui.py, calendar_export.py, and
  calendar_export_ui.py: authorization, transport, export,
  receipts, and recovery. These should not be coupled to the LLM estimator.
- tests/test_estimator.py, test_models.py, test_streamlit_app.py, test_canvas_ui.py and
  conftest.py: review current contracts and isolated preference fixtures before new tests.

## First increment to propose, then test

1. Clarify local versus hosted inference, hardware/runtime availability, provider/model, and
   budget/privacy constraints. Qwen/Ollama was discussed only; neither choice nor installation
   is established. Research current official provider documentation when making a choice.
2. Keep rule_based_v1 intact as the comparison baseline and safe fallback. Design a separate
   model-transport/provider boundary so parsing/fallback can be tested with mock responses.
3. Define a bounded structured output containing positive whole active minutes plus a useful
   explanation and method/model provenance. Reject booleans, invalid/out-of-range numbers,
   missing fields, malformed JSON, and unsupported responses. Bound input and request time.
4. Test successful estimates and safe fallbacks for timeout, unavailable model, authentication/
   rate-limit failure, and malformed output before enabling real inference. Avoid dependencies
   that are not necessary. This first increment does not require private Canvas data.
5. Treat assignment HTML/text as untrusted data, not instructions or executable content. The
   estimator should have no Calendar/Canvas write tools. Minimize personal fields in prompts;
   never include credentials or log private prompts/raw responses by default.
6. Explain the resulting interface and test results; stop for review after the small increment.
   Explicit UI inference actions, result caching/reuse, model setup, and live trials can follow
   once the first component is reviewed and the provider/authorization decisions are settled.

Estimates measure understanding instructions, doing work, and reviewing it. They exclude
breaks and waiting time; a deadline is not evidence of task complexity. LLM output is provisional.
No actual-completion dataset, personalized training, or proven accuracy improvement exists.
Plan comparison against real active completion minutes, including error, latency, failure rate,
and cost. Do not label student adjustments as measured completion records or LLM guesses as truth.

## Private state and scope limits

Ignored `.local/` contains the Desktop OAuth client JSON, planner_preferences.json,
duration_adjustments.json, and calendar_exports.json. Do not read/print credentials, include
these files in Git, clear the export ledger, or edit the owner's saved data to make tests pass.
Native Keychain stores account tokens. Tests must use mocked APIs/storage and temporary paths.
No private live imports/Calendar writes are authorized for the next agent by this handoff.
Establish authorization before model downloads or sending private assignment content externally.
Never ask for secrets in chat. Stop automatic restoration in tests by keeping fixture isolation.

No full database, hosted/multiuser OAuth, Google Tasks, Canvas feed fallback, autonomous event
reconciliation, or AI model training is implemented or part of this next small increment.
Google uses a Desktop client for the local demonstration; public hosting needs a separate web
OAuth/per-user storage design. Google Testing consent can expire and school policy can restrict
access; these are not estimation bugs.

## Suggested next-chat prompt

Continue the project in `/Users/ericrodriguez/Capstone/academic-workload-planner`. Read
AGENTS.md, README.md, docs/llm-estimation-handoff.md, current/next/design sections of
project-plan.md, and recent journal entries. Verify Git and run the project's 533-test suite
using `.venv/bin/python -m pytest -v`. Preserve changes; do not commit/push unless requested.

I want to start LLM-assisted time estimation. I know OOP and am learning Python. Explain the
proposed files/interface first, write meaningful mocked tests before behavior, work in small
increments, and stop after the first focused tested component. Keep rule_based_v1 and its
90-minute unknown fallback, student overrides, scheduler/deadline constraints, and the working
Canvas/Google workflow. No provider/model is chosen; Qwen/Ollama was discussed only. Clarify
local/hosted/hardware/budget/privacy choices while progressing on independent design. No model
downloads, private data transmission, live Canvas/Google requests, or new dependencies without
establishing the necessary scope/authorization. Validate structured active-minute estimates and
explanations, handle failures with the baseline, and do not claim better accuracy without data.

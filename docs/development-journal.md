# Development Journal

## November 9, 2026 — Undated assignments, weekly priority, and Roll Call filtering

- Read continuity docs/source/Git/requirements/ignore rules. Baseline: 498 passed plus one
  stale label assertion, caused by the user's intentional Select Classes to Import edit.
  Preserved that label and updated the test; preserved all other uncommitted changes.
- Explained increments before implementation and wrote failing tests first. Added exact
  normalized Roll Call Attendance/Attendence exclusion before conversion; no rows/selection
  or estimated workload for that administrative record. No broad attendance-title filtering.
- Initial proposal used a Sunday target. User clarified that undated work should be last
  relative to dated work for the reference week and approved explicit module week-start
  mapping. Revised tests/implementation accordingly; no Sunday deadline is inferred.
- Separate deadline_planning resolves student targets without mutating Assignment/Canvas
  due dates. Manual targets take normal priority. Week targets use the entered horizon as
  a planning cutoff, reserve dated work first, and wait until the last related dated-work
  day/session. They can spill into later weeks. Unplaced related dated work keeps them waiting.
- Related work uses confirmed module-week mapping where unambiguous, otherwise due-date week.
  Unreviewed undated work remains reported, and does not block reviewed weekly work.
  Original estimator/scheduler unchanged; planning composes the tested calendar adapter.
- Separate canvas_modules reads all module/item pages and preserves multiple memberships.
  Direct assignment and explicit quiz/discussion IDs only; no guessing from names, unlock
  dates, or matching quiz IDs to assignment IDs. Access/malformed metadata gaps warn.
- Streamlit prompts per selected undated assignment, supports date/time or reference week,
  and lets students load/map modules to Mondays. Missing selected module mappings block
  generation. Configured module choices refresh membership on subsequent imports/reloads.
- Canvas choices/module weeks persist in owner-only ignored local preferences. Source data,
  labels, sample dates, Google preview/approval, and credential storage are preserved. New
  Canvas deadlines take precedence; incompatible already-booked sessions require review.
- Full suite: 531 passed with .venv/bin/python -m pytest -v; git diff --check clean.
  New tests cover exact Roll Call filtering, all-page module reads, invalid IDs, access gaps,
  quiz link identity, multiple modules, manual target persistence, module mapping/reload,
  missing mapping, Wednesday ordering/spillover, waiting work, and busy/booked minute totals.
- Agent verification used synthetic data and mocked APIs/Keychain only. No live private API
  retrieval, Canvas write, calendar write, commit, or push. No dependency/database added.
- Python notes: frozen DeadlineChoice carries immutable user choices; resolve_tasks creates
  scheduling inputs rather than assigning a new value to Assignment.due_at. Composition
  reuses existing schedulers in stages, subtracting earlier sessions and their daily minutes
  before scheduling lower-priority work. Stable IDs reconnect preferences after imports.
- Next: user rehearsal of manual targets, known module-week mapping, and a dated/undated
  mix around calendar events; reconciliation remains a later scoped step.

## November 9, 2026 — Resume local connections and current classes after reload

- Read continuity docs/source/status and ran baseline: 484 passed. Preserved existing
  uncommitted work. User authorized automatic restoration instead of repeating manual imports.
- Explained separate preference storage and noninteractive restoration before implementation.
  Added tests first and observed missing-module failures, then implemented local_preferences
  and resume_ui. Preferences use an allowlist, validation, atomic replacement, and mode 0600.
- Remember assignment-source mode, Canvas site/current-class IDs, and resume flags only.
  No tokens, course names, assignments, generated schedules, or approval snapshots in the file.
- Rename course selector Classes you’re taking this semester. Save choices on user changes;
  restore only accessible IDs; report unavailable saved classes without erasing them. Reload
  refetches current assignments once per browser session, with no repeated reads on widget reruns.
- Successful saved-token Canvas connection enables resume. Google successful connection enables
  resume through Keychain reuse/refresh with allow_interactive=False. Missing credentials never
  open browser login during reload. Disconnect disables resume; Forget also removes credentials.
- Existing installations connect once to enable the new flags. Tokens and consent still expire.
  No automatic generation, calendar creation, or event export. No new dependency or database.
- Updated the previous refresh test: refresh now connects automatically; token fields remain
  absent when connected and are never prefilled. New test isolation prevents real preference
  reads/writes across the entire suite. All API/Keychain behavior was mocked; no live reads.
- Full suite: 499 passed with .venv/bin/python -m pytest -v. Tests include owner-only storage,
  unknown/secret-field rejection, malformed-file preservation, fresh-page mode/classes/import,
  unavailable classes, missing tokens, disconnect across reloads, silent Google restoration,
  expired-authorization handling, and no automatic browser flow. Original demo/export tests pass.
- Python note: session_state lasts for one Streamlit browser session; a JSON file survives a
  reload/server restart. A widget on_change callback saves user choices before rerendering.
  The import alias saved_preferences avoids colliding with the scheduling preferences variable.
- No commit or push. Next: user reload rehearsal on their Mac; automatic reconciliation
  remains a separate milestone.

## November 8, 2026 — Reviewed export and planning around Calendar events

- User reported connection setup working and requested scheduling around existing normal
  Calendar events (Google Tasks excluded). Baseline: 444 passing cases. Preserved prior
  uncommitted work; no commit or push requested.
- Explained the pure planning adapter, export service, and explicit UI actions before each
  increment. Added mocked tests first, observed failures, then implemented behavior.
- Calendar availability reads primary/planner plus selected extras. Fetch every calendar-list
  and planner-event page; incomplete/denied free/busy results block generation/export.
  Calendar names/IDs and busy intervals use new calendar.calendarlist.readonly and
  calendar.events.freebusy scopes. Old stored scopes require explicit reauthorization;
  never override an old token's scope list with the newly requested permissions.
- Busy subtraction uses UTC elapsed intervals, rounds inward to whole-minute study slots,
  and preserves local daily caps. Verified future planner bookings count toward assignment
  and daily minutes. The original estimator and scheduler were left unchanged.
- A test caught pre-start availability consuming daily capacity in the adapter; clipped
  before budgeting. Clock-change and subminute tests verify conservative time handling.
- Session selection -> preview -> approval -> export. Changing selections/account/calendars
  invalidates review. Recheck ownership and busy times immediately before insertion.
- Deterministic UUID-derived event IDs plus private ownership metadata identify retries.
  Owner-only atomic .local/calendar_exports.json records intent before each write and
  completion/uncertainty afterward. No tokens, course names, or assignment titles stored.
- Stop after uncertain/failed writes; report every approved session as exported/already
  present/conflict/failed/uncertain/not attempted. Explicit unfinished-export recovery
  reuses the original ID; verified existing events resolve uncertain local receipts.
- Only inserts into the marker-checked dedicated calendar. No event/calendar deletion,
  updates, attendees, notifications, automatic reconciliation, database, or new dependency.
- Full suite: 484 passed with .venv/bin/python -m pytest -v; git diff --check clean.
  Tests cover interval clipping, minute accounting, daily budgets, scopes, pagination,
  busy-read failures, approval invalidation, partial failures, HTTP 409, retry/restart,
  malformed metadata, and actual Streamlit planning/export/regeneration using mocks.
- Agent made no live calendar reads or writes. Local server restarted for user review.
  User must approve new consent and exercise live behavior privately in the app.
- Limits: only selected calendars checked; existing bookings remain fixed (including
  outside a new horizon); manually changed/deleted/over-budget bookings require review.
  Past bookings do not prove work completed. Retained-booking conflicts need manual review.
  Google has no atomic free/busy-and-insert transaction, so external-change races remain.
- Python notes: frozen dataclasses make preview snapshots immutable; tuple context detects
  changed review inputs. A generator yields per-local-day pieces without building a list.
  A write-ahead record means save intent before calling Google; stable IDs let retries ask
  whether that same event already exists instead of blindly making another event.
- Next: user rehearsal with the new consent, current dates, a known Busy event, a small
  approved export, regeneration, and retry/restart. Reconciliation is a later scoped step.

## November 8, 2026 — Local Google connection and calendar setup

- Read continuity docs/source/status; baseline 401 cases passed. Preserved existing
  uncommitted Canvas, display, Keychain, and scheduling-interface changes.
- User placed a Desktop OAuth client JSON in ignored `.local/`. Validated its shape and
  official endpoint configuration without printing fields; set that file to mode 0600.
- Explained and separated Google authentication, calendar REST, and UI modules before
  implementation. Wrote mocked tests first and observed missing-module failures.
- Added google-auth 2.62.1 and google-auth-oauthlib 1.5.0 in `.venv`. Direct Calendar REST
  calls use the SDK's AuthorizedSession; no additional Calendar SDK was needed.
- Local consent uses the default browser, loopback-only random port, state/PKCE, a two-minute
  callback timeout, and bounded network requests. SDK callback/token logging is disabled.
- Keychain stores the authorization envelope: renewable credentials, verified Google subject,
  selected calendar ID, and creation ownership/pending markers. No token file or browser-field
  prefill. Same-account reauthorization preserves metadata; different accounts do not inherit it.
- Explicit Create planner calendar uses calendar.app.created; OpenID supplies only the identity
  comparison needed for safe reconnection. No calendar listing or event reads/writes implemented.
- Save a pending marker before creation. Uncertain remote failure blocks automatic retries;
  marker-checked recovery uses an ID from Google Calendar settings. Final storage failure keeps
  the returned ID in memory so another click doesn't issue another insert.
- Tests cover auth reuse/refresh, revocation, identity verification, scoped permission denial,
  invalid configuration/state, safe errors, creation/access/recovery, and explicit UI actions.
  Offline real-SDK checks cover credential serialization and generated state/PKCE parameters.
- Full suite: 444 passed using `.venv/bin/python -m pytest -v`; pip check found no broken
  requirements. These establish tested contracts, not live Google-account approval.
- No real Google login, token read, calendar creation, event export, commit, or push performed
  by the agent. User must exercise first live consent and calendar access in the local app.
- Python notes: repr=False prevents dataclass fields from appearing in ordinary object output;
  partial supplies bounded timeout defaults. The existing Keychain layer is extended for a
  separate Google service entry rather than mixing Google credentials with Canvas tokens.
- Next: local live verification, then the separate reviewed/deduplicated event-export milestone.

## November 7, 2026 — Step 3 Canvas scheduling completed in code and tests

- Baseline: 383 passed. Preserved the existing uncommitted formatting/Keychain/interface
  work and verified that Canvas selections already flowed into estimator and scheduler.
- Explained two remaining gaps before implementation: historical dates in Canvas mode
  and widget-owned duration edits lost after deselection or new browser sessions.
- Wrote tests first and observed missing-module/input-recovery failures. Added a current
  planning-date helper, per-source editable date profiles, independent in-memory overrides,
  and a small local duration-preference store. Added `.local/` to ignore rules first.
- Canvas suggests next-minute local start plus a 14-day inclusive horizon. Its dates don't
  overwrite the historical sample demo. Explicit Use current dates preserves minute edits;
  invalid timezone input remains recoverable. Scheduler still uses only explicit inputs.
- Save only Canvas IDs and minute values; use a 0600 atomic replacement file. Preserve
  unrelated edits when merging. Missing files mean no overrides; malformed files are reported
  and not overwritten. Tests use temporary files, not the student's preferences.
- End-to-end AppTest imports synthetic Canvas records, estimates unknown types, applies a
  150-minute adjustment, and generates 60 scheduled + 270 unscheduled = 330 requested minutes.
  Every task is accounted independently; all three warning reasons and the existing constraint
  audit are exercised. Re-import, deselection, fresh session, and save failure are covered.
- Full suite: 401 passed using `.venv/bin/python -m pytest -v`. The historical sample still
  produces 390 scheduled + 60 undated minutes. No estimator/scheduler changes or dependency added.
- No private live API request, token access, commit, or push performed. Code/test completion
  is distinct from inspecting a real-account generated plan in the browser.
- Python notes: a widget callback runs before the next render and copies edited minutes into
  independent state. A stable ID reconnects saved minutes to a re-imported assignment. Atomic
  replacement writes a complete temporary file before swapping it into place, avoiding a
  half-written preferences file if writing fails.
- Next: review real-account output locally, then start the separate reviewed Calendar milestone.

## November 5, 2026 — Readable deadlines and optional remembered Canvas token

- Preserved the uncommitted date/time formatting changes. Baseline: 356 passing cases.
  The user's screenshot showed a real import rendered with the older ISO date format;
  current-source tests confirm both Canvas tables use the shared formatter.
- Added an exact screenshot-boundary test using synthetic data: November 7 at 07:59 UTC
  displays as November 6, 2026 11:59PM PST. Midnight, noon, daylight-saving labels,
  missing deadlines, and original timestamp preservation remain covered.
- Explained the one new dependency before implementation: `keyring==25.7.0`, installed
  only in `.venv`, provides native macOS Keychain storage. `credentials.py` isolates
  storage from HTTP/conversion/UI and explicitly selects the native macOS backend.
- Wrote mocked storage and fresh-session UI tests before implementation. Opt-in Save
  occurs after successful course retrieval; blank-token Load courses reads only that
  site's token. Forget deletes that entry and clears the active connection/import.
- Tokens never prefill widgets, appear in logs, or enter project files. Storage failures
  are sanitized and don't discard an otherwise successful in-memory connection. Tests
  cover opt-in behavior, expiry feedback, manual-token bypass, failure handling, and
  separate site keys without reading or writing actual Keychain credentials.
- Full suite: 376 passed using `.venv/bin/python -m pytest -v`; pip check found no broken
  requirements. No estimator/scheduler change, database, automatic refresh fetch,
  credential migration from chat, commit, or push.
- Python notes: a small wrapper translates backend exceptions into safe messages;
  `raise ... from None` suppresses potentially sensitive backend traceback details.
  A dictionary-backed fake simulates persistent storage across fresh Streamlit sessions.
- Next local review: opt in once with a replacement token in the app, allow macOS Keychain
  access if prompted, then refresh and connect with the field blank. Expiration still
  requires a replacement token; remembering does not renew it.

## November 4, 2026 — Canvas conversion and local import controls

### Verified outcome

- Preserved existing uncommitted interface/documentation work and the prior Canvas-client
  increment. Baseline: 303 cases passed at commit `9a6ab8c` plus uncommitted changes.
- Explained the conversion wrapper, conservative mapping, and explicit import actions first.
  Wrote conversion tests before the new module and UI tests before the controls;
  observed expected missing-module/control failures.
- Added `canvas_import.py` and `canvas_ui.py`. Updated assignment requests to include
  the current user's submission and explicitly apply deadline overrides.
- Full suite: 347 passed using `.venv/bin/python -m pytest -v` (32 new conversion cases,
  12 new UI cases). Sample mode still yields 390 scheduled + 60 unscheduled minutes.
- Started Streamlit on loopback at port 8501 with telemetry disabled; health returned `ok`.
  Socket binding required sandbox escalation. No live Canvas request or real-data inspection
  was performed, so account compatibility and visual layout remain unverified.
- No dependency, estimator/scheduler rule change, secret file, commit, or push.

### Adopted decisions

- Keep `Assignment` unchanged; a frozen wrapper carries status/default selection. IDs contain
  host, course ID, and assignment ID so renaming titles/courses does not change identity.
- Preserve effective `due_at`, not other students' `all_dates`; require timezone-aware dates.
- Only explicit quiz/discussion submission types map to known estimator types. Others stay
  unknown, retaining the provisional 90-minute fallback and editable planning minutes.
- Show submitted/graded/pending-review/excused/unknown work unchecked, allow manual selection,
  and select unsubmitted/redo-request work by default. Grades are not proof of completion.
- Fetch only on Load courses / Import assignments. Report coverage gaps and retain valid work;
  clear old snapshots before refresh and hide them after course/site changes.
- Use a local password form and in-memory client. The user shared a token in chat; instructed
  them to revoke it and enter a replacement locally. The exposed value was not used or saved.
- Keep availability/preferences rendered during import: Streamlit can discard state for
  widgets absent from a run. Keep fixed October sample defaults and explicitly prompt for real dates.

### Python learning notes and next review

- `@dataclass(frozen=True)` supplies a constructor for the metadata wrapper and prevents
  ordinary reassignment of its fields; the wrapped existing Assignment remains mutable.
- The service returns tuples of successful records and warnings, letting the UI report
  partial course access without interpreting it as a complete import.
- Mocks replace Canvas responses, while AppTest exercises actual selection and button flow.
  Passing tests establish those contracts, not successful access to the student's account.
- Next: the student connects privately at `https://cilearn.csuci.edu`, reviews real assignments,
  and sets real planning dates. Google OAuth/export remains a separate future milestone.

## October 21, 2026 — First local Streamlit interface completed

### Verified outcome

- Began at clean scheduler commit `9a6ab8c`; 219 baseline tests passed. Honored the user's request to defer the standalone pipeline-demonstration step and prioritize the interface for a meeting.
- Explained the separation before implementation: weekly expansion module, Streamlit entry point, and interface tests; existing estimator/scheduler rules unchanged.
- Wrote weekly-availability tests first and observed the expected missing-module failure. Implemented frozen weekly rules, timezone localization, and dated expansion; 20 cases passed.
- Wrote two initial page tests first, observed missing-file failures, then built the assignment display/adjustment increment and passed both.
- Added nine failing page cases for generation, settings, warnings, stale results, and errors, then implemented weekly controls, preferences, and scheduler calls. Added recovery, ambiguous planning time, and past-deadline checks. All 14 AppTest cases pass.
- Full suite: 253 passing cases. Installed Streamlit 1.66.0 and required dependencies in the project `.venv`; pinned the direct dependency in requirements.txt. `pip check` reports no broken requirements.
- Started the local app at http://127.0.0.1:8501. Outside sandbox restrictions, HTTP returned 200 and health returned `ok`. Browser automation could not initialize in this session; no visual-layout verification is claimed.
- Updated README, plan/checkpoint, and personal notes. No commit or push performed.

### Adopted decisions

- Keep one page with assignment/estimate table, separate student minute inputs, sidebar preferences, weekly windows, generation button, session table, totals, and readable remainder warnings.
- Default to a clearly labeled fixed October 10–17 demo horizon. Sample deadlines are unchanged. Defaults yield 390 scheduled and 60 unscheduled reading minutes because that assignment has no deadline.
- Add `WeeklyAvailability(weekday, start_time, end_time)` and `expand_weekly_availability()` in availability.py. Dated `AvailabilityPeriod` inputs and the existing scheduler remain unchanged.
- Expand inclusive horizons of 1–366 days, include overnight carry-in, clip both ends, and reject overlaps. The page offers one optional window per day. Earlier end means next day; equal times are rejected.
- Use `localize_datetime()` with UTC round trips and fold offsets to reject ambiguous/nonexistent times. Do not silently choose a daylight-saving interpretation.
- Use stable widget keys and session state; preserve original estimates separately from student overrides. Hide old output when inputs change and clear results when generation fails. Reset demo is an explicit callback that restores defaults.
- Session memory covers normal interactions only; durable storage and persistence across refresh/reconnect/server restarts are not promised. No UI controls for database/API/calendar/AI features were added.

### Python and Streamlit learning notes

- Streamlit reruns the script after normal widget interactions. `st.session_state` holds named values across reruns; `setdefault` initializes a value only when its key is missing.
- Widget `key` values connect controls to session state. Button callbacks run before the next script rendering, allowing Reset demo to update existing widget values safely.
- The page calls `load_assignments()`, `estimate_duration()`, and `build_schedule()` directly. UI code prepares inputs and displays results; core estimation/scheduling rules stay independently testable.
- A frozen weekly dataclass describes recurrence; expanding it over real dates produces the concrete objects the scheduler already accepts.
- AppTest executes the actual page and lets pytest change widgets and click buttons without starting a browser. HTTP checks establish server availability, not visual correctness.

### Next review

Open the local URL and rehearse the documented meeting sequence. Review interface layout and feedback before expanding scope. Standalone demo packaging, persistence, Canvas, Google Calendar, richer availability controls, and prediction models remain future work.

## October 20, 2026 — Step 6 failure reporting and constraint audit completed

### Verified outcome

- Read current guidance/source/tests and preserved existing uncommitted work, including personal notes. Baseline: 194 cases passed.
- Explained the small change before implementation: keep placement behavior and reason codes; add a derived message plus independent output checks in tests.
- Wrote three failure-message cases first; observed the expected missing-property failures, then added `UnscheduledWork.message` and passed them.
- Added 22 scheduler cases: a 12-case workload/limit matrix, per-assignment overload reporting, continued scheduling after an earlier task cannot fit, exact boundaries, duplicate/nested/offset overlaps, midnight reset, multi-day availability, and both daylight-saving transitions.
- Extracted `assert_schedule_constraints()` in test_scheduler.py and reused it in the existing mixed-workload test. It checks actual UTC intervals against original inputs, local daily totals, exact accounting, and correct reason codes without calling placement helpers.
- Full suite: 219 passing cases (original 79 + 97 scheduling-model + 43 scheduler). Used `.venv/bin/python -m pytest -v`; no dependencies added. No placement changes, estimator changes, commit, or push.

### Adopted decisions

- Retain structured `assignment_id`, `remaining_minutes`, and `reason`; expose readable text through a calculated `message` property so no duplicate message state can drift from the fields.
- All messages begin "Could not schedule" and explain missing deadline, deadline at/before planning start, or work left unplaced by the greedy scheduler. No message claims that no feasible arrangement exists.
- Normal shortfalls return partial success plus remainder records. Overlapping availability is invalid input and raises ValueError, including nested/duplicate windows, different offsets, and overlaps before planning start. Touching periods remain valid.
- Allow availability across midnight/multiple days and split at student-local midnight. In tests, inspect the final instant before session end so a session ending exactly at midnight counts toward the day it starts.
- Keep the reusable constraint checker in tests; no standalone production validator or new scheduling algorithm is required by this step.

### Python learning notes

- `@property` exposes `work.message` like a field while calculating it from the validated ID, minutes, and reason. It is not a constructor argument or a separately stored field.
- The explanation dictionary maps stable reason codes to readable text. Callers can use `print(work.message)` while retaining codes for later interface logic.
- A test helper collects common assertions. It checks outputs rather than recreating the placement algorithm; parameterization runs those checks across different workload/session/daily limits.
- Successful tests verify the exercised constraints, not optimization, universal input coverage, or prediction accuracy.

### Next review

Review step 6, then demonstrate the complete sample-data loading/estimation/scheduling pipeline with fitting and overloaded workloads before starting the interface. UI, recurrence, adjustments, storage, external integrations, and AI remain deferred.

## October 20, 2026 — Step 5 simplest scheduler completed

### Verified outcome

- Preserved the existing uncommitted step 4 files/documentation. Baseline: 173 passing cases.
- Explained the public function and greedy placement approach before implementation.
- Started with one task/one period: test failed on missing module, then passed with the first small implementation.
- Added session-splitting, later-period continuation, and remaining-work tests: three expected failures, then four cases passed after the second increment.
- Added deadline ordering, shared daily limits, planning/deadline clipping, ineligible deadlines, and midnight tests: nine expected failures before extending the implementation. Added focused input, timezone, and mixed-workload checks for the final increment.
- `build_schedule()` and 21 scheduler cases now pass; full suite: 194 passing cases using `.venv/bin/python -m pytest -v`.
- Verified a fixed-date 140-minute example: October 10 18:00–19:00 and 19:00–20:00, then October 11 18:00–18:20 with a 60-minute session cap and 120-minute daily cap. No leftover minutes.
- Estimator, loader, and existing model behavior unchanged; scheduling-model docstrings now refer to the implemented scheduler. No dependencies added, commit, or push.

### Adopted implementation decisions

- Keep scheduling in `scheduler.py`; `build_schedule(tasks, availability, preferences)` accepts sequences of validated models and returns the existing `ScheduleResult`.
- Sort availability in UTC, reject overlaps (allow touching endpoints), clip at planning start, and split windows at student-local midnight.
- Schedule eligible tasks by UTC deadline then assignment ID. Preserve requested task order in the result and return chronological sessions in the student timezone.
- Choose each session length as the minimum of remaining work, session cap, usable window before deadline, and remaining daily allowance. Advance each consumed slot's start and share daily totals across all tasks.
- Report missing/past deadlines explicitly; report other leftovers as `unplaced_by_greedy`. Round fractional-minute capacity down. Result construction validates per-task accounting.
- Maintain local copies of slots and counters so inputs remain unchanged and repeated calls are independent. No current-time lookup occurs.

### Python learning notes

- `Sequence[...]` describes ordered inputs such as lists and tuples without requiring one concrete collection type.
- `sorted(..., key=lambda ...)` builds a sorted copy; a short `lambda` supplies the comparison key. A `(deadline, assignment_id)` key provides deterministic tie handling.
- `enumerate(slots)` supplies both an index and a value; the index lets us replace a free slot with its unused remainder.
- `minutes_by_day.get(day, 0)` returns an existing daily total or zero when no session has used that day yet.
- `min(...)` enforces several upper bounds at once; subtracting placed minutes moves the loop toward completion.
- New tests verify exact session times plus a mixed workload's independent containment, non-overlap, deadline, limit, accounting, repeatability, and input-preservation checks. Spring/fall clock changes are covered.

### Limitations and next review

- This greedy scheduler does not backtrack, optimize spacing, insert breaks, or impose a minimum session length. Leftovers do not prove infeasibility.
- Daily limits cover only sessions generated by this call; existing study work and busy events are not imported. Recurrence, UI, storage, APIs, and AI remain deferred.
- No standalone schedule validator was added. Step 6 remains a broader failure/boundary audit; the core policies already have baseline tests because a working scheduler must produce valid output.
- Review step 5 before extending the project. README includes the repeatable example and current API.

## October 19, 2026 — Step 4 scheduling representations completed

### Verified outcome

- Began at clean commit `d63da55`; baseline command `.venv/bin/python -m pytest -v` passed 79 cases.
- Explained the proposed fields, validation, and scheduling policies before implementation.
- Added tests first; confirmed the expected missing-module collection error before implementing.
- Added `scheduling_models.py`: `AvailabilityPeriod`, `SchedulingPreferences`, `SchedulingTask`, `StudySession`, `UnscheduledWork`, and `ScheduleResult`.
- Full suite passes 173 cases: original 79 unchanged plus 94 scheduling-model cases. Tests use fixed October 2026 dates and a November 2026 daylight-saving fold example.
- No dependencies added; estimator, loader, and existing models unchanged. No scheduler, interface, recurrence, integrations, commit, or push performed.

### Adopted decisions

- Use frozen dataclasses and tuple result collections to prevent ordinary post-validation edits in the new models. Existing mutable models retain their behavior.
- Keep requested minutes separate from `DurationEstimate`; future callers may supply durations from any source.
- Require explicit planning start, `ZoneInfo` student timezone, and positive integer minute limits. Calculate elapsed durations in UTC, including across repeated local hours.
- Derive session duration from timestamps rather than storing a second potentially inconsistent value.
- Validate exact minute accounting per assignment, unique requested IDs, known output IDs, and one remainder record per task. A result is an accounting container, not proof of schedule feasibility.
- Missing deadlines and deadlines <= planning start remain fully unscheduled; use stable reason codes. Eligible leftover work uses `unplaced_by_greedy`, without claiming infeasibility.
- Adopt earliest-deadline/ID ordering, reject overlapping availability but allow touching endpoints, allow availability across midnight and split sessions at student-local midnight, and allow sessions ending exactly at deadlines. Enforcement awaits scheduler tests/implementation.

### Python learning notes

- `@dataclass(frozen=True)` generates a constructor and prevents ordinary field reassignment; `__post_init__` still validates initial values.
- `@property` exposes calculated data as `session.duration_minutes` without parentheses.
- `tuple[StudySession, ...]` means a tuple containing any number of study sessions; unlike a list, it cannot be appended to. `(session,)` is a one-element tuple.
- `Literal[...]` documents allowed reason strings for type-checking tools. Explicit runtime checks are still needed because Python does not enforce type hints itself.
- Helpers beginning with `_` are internal by convention. They share validation rules within the new module without changing the existing models.
- Parameterized tests run the same expected behavior against several inputs. Passing 173 cases verifies these contracts, not scheduling correctness or estimator accuracy.

### Review boundary

Review step 4 before building the scheduler. Next work is steps 5–6: enforce the adopted policies and constraints incrementally with tests, then demonstrate fitting and overloaded workloads. Daily limits, overlap prevention, deadline checks, and reason correctness are not yet enforced by an algorithm.

## October 19, 2026 — Initial rule-based estimation completed

- Added `DurationEstimate` to models.py with assignment ID, positive integer minutes, method, and explanation. Booleans/floats are rejected as minutes; text must be nonblank. Validation occurs at construction.
- Created estimator.py with `estimate_duration(assignment)` and `rule_based_v1`: quiz 30, discussion 45, reading 60, homework 90, essay 180, programming 180, fallback 90 minutes.
- Rules are provisional active-work defaults, not measured predictions. Matching normalizes a local type string without changing assignments. Explanations identify fallback/default and lack of personalization.
- Wrote tests first and confirmed missing-import failures, then implemented the model and estimator. Full suite: 79 passed (36 model, 29 loader, 14 estimator). Sample-file integration yields quiz 30, essay 180, reading 60, programming 180 minutes, including estimation without a deadline.
- New test concepts: `dataclasses.replace` creates modified copies; `asdict` snapshots fields for mutation checks; stacked parameterization checks combinations of fields and invalid values.
- No dependencies added. No workload extraction, UI adjustments, AI, or scheduling implemented. Student adjustments remain an interface task and should preserve original estimates.
- Next: explain and define availability periods, preferences, study sessions, and results with unscheduled work. Historical entries below describe earlier checkpoints, not the current implementation.

## October 19, 2026 — Retrospective and loading-milestone checkpoint

This entry summarizes work completed across earlier sessions and the current documentation checkpoint. It is a retrospective, not a claim that every implementation change occurred today. Summer implementation was limited while Eric focused on an internship; initial work emphasized scope and architecture.

### Completed work

- Established the `workload_planner`, `sample_data`, `tests`, and `docs` structure; created package markers, a pytest requirement, and ignore rules for virtual environments, caches, and local secrets.
- Created the local `.venv` environment. The verified interpreter is Python 3.13 and the installed pytest version is 9.1.1. Runtime code uses the standard library.
- Implemented the `Assignment` dataclass and construction-time validation in `models.py`.
- Wrote model tests before implementation, confirmed the initial missing-import failure, then passed 15 cases.
- Added four fictional assignment records: quiz, essay, ungraded reading without a deadline, and programming exercise. Dates are fixed October 2026 examples with explicit UTC offsets.
- Wrote loader tests before implementation. The initial import error was expected because `load_assignments` did not yet exist.
- Implemented `load_assignments` with JSON parsing, structural checks, required-field checks, ISO 8601 conversion, model construction, and contextual errors.
- Verified all 44 cases (15 model and 29 loader cases) and loaded all four actual sample records successfully.
- Updated AGENTS.md, README.md, and the project plan for a new-session handoff and the estimation milestone.

### Design decisions and reasons

- Keep input conversion in the loader and reusable assignment rules in the model. Future Canvas ingestion can create the same model without rewriting the scheduler.
- Use a dataclass and standard-library JSON/date/path utilities to keep the first milestone understandable and avoid unnecessary dependencies.
- Require an explicit `due_at` field but permit null/None. Missing points and description use model defaults. A missing deadline is information the scheduler must handle explicitly later.
- Require timezone-aware supplied deadlines. Parse both numeric UTC offsets and `Z` without inventing a timezone for naive input.
- Preserve input order; prioritization belongs to scheduling.
- Stop on malformed records instead of silently omitting work. Loader ValueErrors identify the record and field; JSON syntax errors identify the file and location. Missing-file errors remain FileNotFoundError.
- Use fresh fixture dictionaries and temporary files so malformed-input tests never damage sample data.
- Keep rule-based estimation as the baseline. Base durations and the estimate representation have not been implemented or finalized.

### Python and tooling concepts covered

Eric understands object-oriented programming and is learning Python. Explanations covered imports, type hints, dataclasses, generated constructors, `self`, default arguments, `None`, `__post_init__`, dictionaries, loops, truthiness, exceptions, and timezone-aware datetimes. Testing explanations covered assertions, fixtures, parameterization, temporary paths, dictionary unpacking, and expected exceptions.

An unresolved pytest import was traced to environment selection: a terminal installed pytest in Anaconda while this project used `.venv`. Code Runner also executed a test file directly, causing a package import error. The working approach is to select `.venv/bin/python` in VS Code and run pytest from the project root:

```bash
.venv/bin/python -m pytest -v
```

The VS Code Testing view is an alternative after configuring pytest. Explicit environment paths do not require activation. A virtual environment is a folder containing its interpreter entry points and installed packages, not a source file.

### Explored ideas, not adopted requirements

- Hosted OpenAI estimation and local Qwen through Ollama could provide estimates, but accuracy must be measured against actual active completion times. Neither is implemented or required for the MVP.
- Local models can avoid per-request provider charges but require computing resources; public hosting introduces deployment considerations. Repeated inference does not automatically train or personalize a model.
- Streamlit is the planned browser interface. No UI exists yet; a local browser demonstration and a publicly hosted app have different deployment requirements.
- A four-week schedule was discussed. Actual progress, the professor's requirements, and remaining time must govern scope; preserve testing/report time and defer optional integrations.

### Known limitations and follow-ups

- `Assignment` is mutable; validation does not automatically rerun on later field assignments.
- NaN/infinite point values and duplicate assignment IDs are not rejected yet.
- Sample dates are intentionally fixed and past; the loader does not enforce scheduling eligibility.
- Dependencies are not version-pinned. Passing tests do not imply exhaustive coverage.
- Estimation, scheduling, interface, storage, and external integrations remain unimplemented.

### Next session

Read AGENTS.md, README.md, project-plan.md sections 21–22, and this entry; inspect relevant code and Git state. Start by explaining and defining a separate duration-estimate representation with assignment ID, active working minutes, method, and explanation. Write meaningful tests, then implement small rule-based estimates with a fallback. Continue one agreed step at a time, explaining new Python syntax. Preserve this journal as history and update the plan's current-status section at future milestones.

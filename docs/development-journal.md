# Development Journal

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

# Development Journal

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

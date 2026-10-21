# Intelligent Academic Workload Planner

## Overview

The Intelligent Academic Workload Planner is a capstone software prototype designed to help students organize assignments and distribute their workload across available study time.

The completed system will retrieve assignment information from Canvas, estimate how long assignments may take, and generate study sessions that occur before their deadlines. Students will be able to review the proposed schedule and eventually export approved study sessions to Google Calendar.

The project focuses on reducing the manual planning required from students while avoiding overloaded study days and last-minute work.

## Problem

Canvas displays assignment deadlines, but it does not tell students:

- Approximately how long each assignment may take
- When they should begin working
- How to distribute a large assignment across multiple days
- Whether their available time is sufficient to complete upcoming work

Students may underestimate assignments, delay starting large projects, or overlook conflicts between courses. This application attempts to transform a collection of deadlines into a structured and realistic study plan.

## Project Goals

The main goals of this project are to:

1. Import assignment information from Canvas or sample data.
2. Estimate the completion time of each assignment.
3. Accept a student’s available study periods and scheduling preferences.
4. Divide long assignments into manageable study sessions.
5. Schedule sessions before assignment deadlines.
6. Warn the student when the available time is insufficient.
7. Allow the student to review the generated schedule.
8. Eventually export approved sessions to Google Calendar.
9. Collect actual completion times for future estimation improvements.

## Minimum Viable Product

The minimum viable product will:

- Load assignments from a sample JSON file
- Store assignment titles, courses, deadlines, types, and point values
- Estimate assignment durations using transparent rules
- Accept weekly study availability
- Divide assignments into study sessions
- Generate a non-overlapping schedule
- Keep sessions within available study periods
- Schedule work before the applicable deadline when possible
- Report assignments that cannot be completed within the available time
- Display assignments and study sessions in a simple Streamlit interface

The project will use sample data before connecting to external services. This allows the core estimation and scheduling logic to be developed and tested independently.

## Planned Technology Stack

- **Language:** Python
- **User interface:** Streamlit
- **Database:** SQLite
- **Database access:** SQLAlchemy
- **Data processing:** pandas
- **Testing:** pytest
- **Machine learning:** scikit-learn
- **Assignment integration:** Canvas LMS REST API
- **Calendar integration:** Google Calendar API
- **Version control:** Git and GitHub

## Planned System Workflow

1. Retrieve assignments from Canvas or load sample JSON data.
2. Normalize the assignments into a consistent internal format.
3. Estimate the required completion time.
4. Retrieve the student’s available study periods.
5. Generate study sessions based on workload and deadlines.
6. Display the proposed schedule for review.
7. Export approved sessions to Google Calendar.
8. Record actual completion times for future improvements.

## Initial Estimation Approach

`estimate_duration(assignment)` in `workload_planner/estimator.py` returns a `DurationEstimate` with assignment ID, positive integer minutes, method, and explanation. Method `rule_based_v1` uses provisional defaults: quiz 30, discussion 45, reading 60, homework 90, essay 180, programming 180, and unknown types 90 minutes.

Matching strips surrounding whitespace and ignores capitalization without modifying assignments. Explanations identify defaults/fallbacks and lack of personalization. Active minutes include understanding instructions, doing the work, and reviewing it, excluding breaks and waiting. These values are starting assumptions, not measured predictions. Only type affects v1 estimates. Later adjustments may consider characteristics such as:

- Assignment type
- Point value
- Description length
- Course
- Keywords in the title or description
- Previous completion times, when available

A machine-learning model may be developed after enough actual completion-time data has been collected. The trained model will be compared against the rule-based baseline to determine whether it provides a meaningful improvement.

## Scheduling Requirements

The scheduling algorithm should:

- Place sessions only within the student’s available times
- Prevent sessions from overlapping
- Keep work before the assignment deadline
- Respect the student’s preferred maximum session length
- Respect the student’s daily study limit
- Divide long assignments across multiple sessions
- Prioritize assignments with urgent deadlines or limited available time
- Report workloads that cannot be scheduled successfully

## Project Status

As of October 20, 2026, loading, initial rule-based estimation, scheduling representations, the simplest scheduler, and the step 6 failure/constraint audit are complete. The latest verification passed 219 tests (36 existing model cases, 29 loader cases, 14 estimator cases, 97 scheduling-model cases, and 43 scheduler cases).

Implemented:

- An `Assignment` dataclass with required-text, numeric-type, nonnegative-point, and timezone-aware deadline validation.
- Four fictional assignments: quiz, essay, reading, and programming; the reading has no deadline or point value.
- `load_assignments(path)`, accepting a string or `Path`, preserving input order, converting ISO 8601 deadlines, and reporting invalid records with field and record context.
- Automated tests using temporary files for valid and malformed input.

The loader accepts an empty list, requires an explicit `due_at` field (which may be `null`), and uses model defaults for omitted points and descriptions. It raises an error rather than returning partial results when any record is invalid. Unknown fields are rejected by the model constructor.

The earliest-deadline-first scheduler is implemented. Next: review step 6, then demonstrate the loaded/estimated/scheduled pipeline with fitting and overloaded workloads before starting the interface. The Streamlit interface, database, Canvas, and Google Calendar are not implemented. Student adjustments are deferred to the interface; workload extraction is not implemented. Local LLM estimation remains an optional future experiment.

## Current Project Structure

```text
academic-workload-planner/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .gitignore
├── workload_planner/
│   ├── __init__.py
│   ├── models.py
│   ├── scheduling_models.py
│   ├── scheduler.py
│   ├── estimator.py
│   └── loaders.py
├── sample_data/
│   └── assignments.json
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_scheduling_models.py
│   ├── test_scheduler.py
│   ├── test_estimator.py
│   └── test_loaders.py
└── docs/
    ├── project-plan.md
    └── development-journal.md
```

Add modules as their milestones begin. The proposed technology stack above is a roadmap, not a list of currently installed dependencies; application code currently uses only the Python standard library, with pytest for testing.

## Scheduling Representations (Step 4)

`workload_planner/scheduling_models.py` defines frozen dataclasses for dated availability,
explicit planning preferences, estimator-independent workload requests, study sessions,
unscheduled work, and scheduling results. Required minutes and limits are positive integers;
timestamps are timezone-aware, and intervals have positive whole-minute elapsed durations.
Use `ZoneInfo("America/Los_Angeles")` from the standard-library `zoneinfo` module for the
student timezone. Session durations are calculated in UTC to handle clock changes.

`ScheduleResult` takes tuples of tasks, sessions, and unscheduled work. It rejects duplicate
task IDs, unknown output IDs, duplicate remainder records, and incorrect per-task minute
accounting. These checks do not establish schedule feasibility: availability containment,
deadlines, non-overlap, session limits, daily limits, and reason selection are handled by
`build_schedule()` in `scheduler.py`. See project-plan.md section 13 for the policies.

## Simplest Scheduler (Step 5)

`build_schedule(tasks, availability, preferences)` accepts lists or tuples of validated
scheduling models. It preserves task input order in the result, sorts eligible work by
UTC deadline then assignment ID, and returns chronological sessions in the student's
timezone. It uses the supplied planning start rather than the computer's current time.

The scheduler fills the earliest free time, splits work at session limits and local midnight,
and shares daily limits across all tasks and availability periods. Overlapping periods and
duplicate task IDs raise `ValueError`; touching periods are allowed. Missing deadlines,
deadlines at/before planning start, and other unplaced work receive the existing explicit
reason codes. Sessions may end exactly at deadlines. Every requested minute is accounted for.

Run `.venv/bin/python` from the repository root and try:

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from workload_planner.scheduler import build_schedule
from workload_planner.scheduling_models import (
    AvailabilityPeriod, SchedulingPreferences, SchedulingTask,
)

zone = ZoneInfo("America/Los_Angeles")

def at(day: int, hour: int) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=zone)

result = build_schedule(
    tasks=[SchedulingTask("essay", 140, at(12, 20))],
    availability=[
        AvailabilityPeriod(at(10, 18), at(10, 21)),
        AvailabilityPeriod(at(11, 18), at(11, 20)),
    ],
    preferences=SchedulingPreferences(at(10, 17), zone, 60, 120),
)
for session in result.sessions:
    print(session.assignment_id, session.start_at, session.end_at, session.duration_minutes)
print(result.unscheduled_work)
```

Expected: October 10 from 18:00–19:00 and 19:00–20:00, then October 11 from
18:00–18:20, with no remaining work. The 120-minute daily cap moves the final 20
minutes to the next day, even though October 10 has another available hour.

This greedy baseline does not backtrack or optimize spacing. `unplaced_by_greedy` does
not prove no feasible schedule exists. Sessions may be back-to-back; breaks, minimum
session length, recurring availability, and existing-calendar work are not modeled.
Daily totals include only work generated by the current call. Fractional-minute capacity
is rounded down. Duration estimates remain provisional and unchanged.

## Scheduling Failures and Constraint Tests (Step 6)

A normal scheduling shortfall returns successful sessions and one `UnscheduledWork`
record for each assignment with remaining work. No requested minutes are silently dropped.
Each record includes `assignment_id`, `remaining_minutes`, `reason`, and a calculated
read-only `message`. To read the explanations:

```python
for work in result.unscheduled_work:
    print(work.message)
```

Example: `Could not schedule 30 active working minutes for assignment 'essay': the
 greedy scheduler left this work unplaced under the supplied availability, deadlines,
 and study limits.`

| Condition | Behavior |
|---|---|
| Missing deadline | All minutes remain; reason `missing_deadline` |
| Deadline at/before explicit planning start | All minutes remain; reason `deadline_not_after_start` |
| Other work left unplaced | Remaining minutes reported as `unplaced_by_greedy` |
| Overlapping availability, including duplicate/nested windows | Raise `ValueError`; reject input before producing a schedule |
| Touching availability windows | Accepted; sessions may meet at endpoints |
| Availability crossing midnight | Split at student-local midnight; apply each day's limit separately |

Messages describe what the algorithm could not schedule; they do not claim that no
feasible arrangement exists. Reason codes remain stable for callers.

The independent test helper `assert_schedule_constraints()` checks output intervals
against original availability, planning start, deadlines, session limits, local daily
limits, and exact per-assignment accounting. It is test code, not an application API.
The audit covers overloaded/mixed workloads, repeatability, input preservation, midnight,
multiple-day windows, and daylight-saving transitions. Passing these tests is evidence for
the tested contracts, not a guarantee that every possible timezone/input has been covered.

## Security and Privacy

The application may handle private academic and calendar information. Credentials and sensitive student data must not be committed to the repository.

The following files and values must remain private:

- Canvas access tokens
- Google OAuth credentials
- API keys
- Real `.env` files
- Personally identifiable student information
- Private assignment submissions or grades

A `.env.example` file may be included to document the required environment variables without containing real credentials.

## Running the Project

The current checkpoint was verified with Python 3.13 and pytest 9.1.1. Use Python 3.11 or newer for this code, including ISO 8601 deadlines ending in `Z`.

From the repository root on macOS/Linux, create an environment once if `.venv` does not already exist:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run all tests:

```bash
.venv/bin/python -m pytest -v
```

Try the actual sample data:

```bash
.venv/bin/python -c 'from workload_planner.loaders import load_assignments; assignments = load_assignments("sample_data/assignments.json"); print(f"Loaded {len(assignments)} assignments"); print(assignments[0])'
```

In VS Code, use **Python: Select Interpreter** to select `.venv/bin/python`. Configure **Python: Configure Tests → pytest → tests** to use the Testing view. Code Runner's direct execution of a test file does not run pytest and can produce import-path errors. Explicit `.venv/bin/python` commands do not require activation; optional terminal activation is `source .venv/bin/activate`.

There is no web application entry point yet. The sample deadlines are fixed October 2026 dates; the loader accepts past deadlines, and scheduling calls and tests supply an explicit planning start time.

## Current Limitations and Handoff

To try estimation, run `.venv/bin/python` from the repository root and enter:

```python
from workload_planner.loaders import load_assignments
from workload_planner.estimator import estimate_duration

assignments = load_assignments("sample_data/assignments.json")
for assignment in assignments:
    estimate = estimate_duration(assignment)
    print(assignment.title, estimate.estimated_minutes, estimate.explanation)
```

- Existing `Assignment` and `DurationEstimate` validation runs at construction; later field edits bypass it. New scheduling models are frozen.
- Assignment loading still accepts non-finite points (NaN/infinity) and duplicate IDs. `ScheduleResult` rejects duplicate requested task IDs.
- The baseline scheduler enforces the documented placement policies; step 6 adds independent constraint checks in tests and readable failure messages. Greedy leftovers do not prove infeasibility.
- Dependencies are not pinned; 219 passing cases establish this checkpoint, not exhaustive validation or prediction accuracy.
- See [the project plan](docs/project-plan.md) for the next milestone and [the development journal](docs/development-journal.md) for decisions and learning notes. New sessions should also read `AGENTS.md` and inspect the current code and Git state.

## Author

Eric Rodriguez

Capstone Project, Fall 2026

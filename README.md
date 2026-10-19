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

The next milestone will start with base durations by assignment type, an unknown-type fallback, and explanations. Actual duration rules have not been selected yet. Later adjustments may consider characteristics such as:

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

As of October 19, 2026, the first milestone is complete: sample JSON can be loaded into validated `Assignment` objects. The latest milestone verification passed 44 tests (15 model cases and 29 loader cases).

Implemented:

- An `Assignment` dataclass with required-text, numeric-type, nonnegative-point, and timezone-aware deadline validation.
- Four fictional assignments: quiz, essay, reading, and programming; the reading has no deadline or point value.
- `load_assignments(path)`, accepting a string or `Path`, preserving input order, converting ISO 8601 deadlines, and reporting invalid records with field and record context.
- Automated tests using temporary files for valid and malformed input.

The loader accepts an empty list, requires an explicit `due_at` field (which may be `null`), and uses model defaults for omitted points and descriptions. It raises an error rather than returning partial results when any record is invalid. Unknown fields are rejected by the model constructor.

The estimator, scheduler, Streamlit interface, database, Canvas, and Google Calendar are not implemented. The next milestone is a separate duration-estimate representation and a tested rule-based estimator. Local LLM estimation is an optional future experiment, not part of the current implementation.

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
│   └── loaders.py
├── sample_data/
│   └── assignments.json
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   └── test_loaders.py
└── docs/
    ├── project-plan.md
    └── development-journal.md
```

Add modules as their milestones begin. The proposed technology stack above is a roadmap, not a list of currently installed dependencies; application code currently uses only the Python standard library, with pytest for testing.

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

There is no web application entry point yet. The sample deadlines are fixed October 2026 dates; the loader accepts past deadlines, and future scheduling tests should supply an explicit planning start time.

## Current Limitations and Handoff

- Model validation runs at construction, not automatically on later field edits.
- Non-finite point values (NaN/infinity) and duplicate assignment IDs are not currently rejected.
- No scheduling policy for overdue or undated assignments exists yet.
- Dependencies are not pinned; 44 passing cases establish this checkpoint, not exhaustive validation.
- See [the project plan](docs/project-plan.md) for the next milestone and [the development journal](docs/development-journal.md) for decisions and learning notes. New sessions should also read `AGENTS.md` and inspect the current code and Git state.

## Author

Eric Rodriguez

Capstone Project, Fall 2026

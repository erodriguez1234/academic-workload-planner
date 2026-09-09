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
4. retrieve the student’s available study periods.
5. Generate study sessions based on workload and deadlines.
6. Display the proposed schedule for review.
7. Export approved sessions to Google Calendar.
8. Record actual completion times for future improvements.

## Initial Estimation Approach

The first version will use a rule-based estimator. It will consider available characteristics such as:

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

The project is currently in the planning and initial prototyping stage.

The first development milestone is to load sample assignments, estimate their durations, and generate a valid schedule without using external APIs.

## Proposed Project Structure

```text
academic-workload-planner/
├── app.py
├── AGENTS.md
├── README.md
├── requirements.txt
├── .gitignore
├── pages/
├── services/
├── scheduler/
├── database/
├── sample_data/
├── tests/
└── docs/
    ├── project-plan.md
    └── development-journal.md
```

This structure may change as the project develops.

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

Setup and execution instructions will be added after the initial prototype has been created.

## Author

Eric Rodriguez

Capstone Project, Fall 2026
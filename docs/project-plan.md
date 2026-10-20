# Intelligent Academic Workload Planner — Project Plan

## 1. Project Summary

The Intelligent Academic Workload Planner is a software prototype that converts academic assignments and student availability into a structured study schedule.

The system will eventually retrieve assignment data from Canvas, estimate the required completion time, divide large assignments into smaller work sessions, and schedule those sessions before their deadlines. The student will review the proposed schedule before any events are exported to Google Calendar.

This project is intended to demonstrate API integration, data processing, database design, algorithm development, software testing, and introductory predictive modeling.

## 2. Problem Statement

Students frequently manage assignments across several courses. Although Canvas displays deadlines, it does not estimate how long assignments will take or recommend when students should work on them.

Students may underestimate their workload, begin large assignments too late, or unknowingly plan more work than their available time can accommodate.

The proposed system addresses this problem by combining assignment information, estimated workload, deadlines, and student availability to generate a personalized study plan.

## 3. Primary Research and Development Question

Can assignment metadata, completion-time estimates, deadlines, and student availability be used to automatically generate a feasible and useful academic work schedule?

A secondary question is:

Can a personalized regression model estimate assignment completion time more accurately than a simple rule-based baseline?

## 4. Target User

The initial target user is a college student who:

- Uses Canvas to receive assignments
- Uses or is willing to use Google Calendar
- Manages assignments from multiple courses
- Has recurring or manually entered study availability
- Wants assistance distributing work before deadlines

The semester prototype will initially support one user.

## 5. Minimum Viable Product

The minimum viable product must:

1. Load assignments from a sample JSON file.
2. Convert the input into a consistent assignment representation.
3. Estimate assignment duration using a rule-based method.
4. Allow the student to enter available study periods.
5. Allow the student to set a maximum session length.
6. Split long assignments into smaller sessions.
7. Generate non-overlapping sessions.
8. Schedule sessions before deadlines whenever possible.
9. Enforce daily study limits.
10. Report assignments that cannot be scheduled completely.
11. Display assignments, estimates, and sessions in Streamlit.
12. Include automated tests for important scheduling rules.
13. Allow the student to review and adjust estimated durations before scheduling.

The minimum viable product must work without Canvas, Google Calendar, or machine learning.

## 6. Stretch Goals

The following features will only be attempted after the minimum viable product is complete:

- Importing live assignments through the Canvas REST API
- Reading busy periods from Google Calendar
- Exporting approved sessions to a separate Google Calendar
- SQLite database persistence
- Actual completion-time tracking
- A regression-based duration estimator
- Optional local LLM estimation comparison using a model such as Qwen through Ollama
- Automatic rescheduling after a missed session
- A built-in assignment timer
- Multiple-user support
- Full OAuth account onboarding

The timer, multiuser support, and continuous automatic rescheduling are considered low-priority stretch goals.

## 7. Non-Goals

The semester prototype is not intended to:

- Replace Canvas
- Guarantee exact completion-time predictions
- Build or train a large language model
- Support every learning-management system
- Produce a commercial production-ready service
- Support an unlimited number of users
- Access or analyze private assignment submissions
- Make irreversible calendar changes without user review
- Guarantee that every workload can fit into the available time

## 8. Technology Stack

### Core technologies

These are planned technologies. The completed loading milestone uses Python's standard library and pytest only; install other dependencies only when needed. The current environment uses Python 3.13; Python 3.11+ supports the loader's UTC `Z` parsing.

- Python
- Streamlit
- SQLite
- SQLAlchemy
- pandas
- pytest
- Git and GitHub

### External integrations

- Canvas LMS REST API
- Google Calendar API
- OAuth 2.0 for Google Calendar authorization
- A Canvas personal access token for initial single-user testing

### Predictive modeling

- scikit-learn
- A rule-based estimator as the baseline
- Linear or Ridge regression as an initial trained model
- Mean absolute error as the primary evaluation measurement

## 9. High-Level Architecture

The application will be separated into the following components:

### Data ingestion

Retrieves assignments from sample JSON data or the Canvas API.

### Data normalization

Converts external Canvas fields into a consistent internal assignment format.

### Duration estimation

Estimates the number of minutes required for each assignment.

### Scheduling engine

Converts assignments and availability into individual study sessions.

### Persistence

Stores assignments, preferences, estimates, sessions, and completion records.

### User interface

Allows the student to inspect assignments, modify estimates, enter availability, generate a schedule, and review the result.

### Calendar integration

Reads busy periods and exports approved study sessions.

## 10. Core Data Entities

### Course

Suggested fields:

- Internal ID
- Canvas course ID
- Course name
- Course code

### Assignment

Implemented in `workload_planner/models.py`:

- `assignment_id: str`
- `course: str`
- `title: str`
- `assignment_type: str`
- `due_at: datetime | None` (required argument, may explicitly be absent)
- `points_possible: float | None = None` (also accepts integers at runtime)
- `description: str = ""`

Required text must be nonblank strings. Supplied points must be numeric, not Boolean, and nonnegative. Supplied deadlines must be timezone-aware datetimes. Descriptions must be strings. Validation occurs in `__post_init__` at construction. Canvas IDs and submission status are deferred until needed.

### Estimate

Implemented as `DurationEstimate`, separately from `Assignment`, with these fields:

- Assignment ID
- Estimated minutes
- Estimation method
- Explanation

Estimated minutes mean active work: understanding instructions, completing the task, and reviewing it. Breaks and waiting time are excluded. The model validates positive integer minutes and nonblank text at construction. Timestamp/history and student adjustments are deferred.

### Availability Period

Suggested fields:

- Day or date
- Start time
- End time
- Recurring status

### Study Session

Suggested fields:

- Assignment ID
- Start date and time
- End date and time
- Session status
- Google Calendar event ID

### Completion Record

Suggested fields:

- Assignment ID
- Estimated minutes
- Actual minutes
- Completion date

## 11. Rule-Based Estimation Strategy

The first estimator will assign a base duration according to assignment type.

Implemented `rule_based_v1`: quiz 30, discussion 45, reading 60, homework 90, essay 180, programming 180; unknown types use 90 minutes. These are approximate hypotheses, not measured predictions. Matching normalizes whitespace/capitalization without modifying assignments. Explanations distinguish defaults/fallbacks. Tests cover rules, validation, repeatability, no mutation, and the sample-data pipeline. Points, descriptions, courses, and deadlines do not affect v1 durations. Workload extraction and student adjustments remain deferred.

Example categories may include:

- Quiz
- Discussion
- Reading
- Homework
- Essay
- Programming assignment
- Exam preparation
- Project

The estimate may then be adjusted using:

- Point value
- Description length
- Keywords
- Course
- Student-selected difficulty
- Previous actual completion times

The rules must remain visible and explainable so their behavior can be evaluated.

## 12. Machine-Learning Strategy

Machine learning will not be required for the first functional version.

Once enough completion records are available, a regression model may use features such as:

- Assignment type
- Course
- Point value
- Description length
- Days until the deadline
- Detected keywords
- Previous average duration for similar assignments

Categorical features may be processed using one-hot encoding.

The trained model will be compared against:

1. The original rule-based estimator
2. The average duration for assignments of the same type

A machine-learning model will only replace the baseline if it produces a meaningful improvement on previously unseen data.

Hosted AI estimation and local Qwen/Ollama inference were discussed, but neither was adopted for the MVP. A pretrained local model could later be compared with the rules using actual completion times, response latency, and failure rates. Calling a model does not automatically personalize it or train it. Local execution requires suitable hardware; remote web deployment would need access to a model service. Retain the rule-based baseline and fallback if this experiment is pursued.

## 13. Scheduling Strategy

The proposed first scheduler will use dated availability periods, order assignments by earliest deadline, and place work into the earliest available periods. Split work to respect maximum session length, allowing a shorter final session. More advanced slack-based prioritization is deferred until the baseline works.

Pass an explicit planning start time and choose a student timezone for daily limits. Define behavior for overdue or undated assignments, overlapping availability, and midnight-crossing periods before implementation. Weekly recurring availability will be expanded into dated periods over a chosen planning horizon for the interface.

The algorithm will:

1. Remove unavailable or occupied periods.
2. Calculate the remaining work for each assignment.
3. Initially rank assignments by deadline with deterministic tie handling.
4. Split assignment work into sessions.
5. Assign sessions to available periods.
6. Validate the resulting schedule.
7. Report any assignments that could not be scheduled completely.

Possible prioritization factors include:

- Time remaining before the deadline
- Estimated work remaining
- Available study time before the deadline
- Assignment priority
- Whether work has already been started

One useful concept is assignment slack:

```text
slack = available study time before deadline - remaining assignment work
```

Least-slack prioritization is a possible later improvement. The initial greedy algorithm does not guarantee an optimal schedule. A failure to place work must be reported as unscheduled work, not proof that no feasible arrangement exists.

## 14. Scheduling Constraints

A valid schedule must satisfy the following requirements:

- A session cannot occur after its assignment deadline.
- Two sessions cannot overlap.
- A session cannot occur outside an availability period.
- A session cannot exceed the maximum session length.
- Total scheduled work cannot exceed the daily study limit.
- A session must have a positive duration.
- The total session duration should equal the estimated assignment duration when enough time is available.
- An infeasible workload must produce a visible warning.

## 15. Testing Strategy

### Unit tests

Completed loading milestone: 15 model cases and 29 loader cases, all passing on October 19, 2026. Loader tests use pytest fixtures and temporary files. They cover multiple records, timezone offsets and UTC `Z`, null/default values, empty lists, malformed JSON, wrong structures, missing required fields, invalid dates/model values, record-context errors, and missing files. Scheduling and estimation tests below remain future work.

Unit tests will cover:

- Assignment data validation
- Duration-estimation rules
- Assignment splitting
- Deadline enforcement
- Overlap prevention
- Daily study limits
- Session-length limits
- Unschedulable workloads
- Missing due dates
- Time-zone handling

### Integration tests

Integration tests may cover:

- Loading and normalizing sample JSON
- Saving and retrieving database records
- Converting Canvas assignments into internal assignments
- Converting study sessions into Google Calendar events

### Manual interface tests

Manual testing will confirm that:

- Forms accept valid input
- Invalid input produces understandable feedback
- Schedules are displayed clearly
- The user can review sessions before calendar export
- Calendar events are not duplicated

## 16. Evaluation Plan

The project will be evaluated using both technical correctness and estimation quality.

### Scheduler evaluation

Possible measurements include:

- Number of overlapping sessions
- Number of sessions scheduled outside availability
- Number of sessions scheduled after deadlines
- Percentage of estimated work successfully scheduled
- Number of correctly reported infeasible assignments

A technically valid schedule should have zero overlaps and zero sessions outside permitted time.

### Estimator evaluation

The primary error measurement will be mean absolute error:

```text
absolute error = |estimated minutes - actual minutes|
```

```text
mean absolute error =
sum of absolute errors / number of completed assignments
```

The rule-based and regression estimators will be compared using the same test observations.

### Usability evaluation

If permitted, a small usability evaluation may ask users whether:

- The schedule was understandable
- The estimates appeared reasonable
- The sessions were appropriately divided
- The system reduced manual planning effort
- They would use a similar application

Any user study will follow the professor’s requirements concerning consent and student data.

## 17. Security and Privacy Plan

- Credentials will be stored in environment variables.
- The real `.env` file will be excluded from Git.
- A `.env.example` file will contain placeholders only.
- Assignment descriptions will not be sent to external AI services during the minimum viable product.
- Calendar events will be previewed before creation.
- Calendar event IDs will be stored to prevent duplicates.
- Testing will use synthetic or personally owned academic data.
- Sensitive student data will not be included in the public repository.
- Access will use the minimum permissions necessary.

## 18. Risks and Mitigations

### Insufficient training data

**Risk:** There may not be enough completion-time data to train an accurate regression model.

**Mitigation:** Build a rule-based estimator first and treat machine learning as an experiment or stretch goal.

### API authentication complexity

**Risk:** Canvas or Google authentication may consume significant development time.

**Mitigation:** Develop the core application using sample data before integrating either API.

### Excessive project scope

**Risk:** The combination of UI, APIs, databases, scheduling, and machine learning may exceed one semester.

**Mitigation:** Require only the minimum viable product and add integrations incrementally.

### Inaccurate duration estimates

**Risk:** Canvas metadata may not provide enough information for accurate predictions.

**Mitigation:** Allow user corrections, collect actual durations, and report estimation error honestly.

### Infeasible schedules

**Risk:** The student may not have enough available time to complete all assignments.

**Mitigation:** Report unscheduled work clearly instead of producing an invalid schedule.

### Time-zone errors

**Risk:** Canvas and Google Calendar may represent dates and times differently.

**Mitigation:** Store time-zone-aware date-times and test daylight-saving and deadline conversions.

### Duplicate calendar events

**Risk:** Running the export repeatedly may create duplicate events.

**Mitigation:** Store external event IDs and check them before creating new events.

## 19. Semester Milestones

### Milestone 1: Validated sample-data loading — complete

- Initialize the repository
- Add documentation
- Define sample assignment data
- Define and validate the Assignment representation
- Load sample JSON with datetime conversion and contextual errors
- Configure pytest
- Pass all 44 model/loader cases and verify the four sample records

### Milestone 2: Rule-based estimation — initial version complete

- Define a separate estimate representation and its tests
- Classify sample assignments
- Calculate initial duration estimates
- Validate estimates
- Add estimator tests

### Milestone 3: Scheduling engine

- Define study sessions, preferences, and a result containing unscheduled minutes/reasons
- Represent availability
- Split assignments into sessions
- Prioritize assignments
- Generate schedules
- Detect infeasible workloads
- Add scheduler tests

### Milestone 4: Streamlit interface

- Display assignments
- Accept availability
- Allow estimate adjustments
- Generate and display schedules
- Show warnings

### Milestone 5: Database persistence

- Add SQLite and SQLAlchemy
- Store assignments
- Store availability
- Store sessions and completion records

### Milestone 6: Canvas integration

- Authenticate using a personal development token
- Retrieve courses and assignments
- Save raw responses for development
- Normalize Canvas data
- Handle missing fields

### Milestone 7: Google Calendar integration

- Complete OAuth setup
- Read existing busy periods
- Preview proposed events
- Export approved sessions
- Prevent duplicate events

### Milestone 8: Estimator evaluation

- Collect actual completion-time observations
- Evaluate the rule-based baseline
- Train a simple regression model if sufficient data exists
- Compare errors

### Milestone 9: Final evaluation and presentation

- Complete system testing
- Document limitations
- Record demonstration data
- Prepare the capstone report
- Prepare the final demonstration

## 20. Definition of Project Success

The project will be considered successful if it can:

1. Load realistic assignment data.
2. Generate understandable duration estimates.
3. Accept student availability.
4. Produce non-overlapping study sessions within that availability.
5. Place sessions before deadlines whenever sufficient time exists.
6. identify and explain infeasible workloads.
7. Display the result through a usable interface.
8. Pass tests for the core scheduling constraints.
9. Demonstrate at least one external integration if time permits.
10. Document the accuracy and limitations of the estimation approach.

The project does not require a highly accurate machine-learning model or a production-ready multiuser service to be successful.

## 21. Current Status

As of October 19, 2026, milestone 1 is complete. `load_assignments(path: str | Path) -> list[Assignment]` reads UTF-8 JSON, preserves input order, converts ISO 8601 dates, and creates validated model objects. It requires a top-level list and object records. Required fields must be present; `due_at: null` is permitted. Omitted points/description use model defaults. Unknown fields are rejected by the constructor.

Malformed JSON produces a ValueError with file and syntax location. Record errors produce ValueError with a one-based record number and relevant field. File-access errors propagate. Invalid records stop loading rather than silently returning a partial list. The synthetic sample contains quiz, essay, reading, and programming records; exactly one has no deadline or points.

The initial estimator and DurationEstimate model are now implemented. All 79 cases pass: 36 model, 29 loader, and 14 estimator cases. Sample estimates are quiz 30, essay 180, reading 60, and programming 180 minutes. Availability/session models, scheduler, UI, persistence, and external integrations are not implemented. Next: scheduling representations and their validation tests.

Known limitations: model mutation bypasses construction validation; NaN/infinite points and duplicate IDs are not yet rejected; dependency versions are not pinned; deadlines in sample data are fixed and now past. These are documented follow-ups, not silently completed work.

The earlier September-to-December schedule and proposed October 6-to-November 2 acceleration were planning targets, not completion evidence. The accelerated dates need reassessment against the actual checkpoint. Prioritize the tested sample-data MVP and final documentation; attempt optional integrations only after it is stable. Confirm final delivery date and local-versus-public deployment expectations with the professor.

## 22. Immediate Next Tasks

1. Loading milestone committed as `8ffa2c4`.
2. Estimate representation, validation, and tests completed; review the implementation.
3. Base-duration rules, fallback, and explanations completed; commit this milestone when requested.
4. Define availability, preferences, sessions, and scheduling results.
5. Build the scheduler incrementally with constraint tests and explicit unscheduled-work reports.
6. Demonstrate the complete pipeline with fitting and overloaded sample workloads.
7. Add a Streamlit interface, weekly availability expansion, editable estimates, and warnings.
8. Evaluate and document the core MVP before adding SQLite, Canvas, or Google Calendar.
9. Collect completion-time observations for estimation evaluation; local LLM/regression experiments remain optional.
10. Prepare the report, repeatable demonstration, and deployment appropriate to course requirements.

At each milestone, verify tests, review changes, record decisions and limitations in the journal, and make a focused Git checkpoint. New chats should read `AGENTS.md`, the README, this status section, and the journal, then verify source and Git state. Do not assume prior conversation access or treat exploratory ideas as approved scope.

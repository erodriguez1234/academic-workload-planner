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

### Scheduling representations — step 4 complete

Implemented in `workload_planner/scheduling_models.py` as frozen dataclasses:

- `AvailabilityPeriod(start_at, end_at)`: dated, aware datetime boundaries; may cross midnight.
- `SchedulingPreferences(planning_start, student_timezone, max_session_minutes, daily_study_limit_minutes)`: explicit aware planning start, standard-library `ZoneInfo`, and positive integer limits.
- `SchedulingTask(assignment_id, required_minutes, due_at)`: independent of the estimation method; accepts missing/past deadlines as data.
- `StudySession(assignment_id, start_at, end_at)`: positive whole-minute interval; `duration_minutes` is derived using UTC elapsed time.
- `UnscheduledWork(assignment_id, remaining_minutes, reason)`: positive integer remainder and a validated reason code.
- `ScheduleResult(tasks, sessions, unscheduled_work)`: tuples of validated records; unique task IDs, known output IDs, at most one remainder per task, and exact minute accounting per task.

Required IDs are nonblank strings; Boolean and floating-point minute values are rejected.
Frozen dataclasses prevent ordinary reassignment after construction. Calendar identifiers,
recurrence, completion status, and interface controls remain deferred.

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

### Adopted baseline policies (implemented in step 5)

- Missing deadlines: leave all requested minutes unscheduled with `missing_deadline`.
- Deadlines at or before planning start: leave all minutes unscheduled with `deadline_not_after_start`.
- Rank eligible tasks by deadline instant in UTC, then assignment ID; reject duplicate IDs.
- Reject overlapping availability rather than double-counting it. Touching endpoints are allowed.
- Allow dated availability across midnight; split sessions at midnight in the student's timezone so each session belongs to one local day.
- Clip usable availability at planning start and deadline. Sessions may end exactly at a deadline.
- Use positive whole active minutes. Respect both session and daily caps even when the session cap exceeds the daily cap.
- Report leftover eligible work as `unplaced_by_greedy`; this does not prove infeasibility.
- Account for every task's requested minutes as session minutes plus remaining minutes.

Step 4 models validate data and accounting only. Step 5 adds `build_schedule()` in
`scheduler.py`, implementing these policies during placement with 21 scheduler cases.
It sorts/splits dated windows, tracks their remaining free starts, and shares per-local-day
minute totals across tasks. All arithmetic uses UTC; output sessions use the student timezone.
No recurrence expansion or independent post-generation schedule validator is implemented.
Step 6 completed the failure/boundary audit with 22 additional scheduler cases (43 total)
and 3 failure-message cases. A shared test helper independently verifies no overlap,
availability containment, deadlines, session/local daily limits, reason selection, and
per-task accounting. Existing and added tests cover repeatability and preserved inputs.
`UnscheduledWork.message` calculates a readable explanation from existing fields; it says
"Could not schedule" without claiming infeasibility. Placement behavior is unchanged.

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

### Interface and weekly expansion decisions — October 21

- `streamlit_app.py` calls existing tested loader/estimator/scheduler functions. No estimation or placement rules moved into the page.
- `availability.py` defines frozen `WeeklyAvailability` and a separately tested expansion function, leaving scheduler inputs as dated periods.
- Weekly weekdays use Monday=0 through Sunday=6. The first page offers one enabled window per day; the expander supports multiple rules but rejects overlaps.
- End earlier than start means overnight; equal times are invalid. Include previous-day carry-in and clip to an inclusive date horizon of 1–366 days.
- Reject ambiguous/nonexistent local-time endpoints and planning starts using UTC round-trip checks instead of guessing around daylight-saving changes.
- Store student-adjusted minutes separately in session state and create `SchedulingTask` objects from them; preserve original estimates and assignments.
- Keep all widgets rendered with stable keys so values survive reruns. Generate only on button click; hide stale results after edits. Reset demo explicitly restores defaults.
- Demo defaults are fixed October 10–17, 2026, with daily 18:00–20:00 availability. The expected baseline is 390 scheduled + 60 undated reading minutes unscheduled.
- Streamlit 1.66.0 is the only new directly declared dependency, installed in `.venv`. No database, account login, domain, external API, calendar, or public deployment is included.
- AppTest covers real widget interactions, retained values, adjusted minutes reaching the scheduler, invalid inputs/recovery, stale-result hiding, and warnings. Local HTTP/health checks passed; visual browser automation was unavailable.

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

### November 4 update — Canvas import implemented, live verification pending

- Read-only client, all-page course/assignment retrieval, safe failure reporting, and
  explicit local Streamlit connection/import actions are implemented; 347 tests pass.
- The student supplied the public Canvas site root `https://cilearn.csuci.edu`.
  No live requests or real assignment inspection were performed by the agent.
- `canvas_import.py` wraps the existing `Assignment` with student submission status
  and a default-selection flag. This avoids changing estimator/scheduler models.
- Preserve effective student `due_at` with date overrides enabled. Namespace IDs by
  Canvas host, course ID, and assignment ID. Quiz/discussion mapping requires explicit
  submission metadata; everything else uses the existing unknown-type fallback.
- Course failures, invalid records, and duplicate IDs are reported as coverage gaps.
  Successful courses remain inspectable; stale snapshots are cleared before refresh.
- The local password form creates an in-memory client. No secret file, new dependency,
  database, Canvas write, Google integration, or public deployment was introduced.
- Scope now prioritizes the owner's local Canvas demonstration, followed by reviewed
  Google Calendar export. The older SQLite-first sequence below is historical.

The following paragraphs record prior checkpoints.

As of October 19, 2026, milestone 1 is complete. `load_assignments(path: str | Path) -> list[Assignment]` reads UTF-8 JSON, preserves input order, converts ISO 8601 dates, and creates validated model objects. It requires a top-level list and object records. Required fields must be present; `due_at: null` is permitted. Omitted points/description use model defaults. Unknown fields are rejected by the constructor.

Malformed JSON produces a ValueError with file and syntax location. Record errors produce ValueError with a one-based record number and relevant field. File-access errors propagate. Invalid records stop loading rather than silently returning a partial list. The synthetic sample contains quiz, essay, reading, and programming records; exactly one has no deadline or points.

The initial estimator and DurationEstimate model are now implemented. All 79 cases pass: 36 model, 29 loader, and 14 estimator cases. Sample estimates are quiz 30, essay 180, reading 60, and programming 180 minutes. Scheduling representations are now implemented with 94 additional cases (173 total passing). As of October 20, step 5 adds the simplest working scheduler with 21 additional cases (194 total passing). It places, splits, and continues work, orders tasks by deadline/ID, enforces session and daily limits, and returns accounted remaining work. At the step 5 checkpoint, UI, persistence, and external integrations were not implemented. Step 6 now adds readable failure messages and the independent constraint audit: 219 total passing (97 scheduling-model and 43 scheduler cases, plus the original 79). Placement behavior is unchanged. As of October 21, the first Streamlit interface is implemented (253 total passing: prior 219 + 20 weekly-availability + 14 interface cases). The user explicitly deferred the standalone pipeline demonstration to prioritize the meeting interface. The page connects loading, estimates, student minute adjustments, weekly expansion, and scheduling; persistence and external integrations remain deferred. Next: review the interface and rehearse the demo.

Known limitations: existing mutable models can bypass construction validation; assignment loading still accepts NaN/infinite points and duplicate IDs (scheduling results reject duplicate task IDs); dependency versions are not fully pinned; deadlines in sample data are fixed and now past. These are documented follow-ups, not silently completed work.

The earlier September-to-December schedule and proposed October 6-to-November 2 acceleration were planning targets, not completion evidence. The accelerated dates need reassessment against the actual checkpoint. Prioritize the tested sample-data MVP and final documentation; attempt optional integrations only after it is stable. Confirm final delivery date and local-versus-public deployment expectations with the professor.

## 22. Immediate Next Tasks

Current next step: verify a real import locally with a replacement token entered only
in the app. Review course access gaps, applicable deadlines, status labels, selections,
and duration adjustments. Set current planning dates explicitly and rehearse a plan.
Then design Google OAuth, a dedicated planner calendar, reviewed export with durable
duplicate prevention, and reconciliation limited to planner-owned events. These are
future milestones; defer database work, AI, feeds, multiuser login, and public hosting.

Historical implementation sequence:

1. Loading milestone committed as `8ffa2c4`.
2. Estimate representation, validation, and tests completed; review the implementation.
3. Base-duration rules, fallback, and explanations completed in `d63da55`.
4. Availability, preferences, sessions, tasks, and accounted scheduling results completed.
5. Simplest scheduler completed with incremental tests and explicit unscheduled-work reports.
6. Failure messages and boundary/constraint audit completed; standalone pipeline demonstration deferred at user request.
7. First Streamlit interface, weekly availability expansion, editable minutes, and warnings completed; review and rehearse the local demonstration. (This is the interface step the user referred to as step 8.)
8. Evaluate and document the core MVP before adding SQLite, Canvas, or Google Calendar.
9. Collect completion-time observations for estimation evaluation; local LLM/regression experiments remain optional.
10. Prepare the report, repeatable demonstration, and deployment appropriate to course requirements.

At each milestone, verify tests, review changes, record decisions and limitations in the journal, and make a focused Git checkpoint. New chats should read `AGENTS.md`, the README, this status section, and the journal, then verify source and Git state. Do not assume prior conversation access or treat exploratory ideas as approved scope.

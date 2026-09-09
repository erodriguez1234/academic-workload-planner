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

The minimum viable product must work without Canvas, Google Calendar, or machine learning.

## 6. Stretch Goals

The following features will only be attempted after the minimum viable product is complete:

- Importing live assignments through the Canvas REST API
- Reading busy periods from Google Calendar
- Exporting approved sessions to a separate Google Calendar
- SQLite database persistence
- User adjustment of duration estimates
- Actual completion-time tracking
- A regression-based duration estimator
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

Suggested fields:

- Internal ID
- Canvas assignment ID
- Course ID
- Title
- Description
- Assignment type
- Point value
- Due date and time
- Submission status

### Estimate

Suggested fields:

- Assignment ID
- Estimated minutes
- Estimation method
- Date generated
- User-adjusted value

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

## 13. Scheduling Strategy

The scheduler will initially divide availability into fixed-size time blocks.

The algorithm will:

1. Remove unavailable or occupied periods.
2. Calculate the remaining work for each assignment.
3. Rank assignments according to urgency and scheduling difficulty.
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

Assignments with the least slack should generally receive higher priority.

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

### Milestone 1: Repository and requirements

- Initialize the repository
- Add documentation
- Define sample assignment data
- Define assignment and session representations
- Configure pytest

### Milestone 2: Rule-based estimation

- Classify sample assignments
- Calculate initial duration estimates
- Validate estimates
- Add estimator tests

### Milestone 3: Scheduling engine

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

The project is currently in the planning and initial development stage.

The immediate next milestone is:

> Given a sample JSON file containing assignments and a manually defined weekly availability schedule, generate non-overlapping study sessions that finish before their respective deadlines.

## 22. Immediate Next Tasks

1. Create the initial repository structure.
2. Add a `.gitignore`.
3. Create a Python virtual environment.
4. Create a sample assignment JSON file.
5. Define the internal `Assignment` and `StudySession` data structures.
6. Write a loader for the sample JSON.
7. Write initial validation tests.
8. Commit the first working checkpoint.
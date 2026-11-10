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

November 9, 2026 update: selected undated work can use a student-entered deadline or
be planned after dated work associated with its confirmed week. Canvas modules can be
mapped to week-start dates; Roll Call Attendance is excluded from workload imports.
531 tests pass with synthetic data and mocked APIs.

November 9, 2026 update: local reload preferences restore the last data mode, remembered
Canvas connection/current classes, fresh assignment imports, and saved Google authorization.
499 tests pass. Credentials remain in Keychain; approval and generated plans remain temporary.

November 8, 2026 update: Google connection, calendar-aware scheduling, and reviewed
study-session export are implemented. New sessions fit around Busy events in selected
calendars. Export uses stable IDs and a private intent ledger to recover retries without
duplicating sessions. Tests use synthetic responses; live verification remains a user action.
Automatic moving/deletion and changed-schedule reconciliation remain deferred.

November 7, 2026 update: selected Canvas assignments run through the existing estimator
and scheduler with current, editable Canvas planning dates. Canvas duration edits survive
re-imports and browser refreshes through private local preferences. All 401 tests pass;
integration checks use synthetic Canvas responses rather than fetching private live data.
Google Calendar export remains unimplemented. Earlier counts below are historical.

November 4, 2026 update: the read-only Canvas client, assignment conversion,
and local Streamlit import/selection flow are implemented. All 347 tests pass
with synthetic responses; real-account import remains to be verified locally.
No database or Google Calendar integration exists. See the Canvas instructions below.
The October checkpoint below describes the earlier sample-data milestone.

As of October 21, 2026, the sample-data core and first single-page Streamlit interface are implemented. The latest verification passed 253 tests: the existing 219 core cases, 20 weekly-availability cases, and 14 interface cases.

Implemented:

- An `Assignment` dataclass with required-text, numeric-type, nonnegative-point, and timezone-aware deadline validation.
- Four fictional assignments: quiz, essay, reading, and programming; the reading has no deadline or point value.
- `load_assignments(path)`, accepting a string or `Path`, preserving input order, converting ISO 8601 deadlines, and reporting invalid records with field and record context.
- Automated tests using temporary files for valid and malformed input.

The loader accepts an empty list, requires an explicit `due_at` field (which may be `null`), and uses model defaults for omitted points and descriptions. It raises an error rather than returning partial results when any record is invalid. Unknown fields are rejected by the model constructor.

The local Streamlit interface calls the existing loader, estimator, and earliest-deadline-first scheduler. It supports session-local student minute adjustments, weekly availability, planning preferences, sessions, and warnings. The separate pipeline-demonstration step was deferred at the user's request so the interface could be built for a meeting. Next: review the page and rehearse the demo. Database, Canvas, Google Calendar, workload extraction, and AI remain unimplemented.

## Current Project Structure

```text
academic-workload-planner/
├── AGENTS.md
├── README.md
├── requirements.txt
├── streamlit_app.py
├── .gitignore
├── workload_planner/
│   ├── __init__.py
│   ├── models.py
│   ├── scheduling_models.py
│   ├── scheduler.py
│   ├── availability.py
│   ├── estimator.py
│   └── loaders.py
├── sample_data/
│   └── assignments.json
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_scheduling_models.py
│   ├── test_scheduler.py
│   ├── test_availability.py
│   ├── test_streamlit_app.py
│   ├── test_estimator.py
│   └── test_loaders.py
└── docs/
    ├── project-plan.md
    └── development-journal.md
```

Add modules as their milestones begin. The proposed technology stack above is a roadmap, not a list of currently installed dependencies; core scheduling/estimation code uses the Python standard library. The interface adds Streamlit (and its required dependencies), with pytest and Streamlit AppTest for testing.

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
session length, and existing-calendar work are not modeled by the scheduler. The interface expands weekly availability separately before calling it.
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

## Local Web Interface (First Version)

`streamlit_app.py` connects the existing modules on one browser page:

1. View the four sample assignments, original estimates, and minutes to use for planning.
2. Open **Adjust working minutes** to change a duration without modifying the original estimate.
3. Use the sidebar for explicit planning start date/time, inclusive end date, IANA timezone, session cap, and daily cap.
4. Select weekly study days and times, then click **Generate schedule**.
5. Review the session table, requested/scheduled/unscheduled totals, and readable warnings.

The initial demo uses October 10–17, 2026, America/Los_Angeles, daily 18:00–20:00
availability, a 60-minute session cap, and a 120-minute daily cap. This intentionally
precedes the fixed sample deadlines. It schedules 390 minutes; the undated reading's
60 minutes remain explicitly unscheduled. Choosing a later real-world planning date
will correctly report the sample deadlines as overdue.

`workload_planner/availability.py` expands weekly rules into dated periods over an inclusive
horizon of at most 366 days. The page offers one window per weekday. An earlier end means
the next day; equal times are rejected. Expansion includes overnight carry-in, clips at
horizon boundaries, and rejects overlapping windows. Ambiguous/nonexistent local clock
change endpoints or planning starts require a different time; the app does not guess.

Widget keys and `st.session_state` retain values and results during normal interactions
in the active browser session. **Reset demo** restores all demonstration settings and
original minutes. Editing inputs hides stale sessions until generation is requested again.
Validation errors leave the inputs available for correction. Refreshing/reconnecting,
opening a new session, or restarting the server may reset values; no durable storage exists.

For a short meeting demonstration:

1. Click **Generate schedule** and show sessions plus the missing-deadline warning.
2. Adjust the quiz from 30 to 75 minutes and regenerate; the original 30-minute estimate remains visible.
3. Lower the daily limit to 30 minutes and regenerate to show additional unscheduled work.
4. Enter an invalid timezone to show readable feedback, then click **Reset demo**.

Streamlit's AppTest exercises the real page and widgets. A local server smoke check
returned HTTP 200 and a healthy status. Automated visual browser inspection was unavailable
in the development session; review the rendered layout locally before the meeting.

## Importing Your Own Canvas Assignments Locally

1. Start the local app using the command in **Running the Project** and choose **Canvas**.
2. Confirm the Canvas site root (default `https://cilearn.csuci.edu`).
3. Enter your personal token privately in the password field. Optionally check
   **Remember token on this Mac**, then click **Load courses**.
4. Choose **Classes you’re taking this semester**, then click **Import assignments**.
   Class IDs are saved locally. Canvas retrieval uses GET requests only.
5. Inspect the full assignment table and import warnings, then choose **Assignments to schedule**.
6. Review your planning dates and availability before generating. Canvas starts at the next
   whole minute in the student timezone with a 14-day inclusive horizon. **Use current dates**
   updates that suggestion explicitly. Edit either date for your workload. Sample mode retains
   the fixed October 10–17, 2026 demo; the two modes retain separate dates during the session.
7. Use **Disconnect and clear Canvas data** to remove the active connection/imported snapshot.
   Use **Forget saved token** to also delete this site's remembered token from macOS Keychain.

The token-entry form hides once courses load successfully. Disconnecting restores
an empty token field for reconnecting; failed connection attempts keep the form visible.

Adjust **working minutes** before clicking **Generate schedule**. The original estimate stays
visible. Canvas edits save automatically by stable assignment ID in
`.local/duration_adjustments.json`, which Git ignores. This owner-readable/writable file holds
only assignment IDs and integer minutes, not tokens, titles, descriptions, or imported records.
Edits survive re-import, deselection, browser refresh, and server restart when the file remains
available. Mode/current-class choices also survive reloads; planning dates, availability,
assignment/session selections, generated results, and export approval remain session-local.
Read/write problems produce a warning; in-memory edits still apply. Corrupt saved files are
reported rather than silently overwritten. Sample minute edits remain session-local.

Only selected assignments become scheduling tasks. Requested minutes always equal scheduled
plus unscheduled minutes, including partially placed work. Missing/overdue deadlines and greedy
shortfalls have explicit warnings. For example, the integration test requests 330 minutes,
schedules 60, and reports the other 270 across the three reasons. The historical sample demo
still produces 390 scheduled + 60 unscheduled minutes.

Keep tokens out of chat, source files, screenshots, and Git. Revoke any token shared in chat
and create a replacement. By default the connection uses session memory only. Opt-in
remembering uses macOS Keychain through `keyring==25.7.0`, outside Git; no credential file
or plaintext fallback is created. The password field is never prefilled with a saved token.
After a successful remembered connection, reloads reopen your last mode, reconnect Canvas,
validate accessible classes, and import fresh assignments for saved classes once per browser
session. Ordinary widget reruns do not repeat this work. Class choices are saved per Canvas
site; inaccessible classes are warned about and skipped without silently erasing saved IDs.
**Disconnect and clear Canvas data** disables automatic reconnect while keeping class choices.
To resume again, leave the token blank and click **Load courses** using the saved Keychain token.
macOS may ask you to allow Python to access Keychain. Tokens still expire/revoke in Canvas;
enter a replacement and check Remember to update one. Saving occurs only after successful
course retrieval. Storage errors leave the current successful connection usable.

Deadline/session tables use month names and AM/PM (for example, **November 6, 2026
11:59PM PST**). Deadlines are displayed in the selected student timezone; original
timestamps and scheduling calculations remain unchanged. Date pickers use MM/DD/YYYY
and time controls use 12-hour AM/PM.

The importer requests every page for selected courses and reports failed courses, malformed
records, and duplicate IDs. Coverage means assignments accessible through the Canvas assignment
API for those courses, not every item visible elsewhere in Canvas. Re-import explicitly to refresh.
Failed refreshes clear the previous snapshot; changing courses hides results until re-import.

Stable IDs include the Canvas site, course ID, and assignment ID. The importer preserves the
requesting student's effective `due_at`; null remains **No deadline**. Only explicit
`online_quiz` and `discussion_topic` submission types map to quiz/discussion. Uploads,
text entries, external tools, and ambiguous types use `unknown` and the existing provisional
90-minute fallback. Neither titles nor file extensions establish essay/programming categories.

Submitted, graded, pending-review, excused, and unknown-status work remains visible and starts
unchecked. Grading does not prove that no further work is needed; you may explicitly select
any imported item. Unsubmitted work and Canvas redo requests start selected. The UI does not
infer your status from `has_submitted_submissions`, which can refer to other students.
Canvas lock/unlock restrictions are not additional scheduling constraints in this version.

`canvas_client.py` handles HTTP, `canvas_import.py` handles conversion/import reports, and
`canvas_ui.py` handles Streamlit controls. Estimator and scheduler rules are unchanged.
Tests cover synthetic responses and AppTest interactions; live data and visual layout remain
for local review. Sample-data mode remains available; reviewed Google export is described below.

## Planning Assignments Without Deadlines

Selected assignments without a Canvas deadline appear in **Review assignments with no
deadline**. The import table continues to show **No deadline**; your choices do not change
Canvas or the original Assignment object.

- **Manual deadline:** enter a date/time in the selected student timezone. This is a student
  planning deadline and takes normal deadline priority. A later real Canvas deadline wins.
- **After dated work (choose week):** choose a date in the assignment's reference week.
- **After dated work (module week):** first click **Load module placement from Canvas**.
  Confirm a Monday week-start date for the relevant module, then select the assignment's
  intended module. Multiple module memberships require your choice; names such as Module 3
  and unlock dates are not treated as due dates or reliable calendar-week numbers.
- **Choose how to plan:** leave unresolved work unscheduled with every minute accounted for.
  A selected module-based option with missing/unverified mapping blocks generation until
  reviewed; choose another option if module access is unavailable.

Week-based work has no invented Sunday due date. The planner reserves time for all selected
work with real/manual deadlines first. For each reference week, it then waits until the last
dated-work day and the end of its reserved sessions before placing undated work. Confirmed
module weeks group dated work where possible; otherwise the actual due-date week is used.
For Monday/Tuesday/Wednesday deadlines, undated work starts Wednesday or later. If related
dated work remains unscheduled, that week’s undated work waits too. It may spill into later
weeks up to the entered planning horizon; extend that horizon if needed. Busy time, retained
bookings, daily/session limits, and exact minute accounting apply across both priority passes.
Existing bookings incompatible with a new priority choice require review, not automatic moves.

Canvas planning choices and module weeks are saved by stable IDs in ignored owner-only
`.local/planner_preferences.json`; there are no assignment titles/descriptions or credentials
in that file. Configured module-based choices refresh module membership during re-import.
Otherwise module lookup is an explicit read-only action. Module/item retrieval fetches all
pages and reports access gaps. Direct assignment links and explicitly matched quiz/discussion
IDs are supported; ambiguous/unavailable links require a manual week/deadline. Normal API
access limitations still apply. Sample choices remain temporary, preserving the historical
390 scheduled + 60 unscheduled demonstration until you explicitly choose a reading target.

Exact **Roll Call Attendance** (also **Roll Call Attendence**) titles are excluded from import
rows and scheduling choices, ignoring case and extra whitespace. Other attendance-related
assignments remain visible. Re-import or reload to remove an existing snapshot's Roll Call row.
This filter does not delete any Canvas assignment or existing Google event.

## Connecting Google Calendar Locally

Developer setup: enable the Calendar API in your Cloud project, configure an External
OAuth app in Testing with your account(s) as test users, and create a Desktop OAuth client.
Keep its downloaded JSON at `.local/google_oauth_client.json`. This folder is ignored by Git.
Do not paste the file, tokens, or callback URLs into chat or commit them.

In Streamlit, expand **Google Calendar** in the sidebar:

1. Click **Connect Google Calendar**. If saved authorization is available, the app reuses
   or refreshes it. Otherwise Google's page opens in the Mac's default browser; choose
   the intended Google account and approve access within two minutes.
2. Return to the planner. macOS may request permission to store/access credentials in Keychain.
3. Review the calendar name and student timezone, then explicitly click **Create planner calendar**.
   This creates a secondary calendar named **Academic Workload Planner** in the account you chose.
4. Use **Check planner calendar access** to verify it. Reconnecting normally reuses its saved ID.
5. **Disconnect Google Calendar** clears the connection and disables automatic reconnect. **Forget saved Google
   authorization** also removes the local Keychain record; it does not revoke Google's consent
   or delete calendars. Consent can be revoked in Google Account settings.

The flow requests `calendar.app.created`, `calendar.calendarlist.readonly`,
`calendar.events.freebusy`, and basic `openid` identity. Calendar-list access supplies names
and IDs; free/busy supplies occupied intervals without personal event titles/descriptions.
Event reads/writes are restricted in code to the dedicated planner calendar. A verified Google subject ID binds calendar
metadata to the account: **Authorize Google again** retains the dedicated calendar for the
same account, while a different account starts without a selected calendar. Forgetting the
Keychain record removes that local association, so check for an existing calendar before
creating another. This is a local, single-account-at-a-time demonstration, not hosted OAuth.

The Google authentication SDK handles state/PKCE and the loopback callback. Tokens, identity,
calendar ID, and an ownership marker stay in macOS Keychain; no `token.json` is written. The
downloaded client JSON is restricted to owner read/write permissions. Callback and token-exchange
logging is suppressed. After a successful connection, reloads restore saved authorization
and refresh expired access when possible, without opening a sign-in window. Missing/revoked
consent requires an explicit Connect/Authorize action; failed automatic restoration is attempted
only once per browser session. Calendar creation and event export still require explicit actions.

Expired access credentials refresh automatically when possible. If renewal fails, the app gives
a reconnection message. Google can require a new sign-in if access is revoked or a testing refresh
token expires; External/Testing applications using Calendar access commonly require reauthorization
after seven days. School policy can also block consent. No trial or paid hosting is introduced.

Calendar creation is never automatically retried. A pending marker is saved before the request.
If its outcome is uncertain, the app blocks another creation and offers **Recover planner calendar**:
copy that calendar's ID from Google Calendar settings → Integrate calendar. Recovery requires the
matching ownership marker; unrelated calendars are rejected. Calendar creation is separate
from the reviewed session export below. No calendar/event deletion or automatic reconciliation is implemented.

## Remembering Your Local Setup

This is a single-user Mac demonstration. `.local/planner_preferences.json` is ignored by Git
and written atomically with owner-only permissions. It holds the last assignment source,
Canvas site/current class IDs, and connection-resume flags—not credentials or assignment content.
The server reads these choices after reload/restart; no database or browser cookie is needed.
Damaged/unreadable preferences are reported and not overwritten. Credentials must remain in
Keychain, and the Canvas token must still be valid. Disconnect disables the corresponding
resume flag; Forget additionally removes saved credentials. There is no automatic login flow,
calendar creation, generation, or event export on reload.

For an existing installation, connect each service once after this update to enable resume.
Canvas can use a blank field to load an already remembered token. Select your semester classes
once. Google normally reuses saved authorization, without another consent screen unless needed.
You can still switch to the historical sample demonstration at any time.

## Scheduling Around Existing Calendar Events and Exporting

If you authorized an earlier version, open **Google Auth Platform → Data Access** in your
Cloud project and add these scopes alongside the existing app-created-calendar scope:

- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`
- `https://www.googleapis.com/auth/calendar.events.freebusy`

Keep the intended accounts as test users. In the planner, click **Authorize Google again**
and approve the updated permissions. Using the same account retains its planner calendar.
Older saved credentials are rejected rather than treated as if they granted new access.

1. In Canvas mode, **Avoid Google Calendar busy times** defaults on. Check your explicit
   planning dates, duration adjustments, weekly availability, timezone, and study limits.
2. Primary and planner calendars are always checked. Click **Load other calendars** and
   select any additional calendars whose events should block study time. Unselected calendars
   are not checked. Normal events marked **Free** do not block; Busy recurring/all-day events do.
3. Click **Generate schedule** to read current busy intervals and fit new study sessions into
   your entered availability. Failed/incomplete calendar reads stop generation. This reads
   calendars without changing them. Requested minutes equal booked + proposed + unscheduled.
4. Select individual proposed sessions, click **Preview selected sessions**, review statuses,
   check the approval box, and click **Export approved sessions**. Preview does not write Google
   events. Export rechecks busy time and skips conflicts, past sessions, and changed events.
   Changed account, calendars, planning inputs, or selected sessions require fresh review.
5. Check the per-session export results. For timeout/restart recovery, use **Review unfinished
   exports**, preview the recorded attempt, and approve ready retries. Matching existing events
   are recognized without another insert. No background retry runs on refresh.

The app writes only to its ownership-marked planner calendar, with no attendees, default
reminders, updates, or deletes. Event IDs are deterministic for account/calendar, assignment,
and UTC interval. Private event metadata identifies app ownership. The owner-only, atomically
replaced `.local/calendar_exports.json` stores IDs, intervals, assignment IDs, and attempt
states; it contains no tokens or titles. Keep this ignored file for recovery across restarts.
An unreadable ledger blocks export and is not overwritten.

On regeneration, verified future planner bookings remain fixed and count toward assignment
minutes and daily study capacity, including bookings outside the new horizon. Only the remainder
is scheduled. Existing bookings that were moved, deleted, exceed adjusted minutes, or no longer
fit the deadline can block replanning for review. Automatic reconciliation is a later milestone;
this step never shifts an existing event. Past bookings are not evidence of completed work:
review remaining assignment minutes yourself. Existing conflicts involving retained bookings
also require manual review. There is no atomic Google free/busy-and-insert transaction, so an
external change during export can still introduce a race despite immediate rechecks.

Sample mode keeps October 10–17, 2026 and defaults calendar checks off. Past demo sessions
cannot be exported. Google Tasks, automatic schedule reconciliation, and public hosting remain
outside this step. No new dependency was needed.

## Private Data

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

The current checkpoint was verified with Python 3.13, pytest 9.1.1, and Streamlit 1.66.0. Use Python 3.11 or newer for this code, including ISO 8601 deadlines ending in `Z`.

From the repository root on macOS/Linux, create an environment once if `.venv` does not already exist:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If the environment already exists, install/update the declared dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Start the local browser interface:

```bash
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit (normally http://127.0.0.1:8501).
Keep the terminal process running while using the page; press Ctrl+C to stop it.
No domain, hosting account, or public deployment is needed for a local demonstration.

Run all tests:

```bash
.venv/bin/python -m pytest -v
```

Try the actual sample data:

```bash
.venv/bin/python -c 'from workload_planner.loaders import load_assignments; assignments = load_assignments("sample_data/assignments.json"); print(f"Loaded {len(assignments)} assignments"); print(assignments[0])'
```

In VS Code, use **Python: Select Interpreter** to select `.venv/bin/python`. Configure **Python: Configure Tests → pytest → tests** to use the Testing view. Code Runner's direct execution of a test file does not run pytest and can produce import-path errors. Explicit `.venv/bin/python` commands do not require activation; optional terminal activation is `source .venv/bin/activate`.

`streamlit_app.py` is the web application entry point. The sample deadlines are fixed October 2026 dates; the loader accepts past deadlines, and scheduling calls and tests supply an explicit planning start time.

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
- Streamlit is pinned to the tested version; pytest and transitive dependencies are not fully pinned. The 253 passing cases establish this checkpoint, not exhaustive validation or prediction accuracy.
- See [the project plan](docs/project-plan.md) for the next milestone and [the development journal](docs/development-journal.md) for decisions and learning notes. New sessions should also read `AGENTS.md` and inspect the current code and Git state.

## Author

Eric Rodriguez

Capstone Project, Fall 2026

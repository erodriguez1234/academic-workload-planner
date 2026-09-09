# Academic Workload Planner

## Project goal

Build a semester-scale Python prototype that imports Canvas assignments,
estimates their required completion time, and schedules study sessions
before their deadlines.

## Technology stack

- Python
- Streamlit
- SQLite and SQLAlchemy
- pandas
- pytest
- Canvas REST API
- Google Calendar API
- scikit-learn later in development

## Development priorities

1. Build and test the scheduling logic using sample JSON data.
2. Add a simple Streamlit interface.
3. Add SQLite storage.
4. Integrate the Canvas API.
5. Integrate Google Calendar.
6. Experiment with prediction models only after collecting data.

## Coding guidelines

- Keep API, database, scheduling, and interface logic in separate modules.
- Use type hints and clear function names.
- Write tests for scheduling behavior.
- Never commit API keys, tokens, or OAuth credentials.
- Explain significant architectural changes before implementing them.
- Prefer small, focused changes that can be tested independently.
- Do not add a new dependency unless it is necessary.
- Do not replace working code without explaining the reason.

## Learning requirement

This is a student capstone. Explain important code and design decisions
so that the student can understand and present the work independently.
Do not implement large features without breaking them into understandable
steps.
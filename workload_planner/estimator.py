"""Simple, explainable assignment-type estimates; no measured accuracy claimed."""

from workload_planner.models import Assignment, DurationEstimate


# Provisional active-working-time defaults, to be evaluated against real records.
BASE_MINUTES_BY_TYPE: dict[str, int] = {
    "quiz": 30,
    "discussion": 45,
    "reading": 60,
    "homework": 90,
    "essay": 180,
    "programming": 180,
}
FALLBACK_MINUTES = 90
ESTIMATION_METHOD = "rule_based_v1"


def estimate_duration(assignment: Assignment) -> DurationEstimate:
    """Estimate a valid Assignment's workload without modifying it.

    Only assignment type affects v1 estimates. Missing or past deadlines do not
    change workload; scheduling eligibility belongs to the future scheduler.
    """
    assignment_type = assignment.assignment_type.strip().lower()

    if assignment_type in BASE_MINUTES_BY_TYPE:
        minutes = BASE_MINUTES_BY_TYPE[assignment_type]
        explanation = (
            f"Default for assignment type '{assignment_type}': "
            f"{minutes} active working minutes; provisional and not personalized."
        )
    else:
        minutes = FALLBACK_MINUTES
        explanation = (
            f"Unrecognized assignment type '{assignment_type}'; "
            f"using the general fallback of {minutes} active working minutes; "
            "provisional and not personalized."
        )

    return DurationEstimate(
        assignment_id=assignment.assignment_id,
        estimated_minutes=minutes,
        method=ESTIMATION_METHOD,
        explanation=explanation,
    )

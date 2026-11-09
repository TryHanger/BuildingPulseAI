"""Source-clock daily sufficiency for the research SAT pilot."""
from dataclasses import dataclass
from typing import Literal

POLICY_VERSION = "sat-daily-coverage@1.0.0"
Status = Literal["EVALUATED", "NOT_EVALUABLE", "INSUFFICIENT_COVERAGE"]


@dataclass(frozen=True)
class Coverage:
    status: Status
    reason: str | None
    continuous_minutes: int


def assess(minutes, running_minutes: int) -> Coverage:
    """Accept sorted, distinct source-clock minute-of-day values for one day."""
    longest = streak = 0
    previous = -2
    for minute in minutes:
        if not 0 <= minute < 1440 or minute <= previous:
            raise ValueError("Invalid source-clock minute order")
        streak = streak + 1 if minute == previous + 1 else 1
        longest = max(longest, streak)
        previous = minute
    usable = len(minutes)
    if not 0 <= usable <= running_minutes <= 1440:
        raise ValueError("Invalid RUNNING coverage denominator")
    if not usable:
        return Coverage("NOT_EVALUABLE", "NO_ELIGIBLE_MINUTES", longest)
    if usable < 120 or longest < 30 or usable * 5 < running_minutes * 4:
        return Coverage("INSUFFICIENT_COVERAGE", "DAILY_COVERAGE_FLOOR", longest)
    return Coverage("EVALUATED", None, longest)

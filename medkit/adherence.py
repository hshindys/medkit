from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from .store import HistoryEntry

# Below this the panel and the notifications start saying so.
ADHERENCE_THRESHOLD = 80

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_BLOCKS = " ▏▎▍▌▋▊▉█"


def _scheduled_and_taken(
    day: date,
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime,
) -> tuple[int, int]:
    """Doses due on `day` up to now, and how many of them were taken."""
    taken_by_day: dict[date, int] = {}
    for entry in history:
        if entry.action == "taken":
            taken_by_day[entry.ts.date()] = taken_by_day.get(entry.ts.date(), 0) + 1

    scheduled = 0
    taken_pool = taken_by_day.get(day, 0)
    taken = 0
    for medicine in medicines:
        if not getattr(medicine, "active", True):
            continue
        for clock in medicine.parsed_times():
            if datetime.combine(day, clock, now.tzinfo) > now:
                continue
            scheduled += 1
            if taken_pool > 0:
                taken_pool -= 1
                taken += 1
    return scheduled, taken


def pct(scheduled: int, taken: int) -> float | None:
    if scheduled <= 0:
        return None
    return round(100.0 * taken / scheduled, 1)


def day_stats(
    day: date,
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime,
) -> dict:
    scheduled, taken = _scheduled_and_taken(day, medicines, history, now)
    value = pct(scheduled, taken)
    return {
        "date": day.isoformat(),
        "weekday": WEEKDAYS[day.weekday()],
        "scheduled": scheduled,
        "taken": taken,
        "missed": max(0, scheduled - taken),
        "pct": value,
        "label": "—" if value is None else f"{round(value)}%",
        "color": _color(value),
    }


def _color(value: float | None) -> str:
    if value is None:
        return "#5a6068"
    if value >= ADHERENCE_THRESHOLD:
        return "#c3c8d0"
    if value >= 60:
        return "#9aa0a8"
    return "#f2f4f7"


def bar(value: float | None, width: int = 20) -> str:
    """A 20-cell text bar — the graph that survives a terminal and a log file."""
    if value is None:
        return " " * width
    filled = max(0, min(width, int(round(value / 100.0 * width))))
    return "█" * filled + " " * (width - filled)


def daily(
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime | None = None,
) -> dict:
    moment = now or datetime.now().astimezone()
    stats = day_stats(moment.date(), medicines, history, moment)
    return {
        **stats,
        "threshold": ADHERENCE_THRESHOLD,
        "below": stats["pct"] is not None and stats["pct"] < ADHERENCE_THRESHOLD,
        "text": f"today {stats['label']} ({stats['taken']}/{stats['scheduled']})",
    }


def weekly(
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime | None = None,
) -> dict:
    moment = now or datetime.now().astimezone()
    days = [
        day_stats(moment.date() - timedelta(days=offset), medicines, history, moment)
        for offset in range(6, -1, -1)
    ]
    scheduled = sum(day["scheduled"] for day in days)
    taken = sum(day["taken"] for day in days)
    overall = pct(scheduled, taken)
    graph = [
        f"{day['weekday']} {day['label']:>4} {bar(day['pct'])}"
        for day in days
    ]
    return {
        "days": days,
        "pct": overall,
        "scheduled": scheduled,
        "taken": taken,
        "missed": max(0, scheduled - taken),
        "label": "—" if overall is None else f"{round(overall)}%",
        "threshold": ADHERENCE_THRESHOLD,
        "below": overall is not None and overall < ADHERENCE_THRESHOLD,
        "graph": graph,
        "lines": ["7-day adherence"] + graph + [f"overall {round(overall or 0)}%"],
    }


def monthly(
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime | None = None,
    days: int = 30,
) -> dict:
    moment = now or datetime.now().astimezone()
    series = [
        day_stats(moment.date() - timedelta(days=offset), medicines, history, moment)
        for offset in range(days - 1, -1, -1)
    ]
    scheduled = sum(day["scheduled"] for day in series)
    taken = sum(day["taken"] for day in series)
    overall = pct(scheduled, taken)
    measured = [day for day in series if day["pct"] is not None]
    worst = min(measured, key=lambda day: day["pct"]) if measured else None
    best = max(measured, key=lambda day: day["pct"]) if measured else None
    below_days = [day for day in measured if day["pct"] < ADHERENCE_THRESHOLD]
    return {
        "days": days,
        "series": series,
        "pct": overall,
        "scheduled": scheduled,
        "taken": taken,
        "missed": max(0, scheduled - taken),
        "label": "—" if overall is None else f"{round(overall)}%",
        "threshold": ADHERENCE_THRESHOLD,
        "below": overall is not None and overall < ADHERENCE_THRESHOLD,
        "belowDays": len(below_days),
        "best": best,
        "worst": worst,
        "start": series[0]["date"] if series else "",
        "end": series[-1]["date"] if series else "",
    }


def overall_streak(
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime | None = None,
) -> dict:
    """Consecutive days on which every scheduled dose was taken."""
    moment = now or datetime.now().astimezone()

    def complete(day: date) -> bool:
        scheduled, taken = _scheduled_and_taken(day, medicines, history, moment)
        if scheduled == 0:
            return False
        skipped = any(
            entry.action == "skipped" and entry.ts.date() == day for entry in history
        )
        return not skipped and taken >= scheduled

    streak = 0
    cursor = moment.date()
    if complete(cursor):
        streak = 1
        cursor -= timedelta(days=1)
        while (moment.date() - cursor).days <= 400:
            if not complete(cursor):
                break
            streak += 1
            cursor -= timedelta(days=1)
    return {
        "days": streak,
        "active": streak > 0,
        "label": f"{streak} day streak" if streak else "no streak yet",
    }


def alert_state(
    medicines: Sequence,
    history: Sequence[HistoryEntry],
    now: datetime | None = None,
    threshold: int = ADHERENCE_THRESHOLD,
) -> dict:
    """Yesterday's score decides the daily nudge — today is still in progress."""
    moment = now or datetime.now().astimezone()
    yesterday = day_stats(moment.date() - timedelta(days=1), medicines, history, moment)
    value = yesterday["pct"]
    firing = value is not None and value < threshold
    return {
        "firing": firing,
        "pct": value,
        "label": yesterday["label"],
        "date": yesterday["date"],
        "threshold": threshold,
        "message": (
            f"Adherence yesterday was {yesterday['label']} — below your {threshold}% target."
            if firing
            else ""
        ),
    }

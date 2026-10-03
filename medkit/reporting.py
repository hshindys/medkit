from __future__ import annotations

from datetime import datetime
from typing import Sequence

from . import adherence, food, interactions, missed, pregnancy, refill, review, sideeffects
from .knowledge import load

# Reports are plain text first: they print, they paste into an email to a
# doctor, and they become a PDF with no formatting surprises in between.


def weekly(
    medicines: Sequence,
    history: Sequence,
    now: datetime | None = None,
) -> dict:
    moment = now or datetime.now().astimezone()
    book = load()
    active = [m for m in medicines if getattr(m, "active", True)]
    profile = pregnancy.check(active, None, book)  # profile-less: shows status only

    week = adherence.weekly(active, history, moment)
    effects = sideeffects.weekly_summary(moment)
    refills = refill.check(active, moment)
    findings = interactions.check(active, book)
    food_rows = food.alerts(active, book)
    missed_today = missed.missed_today(active, moment, history)

    lines = [f"Weekly health report — week ending {moment.strftime('%Y-%m-%d')}", ""]
    lines.append("## Adherence (7 days)")
    lines.extend("  " + row for row in week["graph"])
    lines.append(f"  overall {week['label']}  (threshold {week['threshold']}%)")
    if week["below"]:
        lines.append("  BELOW TARGET — a nudge will fire each morning until it recovers.")
    lines.append("")

    lines.append("## Side effects")
    lines.extend(effects["lines"])
    lines.append("")

    lines.append("## Supply")
    if refills["warnings"] or refills["out"]:
        for row in refills["out"]:
            lines.append(f"- OUT: {row['name']} (0 left)")
        for row in refills["warnings"]:
            lines.append(
                f"- {row['name']}: {row['stock']} left, about {row['daysLeft']} day(s) "
                f"({row['perDay']}/day) — refill before {row['runOut']}"
            )
    else:
        lines.append("- every counted medicine has more than "
                     f"{refill.REFILL_WARNING_DAYS} days of supply")
    lines.append("")

    lines.append("## Safety")
    if findings:
        for finding in findings:
            lines.append(f"- [{finding.severity}] {finding.a} + {finding.b}")
    else:
        lines.append("- no drug–drug interactions flagged")
    if food_rows:
        for row in food_rows:
            lines.append(f"- food: {row['medicine']} — {row['tip']}")
    if missed_today:
        lines.append(f"- {len(missed_today)} dose(s) missed today")
    lines.append("")
    lines.append("This is not medical advice.")
    lines.append(f"Local data only — knowledge snapshot {book.updated}.")

    return {
        "kind": "weekly",
        "end": moment.strftime("%Y-%m-%d"),
        "adherence": week,
        "sideEffects": effects,
        "refills": refills,
        "interactions": [f.to_dict() for f in findings],
        "food": food_rows,
        "missed": missed_today,
        "lines": lines,
    }


def monthly(
    medicines: Sequence,
    history: Sequence,
    now: datetime | None = None,
) -> dict:
    moment = now or datetime.now().astimezone()
    book = load()
    active = [m for m in medicines if getattr(m, "active", True)]

    month = adherence.monthly(active, history, moment)
    streak = adherence.overall_streak(active, history, moment)
    effects = sideeffects.since(30, moment)
    repeats = sideeffects.repeat_alerts()
    refills = refill.check(active, moment)
    findings = interactions.check(active, book)
    state = review.status(moment)

    lines = [f"Monthly health report — {month['start']} to {month['end']}", ""]
    lines.append("## Adherence (30 days)")
    lines.append(f"  {month['label']} of scheduled doses taken")
    lines.append(f"  taken {month['taken']} of {month['scheduled']}  ·  missed {month['missed']}")
    lines.append(f"  days below {month['threshold']}%: {month['belowDays']}")
    if month["best"]:
        lines.append(f"  best day: {month['best']['date']} {month['best']['label']}")
    if month["worst"]:
        lines.append(f"  worst day: {month['worst']['date']} {month['worst']['label']}")
    lines.append(f"  streak: {streak['label']}")
    lines.append("")

    lines.append("## Side effects (30 days)")
    lines.append(f"  {len(effects)} reported")
    if repeats:
        for row in repeats:
            lines.append(f"  REPEAT: {row['effect']} with {row['medicine']} — {row['count']} times")
    else:
        lines.append("  no effect reported 3+ times")
    lines.append("")

    lines.append("## Supply")
    for row in refills["out"]:
        lines.append(f"- OUT: {row['name']}")
    for row in refills["warnings"]:
        lines.append(f"- {row['name']}: {row['stock']} left (~{row['daysLeft']} days)")
    if not refills["out"] and not refills["warnings"]:
        lines.append("- nothing within the refill window")
    lines.append("")

    lines.append("## Safety")
    lines.append(f"- {len(findings)} interaction(s) flagged")
    for finding in findings[:10]:
        lines.append(f"    [{finding.severity}] {finding.a} + {finding.b}")
    lines.append("")

    lines.append("## Review")
    lines.append(f"- last: {state['lastLabel']}  ·  next: {state['nextLabel']}"
                 + ("  ·  DUE NOW" if state["due"] else ""))
    lines.append("")
    lines.append("This is not medical advice.")

    return {
        "kind": "monthly",
        "start": month["start"],
        "end": month["end"],
        "adherence": month,
        "streak": streak,
        "sideEffects": {"count": len(effects), "rows": effects, "repeats": repeats},
        "refills": refills,
        "interactions": [f.to_dict() for f in findings],
        "review": state,
        "lines": lines,
    }


def render(kind: str, medicines: Sequence, history: Sequence, now: datetime | None = None) -> dict:
    if kind == "monthly":
        return monthly(medicines, history, now)
    return weekly(medicines, history, now)

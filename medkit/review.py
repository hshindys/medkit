from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Sequence

from . import adherence, interactions, paths, sideeffects, store
from .knowledge import Knowledge, load

# "A comprehensive review every 3 months" — measured in months, not a fixed
# 90 days, so February does not quietly shorten the interval.
REVIEW_INTERVAL_MONTHS = 3

DISCLAIMER = "This is not medical advice. Bring this list to your doctor — it is a record, not a prescription."


def add_months(day: datetime, months: int) -> datetime:
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last))


def status(now: datetime | None = None) -> dict:
    moment = now or datetime.now().astimezone()
    review = store.load_review()
    last_text = str(review.get("last_review", ""))
    next_text = str(review.get("next_review", ""))

    if not next_text and last_text:
        try:
            next_text = add_months(datetime.fromisoformat(last_text), REVIEW_INTERVAL_MONTHS).isoformat(
                timespec="seconds"
            )
        except ValueError:
            next_text = ""

    due = False
    days_left = None
    if next_text:
        try:
            target = datetime.fromisoformat(next_text)
            due = moment >= target
            days_left = (target.date() - moment.date()).days
        except ValueError:
            due = False
    elif not last_text:
        # Never reviewed: due the moment the list exists.
        due = True

    return {
        "last": last_text,
        "lastLabel": _label(last_text),
        "next": next_text,
        "nextLabel": _label(next_text),
        "due": due,
        "daysLeft": days_left,
        "intervalMonths": REVIEW_INTERVAL_MONTHS,
        "history": review.get("history", []),
        "never": not last_text,
    }


def _label(stamp: str) -> str:
    if not stamp:
        return "never"
    try:
        return datetime.fromisoformat(stamp).strftime("%Y-%m-%d")
    except ValueError:
        return str(stamp)


def mark_reviewed(now: datetime | None = None, exported: str = "") -> dict:
    moment = now or datetime.now().astimezone()
    review = store.load_review()
    review["last_review"] = moment.isoformat(timespec="seconds")
    review["next_review"] = add_months(moment, REVIEW_INTERVAL_MONTHS).isoformat(
        timespec="seconds"
    )
    history = review.get("history") or []
    history.append(
        {
            "date": moment.strftime("%Y-%m-%d"),
            "exported": exported,
        }
    )
    review["history"] = history[-24:]
    store.save_review(review)
    return review


def duplicates(
    medicines: Sequence,
    knowledge: Knowledge | None = None,
) -> list[dict]:
    """Two boxes on the shelf that do the same job — or worse, the same job twice."""
    book = knowledge or load()
    spec = book.raw.get("duplicate") or {}
    pair_severity = spec.get("same_class_pairs") or {}
    generic_severity = str(spec.get("same_generic", "severe"))

    active = [m for m in medicines if getattr(m, "active", True)]
    resolved = [(m, book.resolve(m.name, getattr(m, "generic", ""))) for m in active]

    out: list[dict] = []
    seen: set[tuple] = set()

    # The same molecule under two names.
    by_generic: dict[str, list] = {}
    for medicine, item in resolved:
        if item.generic:
            by_generic.setdefault(item.generic, []).append(medicine.name)
    for generic, names in by_generic.items():
        if len(names) < 2:
            continue
        key = ("generic", tuple(sorted(names)))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "severity": generic_severity,
                "severityLabel": generic_severity.title(),
                "kind": "duplicate ingredient",
                "concept": generic,
                "names": sorted(names),
                "text": f"{', '.join(sorted(names))} all contain {generic} — one dose too many.",
            }
        )

    # Two medicines from the same class where two is never better than one.
    for class_id, severity in pair_severity.items():
        holders = [item.name for _, item in resolved if class_id in item.concepts]
        if len(holders) < 2:
            continue
        key = ("class", class_id, tuple(sorted(holders)))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "severity": str(severity),
                "severityLabel": str(severity).title(),
                "kind": "therapeutic duplication",
                "concept": class_id,
                "conceptLabel": book.class_label(class_id),
                "names": sorted(holders),
                "text": (
                    f"{', '.join(sorted(holders))} are both {book.class_label(class_id)}s — "
                    "two medicines doing one job usually means extra side effects, not extra benefit."
                ),
            }
        )

    order = {"severe": 0, "moderate": 1, "mild": 2}
    out.sort(key=lambda row: (order.get(row["severity"], 3), row["text"]))
    return out


def report(
    medicines: Sequence,
    history: Sequence,
    now: datetime | None = None,
    knowledge: Knowledge | None = None,
    profile: dict | None = None,
) -> dict:
    """The whole therapy in one page: doses, duplicates, safety, scores."""
    book = knowledge or load()
    moment = now or datetime.now().astimezone()
    active = [m for m in medicines if getattr(m, "active", True)]

    rows = []
    for medicine in active:
        resolved = book.resolve(medicine.name, getattr(medicine, "generic", ""))
        rows.append(
            {
                "name": medicine.name,
                "dose": medicine.dose or "—",
                "times": ", ".join(medicine.times) or "as needed",
                "stock": medicine.stock,
                "category": medicine.category,
                "days": medicine.days,
                "notes": medicine.notes,
                "generic": resolved.generic,
                "classes": list(resolved.classes),
                "classLabels": [book.class_label(c) for c in resolved.classes],
                "active": medicine.active,
            }
        )

    findings = interactions.check(active, book)
    dupes = duplicates(active, book)
    adherence_month = adherence.monthly(active, history, moment)
    repeats = sideeffects.repeat_alerts()
    state = status(moment)

    return {
        "generated": moment.strftime("%Y-%m-%d %H:%M"),
        "medicines": rows,
        "count": len(rows),
        "duplicates": dupes,
        "duplicateCount": len(dupes),
        "interactions": [finding.to_dict() for finding in findings],
        "interactionCount": len(findings),
        "adherence": adherence_month,
        "streak": adherence.overall_streak(active, history, moment),
        "sideEffects": repeats,
        "review": state,
        "profile": profile if profile is not None else store.load_profile(),
        "sources": book.sources,
        "disclaimer": DISCLAIMER,
    }


def render_lines(data: dict) -> list[str]:
    lines: list[str] = []
    lines.append(f"Medication therapy review — {data['generated']}")
    lines.append(f"Medicines on the list: {data['count']}")
    lines.append("")
    lines.append("## Medicines")
    for row in data["medicines"]:
        flags = []
        if row["category"] == "emergency":
            flags.append("emergency")
        if row["days"]:
            flags.append(f"{row['days']}-day course")
        if row["stock"] is not None:
            flags.append(f"{row['stock']} left")
        suffix = f"  ({'; '.join(flags)})" if flags else ""
        lines.append(f"- {row['name']} — {row['dose']} — {row['times']}{suffix}")
        if row["generic"]:
            lines.append(f"    generic: {row['generic']}")
        if row["notes"]:
            lines.append(f"    note: {row['notes']}")

    lines.append("")
    lines.append("## Duplicates")
    if data["duplicates"]:
        for row in data["duplicates"]:
            lines.append(f"- [{row['severity']}] {row['text']}")
    else:
        lines.append("- none found")

    lines.append("")
    lines.append("## Interactions")
    if data["interactions"]:
        for row in data["interactions"]:
            lines.append(f"- [{row['severity']}] {row['a']} + {row['b']}: {row['effect']}")
    else:
        lines.append("- none found")

    lines.append("")
    lines.append("## Adherence (last 30 days)")
    month = data["adherence"]
    lines.append(f"- {month['label']} of scheduled doses taken ({month['taken']}/{month['scheduled']})")
    lines.append(f"- {month['belowDays']} day(s) below {month['threshold']}%")
    lines.append(f"- current streak: {data['streak']['days']} day(s)")

    if data["sideEffects"]:
        lines.append("")
        lines.append("## Repeated side effects")
        for row in data["sideEffects"]:
            lines.append(
                f"- {row['effect']} with {row['medicine']}: reported {row['count']} times "
                f"(worst: {row['worst']}, last {row['last']})"
            )

    lines.append("")
    lines.append("## Review schedule")
    review = data["review"]
    lines.append(f"- last review: {review['lastLabel']}")
    lines.append(f"- next review: {review['nextLabel']}")

    lines.append("")
    lines.append("Sources: " + "; ".join(data["sources"]))
    lines.append("This is not medical advice.")
    return lines


def export_pdf(data: dict) -> paths.Path:
    from .pdf import write_text_pdf

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d")
    target = paths.reports_dir() / f"therapy-review-{stamp}.pdf"
    write_text_pdf(target, "Medication therapy review", render_lines(data))
    return target


def full_review(
    medicines: Sequence,
    history: Sequence,
    now: datetime | None = None,
    knowledge: Knowledge | None = None,
) -> tuple[dict, paths.Path]:
    data = report(medicines, history, now, knowledge)
    path = export_pdf(data)
    mark_reviewed(now, exported=str(path))
    return data, path

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from . import engine
from .knowledge import Knowledge, load

# A dose is only "missed" once it is past its scheduled time plus this grace
# — a few minutes of being busy is not a missed dose.
MISSED_GRACE = timedelta(minutes=30)

# Two or more in one day means the day has slipped, not a single dose.
MULTI_MISS_THRESHOLD = 2


def protocol_for(medicine, knowledge: Knowledge | None = None) -> dict:
    """What to do about a missed dose of this medicine.

    The instruction is derived from the drug class so the answer is specific
    ("never double, watch for bleeding") rather than a generic shrug; a
    personal note written on the medicine always wins.
    """
    book = knowledge or load()
    spec = book.raw.get("missed_dose") or {}
    personal = str(getattr(medicine, "missed_dose_note", "") or "").strip()
    if personal:
        return {
            "name": medicine.name,
            "source": "personal",
            "sourceLabel": "your own note",
            "text": personal,
        }

    resolved = book.resolve(medicine.name, getattr(medicine, "generic", ""))
    by_drug = spec.get("by_drug") or {}
    if resolved.generic and resolved.generic in by_drug:
        return {
            "name": medicine.name,
            "source": "drug",
            "sourceLabel": resolved.generic,
            "text": str(by_drug[resolved.generic]),
        }

    by_class = spec.get("by_class") or {}
    # The most specific class wins: an ACE inhibitor has its own line, but a
    # beta blocker shares the standard "skip, never double" text.
    for class_id in sorted(resolved.classes):
        if class_id in by_class:
            return {
                "name": medicine.name,
                "source": "class",
                "sourceLabel": book.class_label(class_id),
                "text": str(by_class[class_id]),
            }

    if getattr(medicine, "category", "normal") == "emergency":
        return {
            "name": medicine.name,
            "source": "as-needed",
            "sourceLabel": "as-needed medicine",
            "text": str(spec.get("as_needed", spec.get("default", ""))),
        }

    return {
        "name": medicine.name,
        "source": "default",
        "sourceLabel": "standard rule",
        "text": str(spec.get("default", "")),
    }


def all_protocols(medicines: Sequence, knowledge: Knowledge | None = None) -> list[dict]:
    book = knowledge or load()
    return [
        protocol_for(medicine, book)
        for medicine in medicines
        if getattr(medicine, "active", True)
    ]


def missed_today(
    medicines: Sequence,
    now: datetime,
    history: Sequence,
) -> list[dict]:
    """Doses whose time has passed today and that were neither taken nor skipped."""
    status = engine.evaluate(list(medicines), now, history, wizard_done=True)
    moment = now
    out: list[dict] = []
    for dose in status.doses:
        if dose.taken:
            continue
        if dose.when + MISSED_GRACE > moment:
            continue
        skipped = any(
            entry.action == "skipped"
            and entry.medicine == dose.medicine.name
            and entry.ts.date() == now.date()
            for entry in history
        )
        if skipped:
            continue
        out.append(
            {
                "name": dose.medicine.name,
                "dose": dose.medicine.dose,
                "clock": dose.clock,
                "minutesLate": int((moment - dose.when).total_seconds() // 60),
                "tab": dose.tab,
            }
        )
    out.sort(key=lambda item: item["minutesLate"], reverse=True)
    return out


def summary(
    medicines: Sequence,
    now: datetime,
    history: Sequence,
    knowledge: Knowledge | None = None,
) -> dict:
    book = knowledge or load()
    missed = missed_today(medicines, now, history)
    per_medicine = all_protocols(medicines, book)
    by_name = {row["name"]: row for row in per_medicine}
    return {
        "missed": missed,
        "count": len(missed),
        "alert": len(missed) >= MULTI_MISS_THRESHOLD,
        "threshold": MULTI_MISS_THRESHOLD,
        "protocols": per_medicine,
        "forMissed": [
            {**item, **by_name.get(item["name"], {})} for item in missed
        ],
        "disclaimer": book.disclaimer,
    }

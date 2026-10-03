from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Sequence

from . import store

# "The same side effect three times" is the point at which a pattern stops
# being coincidence.
REPEAT_THRESHOLD = 3

SEVERITIES = ("mild", "moderate", "severe")
SEVERITY_LEVEL = {"mild": 1, "moderate": 2, "severe": 3}
SEVERITY_COLOR = {"mild": "#38bdf8", "moderate": "#f59e0b", "severe": "#ef4444"}

_NON_WORD = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")


class SideEffectError(Exception):
    pass


def normalize_severity(value) -> str:
    if isinstance(value, int):
        return SEVERITIES[max(1, min(3, value)) - 1]
    text = str(value or "").strip().lower()
    if text in SEVERITIES:
        return text
    if text in ("1", "2", "3"):
        return SEVERITIES[int(text) - 1]
    if text in ("low", "light", "slight", "minor"):
        return "mild"
    if text in ("med", "medium", "middle"):
        return "moderate"
    if text in ("high", "bad", "strong", "serious"):
        return "severe"
    raise SideEffectError(f"severity must be one of {', '.join(SEVERITIES)} (or 1-3)")


def normalize_effect(text: str) -> str:
    """Fold wording together so 'Headache' and 'headache!' count as one."""
    cleaned = _NON_WORD.sub(" ", str(text or "").lower())
    return _SPACES.sub(" ", cleaned).strip()


def log(
    medicine_name: str,
    effect: str,
    severity="mild",
    dose: str = "",
    notes: str = "",
    now: datetime | None = None,
    allow_unknown: bool = False,
) -> dict:
    """Record one side effect against the medicine and dose it came from."""
    name = str(medicine_name or "").strip()
    text = str(effect or "").strip()
    if not name:
        raise SideEffectError("medicine is required")
    if not text:
        raise SideEffectError("describe the side effect")

    from .store import load_medicines

    document = load_medicines()
    medicine = document.by_name(name)
    if medicine is None and not allow_unknown:
        raise SideEffectError(f"unknown medicine: {name}")
    if medicine is not None and not dose:
        dose = medicine.dose

    level = normalize_severity(severity)
    moment = now or datetime.now().astimezone()
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": moment.isoformat(timespec="seconds"),
        "date": moment.strftime("%Y-%m-%d"),
        "medicine": name,
        "dose": str(dose or ""),
        "effect": text,
        "effectKey": normalize_effect(text),
        "severity": level,
        "severityLevel": SEVERITY_LEVEL[level],
        "severityColor": SEVERITY_COLOR[level],
        "notes": str(notes or ""),
    }
    store.append_sideeffect(record)
    return record


def all_records() -> list[dict]:
    return store.read_sideeffects()


def since(days: int, now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now().astimezone()
    cutoff = (moment - timedelta(days=days)).date()
    rows = []
    for row in all_records():
        try:
            day = datetime.fromisoformat(str(row.get("ts", ""))).date()
        except ValueError:
            continue
        if day >= cutoff:
            rows.append(row)
    return rows


def repeat_alerts(threshold: int = REPEAT_THRESHOLD) -> list[dict]:
    """Every medicine+effect pair that has now been reported `threshold` times."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in all_records():
        key = (str(row.get("medicine", "")), str(row.get("effectKey", "")))
        grouped.setdefault(key, []).append(row)

    out: list[dict] = []
    for (medicine, effect_key), rows in grouped.items():
        if len(rows) < threshold:
            continue
        rows.sort(key=lambda row: str(row.get("ts", "")))
        severities = [SEVERITY_LEVEL.get(str(r.get("severity", "mild")), 1) for r in rows]
        out.append(
            {
                "medicine": medicine,
                "effect": str(rows[-1].get("effect", effect_key)),
                "effectKey": effect_key,
                "count": len(rows),
                "threshold": threshold,
                "first": str(rows[0].get("date", "")),
                "last": str(rows[-1].get("date", "")),
                "dose": str(rows[-1].get("dose", "")),
                "worst": SEVERITIES[max(severities) - 1],
                "worstColor": SEVERITY_COLOR[SEVERITIES[max(severities) - 1]],
                "dates": [str(r.get("date", "")) for r in rows],
            }
        )
    out.sort(key=lambda row: (-row["count"], row["medicine"]))
    return out


def weekly_summary(now: datetime | None = None) -> dict:
    """The last seven days: what was reported, how badly, and what repeats."""
    moment = now or datetime.now().astimezone()
    rows = since(7, moment)
    by_medicine: dict[str, int] = {}
    by_severity = {name: 0 for name in SEVERITIES}
    for row in rows:
        medicine = str(row.get("medicine", ""))
        by_medicine[medicine] = by_medicine.get(medicine, 0) + 1
        severity = str(row.get("severity", "mild"))
        by_severity[severity] = by_severity.get(severity, 0) + 1

    repeats = repeat_alerts()
    lines = [
        f"{len(rows)} side effect(s) reported in the last 7 days"
        if rows
        else "No side effects reported in the last 7 days"
    ]
    for medicine, count in sorted(by_medicine.items(), key=lambda item: -item[1]):
        lines.append(f"  {medicine}: {count}")
    for repeat in repeats:
        lines.append(
            f"  REPEAT ({repeat['count']}x): {repeat['effect']} with {repeat['medicine']}"
        )
    lines.append("This is not medical advice — mention repeats to your doctor or pharmacist.")

    return {
        "days": 7,
        "total": len(rows),
        "rows": rows,
        "byMedicine": by_medicine,
        "bySeverity": by_severity,
        "repeats": repeats,
        "lines": lines,
        "end": moment.strftime("%Y-%m-%d"),
        "start": (moment - timedelta(days=7)).strftime("%Y-%m-%d"),
    }

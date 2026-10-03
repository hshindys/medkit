from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

# The requirement is explicit: warn three days before the box runs out.
REFILL_WARNING_DAYS = 3


def doses_per_day(medicine) -> int:
    return len(getattr(medicine, "times", []) or [])


def days_left(medicine) -> float | None:
    """Whole days of supply left, or None when the count is unknown."""
    stock = getattr(medicine, "stock", None)
    per_day = doses_per_day(medicine)
    if stock is None or per_day <= 0:
        return None
    return float(stock) / per_day


def projected_run_out(medicine, today: datetime) -> str:
    left = days_left(medicine)
    if left is None:
        return ""
    return (today + timedelta(days=int(left))).strftime("%Y-%m-%d")


def check(
    medicines: Sequence,
    now: datetime | None = None,
    profile: dict | None = None,
) -> dict:
    """Every active medicine with a known count, soonest to run out first."""
    moment = now or datetime.now().astimezone()
    pharmacy = (profile or {}).get("pharmacy") or {}
    rows: list[dict] = []
    for medicine in medicines:
        if not getattr(medicine, "active", True):
            continue
        stock = getattr(medicine, "stock", None)
        if stock is None:
            continue
        left = days_left(medicine)
        per_day = doses_per_day(medicine)
        soon = left is not None and left <= REFILL_WARNING_DAYS
        rows.append(
            {
                "name": medicine.name,
                "dose": medicine.dose,
                "stock": stock,
                "refillAt": medicine.refill_at,
                "perDay": per_day,
                "daysLeft": None if left is None else round(left, 1),
                "daysLeftInt": None if left is None else int(left),
                "runOut": projected_run_out(medicine, moment),
                "low": bool(getattr(medicine, "is_low", lambda: False)()),
                "out": bool(getattr(medicine, "is_out", lambda: False)()),
                "warn": soon,
                "category": medicine.category,
                "pharmacyName": str(pharmacy.get("name", "")),
                "pharmacyPhone": str(pharmacy.get("phone", "")),
            }
        )
    rows.sort(
        key=lambda row: (
            row["daysLeft"] is None,
            row["daysLeft"] if row["daysLeft"] is not None else 9e9,
            row["name"],
        )
    )
    warnings = [row for row in rows if row["warn"] and not row["out"]]
    out_of_stock = [row for row in rows if row["out"]]
    unknown = [row for row in rows if row["daysLeft"] is None]
    return {
        "medicines": rows,
        "warnings": warnings,
        "out": out_of_stock,
        "unknown": unknown,
        "warningDays": REFILL_WARNING_DAYS,
        "count": len(rows),
        "countWarn": len(warnings) + len(out_of_stock),
        "pharmacy": dict(pharmacy),
        "next": rows[0] if rows else None,
    }


def call_uri(phone: str) -> str:
    """A tel: URI the shell can hand straight to the dialler — no network."""
    cleaned = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch in "+")
    return f"tel:{cleaned}" if cleaned else ""

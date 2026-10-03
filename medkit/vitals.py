from __future__ import annotations

import csv
import re
import uuid
from datetime import datetime, timedelta
from typing import Sequence

from . import store

# Readings are matched to a dose inside this window. Blood pressure answers
# to the dose that caused it over hours, not minutes, so the window is wide.
CORRELATION_WINDOW_HOURS = 4

KINDS = {
    "bp": {"label": "Blood pressure", "unit": "mmHg", "color": "#ef4444", "two": True},
    "glucose": {"label": "Blood sugar", "unit": "mg/dL", "color": "#f59e0b", "two": False},
    "sugar": {"label": "Blood sugar", "unit": "mg/dL", "color": "#f59e0b", "two": False},
    "pulse": {"label": "Pulse", "unit": "bpm", "color": "#38bdf8", "two": False},
    "weight": {"label": "Weight", "unit": "kg", "color": "#a78bfa", "two": False},
    "spo2": {"label": "Oxygen saturation", "unit": "%", "color": "#22d3ee", "two": False},
    "temp": {"label": "Temperature", "unit": "°C", "color": "#f97316", "two": False},
}

_ALIASES = {
    "blood pressure": "bp",
    "bp_sys": "bp",
    "systolic": "bp",
    "diastolic": "bp",
    "dia": "bp",
    "sys": "bp",
    "blood sugar": "glucose",
    "blood glucose": "glucose",
    "glu": "glucose",
    "hr": "pulse",
    "heart rate": "pulse",
    "bpm": "pulse",
    "o2": "spo2",
    "oxygen": "spo2",
    "temperature": "temp",
    "weight_kg": "weight",
}


class VitalError(Exception):
    pass


def normalize_kind(value: str) -> str:
    text = str(value or "").strip().lower()
    text = _ALIASES.get(text, text)
    if text not in KINDS:
        raise VitalError(f"unknown reading type: {value} (try {', '.join(sorted(KINDS))})")
    return text


def _unit_for(kind: str, value: float) -> str:
    if kind == "glucose":
        # A sugar of 6.2 is mmol/L; 112 is mg/dL. Guessing beats demanding a
        # unit the caller will get wrong half the time.
        return "mmol/L" if 0 < value < 30 else "mg/dL"
    if kind == "temp" and value < 45:
        return "°C"
    return KINDS[kind]["unit"]


def parse_value(kind: str, raw) -> tuple[float, float | None]:
    """Accepts '120/80', '120 / 80', '112' and '6.2'."""
    text = str(raw or "").strip()
    if not text:
        raise VitalError("a reading is required")
    parts = re.split(r"[\/]", text)
    try:
        primary = float(parts[0].replace(",", "."))
    except ValueError:
        raise VitalError(f"not a number: {raw}") from None
    secondary = None
    if kind == "bp":
        if len(parts) < 2:
            raise VitalError("blood pressure needs both numbers, e.g. 120/80")
        try:
            secondary = float(parts[1].replace(",", "."))
        except ValueError:
            raise VitalError(f"not a number: {raw}") from None
    return primary, secondary


def add(
    kind: str,
    raw_value,
    now: datetime | None = None,
    source: str = "manual",
    note: str = "",
    ts: datetime | None = None,
) -> dict:
    normalized = normalize_kind(kind)
    value, secondary = parse_value(normalized, raw_value)
    moment = ts or now or datetime.now().astimezone()
    if moment.tzinfo is None:
        moment = moment.astimezone()
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": moment.isoformat(timespec="seconds"),
        "date": moment.strftime("%Y-%m-%d"),
        "clock": moment.strftime("%H:%M"),
        "kind": normalized,
        "label": KINDS[normalized]["label"],
        "value": value,
        "value2": secondary,
        "unit": _unit_for(normalized, value),
        "source": str(source or "manual"),
        "note": str(note or ""),
        "color": KINDS[normalized]["color"],
    }
    store.append_vital(record)
    return record


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%Y")


def _parse_date(text: str) -> datetime | None:
    text = str(text or "").strip()
    if not text:
        return None
    # ISO first: "2026-10-03 07:45" or "2026-10-03T07:45:00"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            continue
    return None


def _detect_kind(header: str) -> str:
    lowered = header.strip().lower()
    if "sys" in lowered or "dias" in lowered or "blood pressure" in lowered:
        return "bp"
    if "glucose" in lowered or "sugar" in lowered:
        return "glucose"
    if "pulse" in lowered or "heart" in lowered:
        return "pulse"
    if "weight" in lowered or "kg" in lowered:
        return "weight"
    if "spo2" in lowered or "oxygen" in lowered or "satur" in lowered:
        return "spo2"
    if "temp" in lowered:
        return "temp"
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    return ""


def import_rows(rows: Sequence[dict]) -> dict:
    """Import generic health-app exports: one row per reading.

    Recognised columns (English, case-insensitive): date / time, systolic +
    diastolic (or a blood pressure column containing 120/80), glucose /
    blood sugar, pulse / heart rate, weight, spo2, temperature.
    """
    imported = 0
    skipped = 0
    for row in rows:
        lowered = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
        moment = None
        for key in ("date", "datetime", "timestamp", "time", "day", "reading date"):
            if key in lowered:
                moment = _parse_date(str(lowered[key]))
                if moment:
                    break
        if moment is None:
            skipped += 1
            continue

        pair = None
        for key in ("blood pressure", "bp", "systolic/diastolic"):
            if key in lowered and str(lowered[key]).strip():
                pair = ("bp", str(lowered[key]))
                break
        if pair is None and ("systolic" in lowered or "sys" in lowered):
            sys_v = str(lowered.get("systolic", lowered.get("sys", ""))).strip()
            dia_v = str(lowered.get("diastolic", lowered.get("dias", lowered.get("dia", "")))).strip()
            if sys_v and dia_v:
                pair = ("bp", f"{sys_v}/{dia_v}")

        if pair is None:
            for key, value in lowered.items():
                if value is None or not str(value).strip():
                    continue
                detected = _detect_kind(key)
                if detected and detected != "bp":
                    pair = (detected, str(value))
                    break

        if pair is None:
            skipped += 1
            continue

        try:
            add(pair[0], pair[1], ts=moment, source="import")
            imported += 1
        except VitalError:
            skipped += 1
    return {"imported": imported, "skipped": skipped}


def import_csv(path: str) -> dict:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise VitalError(f"no rows in {path}")
    result = import_rows(rows)
    result["path"] = str(path)
    return result


def readings(days: int = 30, now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now().astimezone()
    cutoff = (moment - timedelta(days=days)).date()
    out = []
    for row in store.read_vitals():
        try:
            day = datetime.fromisoformat(str(row.get("ts", ""))).date()
        except ValueError:
            continue
        if day >= cutoff:
            out.append(row)
    out.sort(key=lambda row: str(row.get("ts", "")))
    return out


def correlate(
    medicines: Sequence,
    history: Sequence,
    days: int = 30,
    now: datetime | None = None,
    window_hours: int = CORRELATION_WINDOW_HOURS,
) -> dict:
    """Attach every reading to the doses taken around it.

    A reading gets the nearest dose of each medicine within the window, with
    the signed gap in minutes — negative means the dose came after the
    reading, which is exactly what makes a chart readable.
    """
    moment = now or datetime.now().astimezone()
    window = timedelta(hours=window_hours)
    since = moment - timedelta(days=days)

    taken: list[tuple[datetime, str]] = []
    for entry in history:
        if entry.action == "taken" and entry.ts >= since:
            taken.append((entry.ts, entry.medicine))

    rows = readings(days, moment)
    per_reading: list[dict] = []
    for row in rows:
        try:
            stamp = datetime.fromisoformat(str(row["ts"]))
        except (ValueError, KeyError):
            continue
        nearby = []
        for taken_at, name in taken:
            delta = int((stamp - taken_at).total_seconds() // 60)
            if abs(delta) <= window_hours * 60:
                nearby.append({"medicine": name, "minutes": delta})
        nearby.sort(key=lambda item: abs(item["minutes"]))
        per_reading.append({**row, "doses": nearby})

    # Group by medicine so the chart can plot one line per drug.
    by_medicine: dict[str, list[dict]] = {}
    for row in per_reading:
        for dose in row["doses"]:
            by_medicine.setdefault(dose["medicine"], []).append(
                {
                    "ts": row["ts"],
                    "date": row["date"],
                    "clock": row["clock"],
                    "kind": row["kind"],
                    "value": row["value"],
                    "value2": row.get("value2"),
                    "unit": row.get("unit"),
                    "minutesFromDose": dose["minutes"],
                }
            )
    for name in by_medicine:
        by_medicine[name].sort(key=lambda item: item["ts"])

    linked = [row for row in per_reading if row["doses"]]
    return {
        "days": days,
        "windowHours": window_hours,
        "readings": per_reading,
        "linked": len(linked),
        "unlinked": len(per_reading) - len(linked),
        "byMedicine": by_medicine,
        "medicines": sorted(by_medicine),
    }


def chart(days: int = 14, now: datetime | None = None) -> dict:
    """Series the panel can draw: one array per reading type."""
    rows = readings(days, now)
    series: dict[str, list[dict]] = {}
    for row in rows:
        series.setdefault(str(row.get("kind", "")), []).append(
            {
                "ts": row.get("ts", ""),
                "date": row.get("date", ""),
                "clock": row.get("clock", ""),
                "value": row.get("value"),
                "value2": row.get("value2"),
                "unit": row.get("unit", ""),
                "doses": [],
            }
        )
    return {
        "days": days,
        "series": {kind: values for kind, values in series.items() if values},
        "count": len(rows),
        "kinds": {kind: KINDS[kind] for kind in KINDS},
    }


def latest(kind: str, now: datetime | None = None) -> dict | None:
    normalized = normalize_kind(kind)
    rows = [row for row in readings(90, now) if row.get("kind") == normalized]
    return rows[-1] if rows else None


def summarize(days: int = 7, now: datetime | None = None) -> dict:
    rows = readings(days, now)
    summary: dict[str, dict] = {}
    for row in rows:
        kind = str(row.get("kind", ""))
        bucket = summary.setdefault(kind, {"kind": kind, "count": 0, "values": [], "values2": []})
        bucket["count"] += 1
        bucket["values"].append(float(row.get("value") or 0))
        if row.get("value2") is not None:
            bucket["values2"].append(float(row.get("value2")))
    out = []
    for kind, bucket in summary.items():
        values = bucket["values"]
        label = KINDS.get(kind, {}).get("label", kind)
        unit = KINDS.get(kind, {}).get("unit", "")
        if kind == "glucose" and values and values[-1] < 30:
            unit = "mmol/L"
        row = {
            "kind": kind,
            "label": label,
            "count": bucket["count"],
            "unit": unit,
            "latest": values[-1] if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": round(sum(values) / len(values), 1) if values else None,
        }
        if kind == "bp" and bucket["values2"]:
            row["latest2"] = bucket["values2"][-1]
            row["avg2"] = round(sum(bucket["values2"]) / len(bucket["values2"]), 1)
        out.append(row)
    return {"days": days, "count": len(rows), "types": out}

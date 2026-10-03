from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import paths, store

DISCLAIMER = "This is not medical advice — it is a record of what you told MedKit."


def call_uri(phone: str) -> str:
    """tel: URI — dialling needs no network and no app store."""
    cleaned = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch in "+")
    return f"tel:{cleaned}" if cleaned else ""


def profile() -> dict:
    return store.load_profile()


def save(updates: dict) -> dict:
    """Merge a partial update into the card and write it back."""
    current = store.load_profile()
    for key, value in updates.items():
        if isinstance(current.get(key), dict) and isinstance(value, dict):
            merged = dict(current[key])
            merged.update(value)
            current[key] = merged
        else:
            current[key] = value
    store.save_profile(current)
    return current


def set_field(key: str, value: str) -> dict:
    """Flat setter for the CLI: `--profile-set allergies "penicillin, aspirin"`."""
    current = store.load_profile()
    if key in ("allergies", "conditions"):
        items = [part.strip() for part in value.split(",") if part.strip()]
        current[key] = items
    elif key in ("emergency_contact", "doctor", "pharmacy"):
        # "Name | +20 100 000 0000" (or just the phone number).
        if "|" in value:
            name, _, phone = value.partition("|")
            current[key] = {"name": name.strip(), "phone": phone.strip()}
        elif value.strip().startswith("+") or value.strip().replace(" ", "").isdigit():
            current[key] = {**current.get(key, {}), "phone": value.strip()}
        else:
            current[key] = {**current.get(key, {}), "name": value.strip()}
    else:
        current[key] = value
    store.save_profile(current)
    return current


def card(medicines: Sequence | None = None) -> dict:
    """Everything a first responder needs, on one screen, offline."""
    data = profile()
    if medicines is None:
        medicines = store.load_medicines().active()
    active = [m for m in medicines if getattr(m, "active", True)]

    rows = []
    for medicine in active:
        rows.append(
            {
                "name": medicine.name,
                "dose": medicine.dose,
                "times": ", ".join(medicine.times),
                "note": medicine.notes,
                "emergency": medicine.is_emergency,
            }
        )

    contact = data.get("emergency_contact") or {}
    doctor = data.get("doctor") or {}
    allergies = [str(item) for item in data.get("allergies", [])]
    conditions = [str(item) for item in data.get("conditions", [])]

    return {
        "name": str(data.get("name", "")),
        "birthDate": str(data.get("birth_date", "")),
        "bloodType": str(data.get("blood_type", "")) or "unknown",
        "allergies": allergies,
        "conditions": conditions,
        "medicines": rows,
        "status": str(data.get("status", "none")),
        "emergencyContact": dict(contact),
        "emergencyPhone": str(contact.get("phone", "")),
        "emergencyPhoneUri": call_uri(str(contact.get("phone", ""))),
        "doctor": dict(doctor),
        "doctorPhone": str(doctor.get("phone", "")),
        "doctorPhoneUri": call_uri(str(doctor.get("phone", ""))),
        "updated": str(data.get("updated", "")),
        "incomplete": not allergies and not conditions and not str(data.get("blood_type", "")),
        "updatedDate": _date_of(data.get("updated")),
        "disclaimer": DISCLAIMER,
        "offline": True,
    }


def _date_of(stamp) -> str:
    try:
        return datetime.fromisoformat(str(stamp)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ""


def card_text(medicines: Sequence | None = None) -> str:
    """The same card as plain text — printable, and readable on any phone."""
    data = card(medicines)
    width = 46
    lines: list[str] = []
    lines.append("=" * width)
    lines.append("MEDICAL EMERGENCY CARD".center(width))
    lines.append("=" * width)
    if data["name"]:
        lines.append(f"Name        : {data['name']}")
    if data["birthDate"]:
        lines.append(f"Born        : {data['birthDate']}")
    lines.append(f"Blood type  : {data['bloodType']}")
    lines.append("")
    lines.append("ALLERGIES")
    if data["allergies"]:
        lines.extend(f"  - {item}" for item in data["allergies"])
    else:
        lines.append("  none recorded")
    lines.append("")
    lines.append("CHRONIC CONDITIONS")
    if data["conditions"]:
        lines.extend(f"  - {item}" for item in data["conditions"])
    else:
        lines.append("  none recorded")
    lines.append("")
    lines.append("CURRENT MEDICATIONS")
    for row in data["medicines"]:
        dose = f" {row['dose']}" if row["dose"] else ""
        marker = " [EMERGENCY]" if row["emergency"] else ""
        lines.append(f"  - {row['name']}{dose} @ {row['times'] or 'as needed'}{marker}")
    if not data["medicines"]:
        lines.append("  none recorded")
    lines.append("")
    if data["status"] not in ("", "none"):
        lines.append(f"Status      : {data['status']}")
    contact = data["emergencyContact"]
    if contact.get("name") or contact.get("phone"):
        lines.append(f"Emergency   : {contact.get('name', '')} {contact.get('phone', '')}".rstrip())
    if data["doctorPhone"] or data["doctor"].get("name"):
        lines.append(f"Doctor      : {data['doctor'].get('name', '')} {data['doctorPhone']}".rstrip())
    lines.append("")
    lines.append("This is not medical advice.")
    lines.append(f"Record updated: {data['updatedDate'] or 'never'}")
    lines.append("=" * width)
    return "\n".join(line for line in lines if line is not None)


def export_wallet(medicines: Sequence | None = None) -> Path:
    """Write the printable card next to the rest of the health data."""
    paths.reports_dir().mkdir(parents=True, exist_ok=True)
    target = paths.reports_dir() / "emergency-card.txt"
    target.write_text(card_text(medicines), encoding="utf-8")
    return target


def export_wallet_pdf(medicines: Sequence | None = None) -> Path:
    from .pdf import write_text_pdf

    paths.reports_dir().mkdir(parents=True, exist_ok=True)
    target = paths.reports_dir() / "emergency-card.pdf"
    write_text_pdf(
        target,
        "MEDICAL EMERGENCY CARD",
        card_text(medicines).splitlines(),
    )
    return target


def emergency_numbers() -> list[dict]:
    """Built-in numbers — they work with the network radio off."""
    data = profile()
    rows = []
    if data.get("emergency_contact", {}).get("phone"):
        rows.append(
            {
                "label": "Emergency contact",
                "name": data["emergency_contact"].get("name", ""),
                "phone": data["emergency_contact"].get("phone", ""),
                "uri": call_uri(data["emergency_contact"].get("phone", "")),
                "tint": "#ef4444",
            }
        )
    if data.get("doctor", {}).get("phone"):
        rows.append(
            {
                "label": "Doctor",
                "name": data["doctor"].get("name", ""),
                "phone": data["doctor"].get("phone", ""),
                "uri": call_uri(data["doctor"].get("phone", "")),
                "tint": "#f59e0b",
            }
        )
    if data.get("pharmacy", {}).get("phone"):
        rows.append(
            {
                "label": "Pharmacy",
                "name": data["pharmacy"].get("name", ""),
                "phone": data["pharmacy"].get("phone", ""),
                "uri": call_uri(data["pharmacy"].get("phone", "")),
                "tint": "#38bdf8",
            }
        )
    rows.append(
        {
            "label": "Ambulance (Egypt)",
            "name": "Ambulance",
            "phone": "123",
            "uri": "tel:123",
            "tint": "#ef4444",
        }
    )
    return rows

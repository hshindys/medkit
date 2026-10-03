from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

VALID_CATEGORIES = ("normal", "emergency")
DEFAULT_REFILL_AT = 2


@dataclass
class Medicine:
    name: str
    dose: str = ""
    times: list[str] = field(default_factory=list)
    stock: int | None = None
    refill_at: int = DEFAULT_REFILL_AT
    notes: str = ""
    category: str = "normal"
    active: bool = True
    emergency_contacts: str = ""
    days: int = 0
    # The international non-proprietary name ("bisoprolol" for "Concor").
    # The safety checks match on this first, then fall back to the brand
    # name, so a brand-only entry still finds its drug class.
    generic: str = ""
    # A personal missed-dose instruction. When empty the protocol is derived
    # from the medicine's drug class (see missed.py).
    missed_dose_note: str = ""

    @property
    def is_emergency(self) -> bool:
        return self.category == "emergency"

    def is_low(self) -> bool:
        return self.stock is not None and self.stock <= self.refill_at

    def is_out(self) -> bool:
        return self.stock == 0

    def parsed_times(self) -> list[time]:
        result: list[time] = []
        for raw in self.times:
            hour_text, _, minute_text = raw.partition(":")
            result.append(time(int(hour_text), int(minute_text)))
        return sorted(result)

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("name is required")
        if self.category not in VALID_CATEGORIES:
            errors.append("category must be normal or emergency")
        if self.refill_at < 0:
            errors.append("refill_at cannot be negative")
        if self.days < 0:
            errors.append("days cannot be negative")
        if self.stock is not None and self.stock < 0:
            errors.append("stock cannot be negative")
        if not self.times:
            errors.append("at least one time is required")
        for raw in self.times:
            try:
                self._parse_clock(raw)
            except ValueError:
                errors.append(f"time '{raw}' must be HH:MM")
        return errors

    @staticmethod
    def _parse_clock(raw: str) -> time:
        hour_text, sep, minute_text = raw.partition(":")
        if not sep or not hour_text.isdigit() or not minute_text.isdigit():
            raise ValueError(raw)
        hour, minute = int(hour_text), int(minute_text)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(raw)
        return time(hour, minute)

    @classmethod
    def from_dict(cls, raw: dict) -> Medicine:
        times = [str(item).strip() for item in raw.get("times", []) if str(item).strip()]
        stock = raw.get("stock")
        refill = raw.get("refill_at", DEFAULT_REFILL_AT)
        days = raw.get("days", 0)
        return cls(
            name=str(raw.get("name", "")).strip(),
            dose=str(raw.get("dose", "")),
            times=times,
            stock=None if stock is None else int(stock),
            refill_at=DEFAULT_REFILL_AT if refill is None else int(refill),
            notes=str(raw.get("notes", "")),
            category=str(raw.get("category", "normal")) or "normal",
            active=bool(raw.get("active", True)),
            emergency_contacts=str(raw.get("emergency_contacts", "")),
            days=int(days or 0),
            generic=str(raw.get("generic", "")),
            missed_dose_note=str(raw.get("missed_dose_note", "")),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "dose": self.dose,
            "times": list(self.times),
            "stock": self.stock,
            "refill_at": self.refill_at,
            "notes": self.notes,
            "category": self.category,
            "active": self.active,
            "emergency_contacts": self.emergency_contacts,
            "days": self.days,
            "generic": self.generic,
            "missed_dose_note": self.missed_dose_note,
        }


SEED_MEDICINES: list[Medicine] = [
    Medicine(name="Alpha 5 mg", dose="5 mg", times=["09:00"]),
    Medicine(name="Beta 40 mg", dose="40 mg", times=["09:00"]),
    Medicine(name="Gamma 10 mg", dose="10 mg", times=["20:00"]),
    Medicine(name="Delta 10 mg", dose="10 mg", times=["20:00"]),
    Medicine(name="Evening pill", dose="", times=["20:00"], notes="بعد الأكل، مش على معدة فاضية"),
    Medicine(name="Epsilon 10 mg", dose="10 mg", times=["20:00"], notes="مع العشاء"),
    Medicine(name="Omega sample", dose="", times=["20:00"], notes="مع العشاء"),
]

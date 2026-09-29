from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Sequence

from .models import Medicine
from .store import HistoryEntry

REMINDER_STEP = timedelta(minutes=15)
MAX_REMINDERS = 3
OVERDUE_AFTER = timedelta(minutes=60)
BADLY_OVERDUE_AFTER = timedelta(minutes=120)
PAIRING_GRACE = timedelta(minutes=5)

COLOR_NEUTRAL = "neutral"
COLOR_GREEN = "green"
COLOR_AMBER = "amber"
COLOR_RED = "red"

COLOR_LABELS = {
    COLOR_NEUTRAL: "nothing due yet",
    COLOR_GREEN: "all doses taken",
    COLOR_AMBER: "a dose is due now",
    COLOR_RED: "overdue or emergency supply low",
}


@dataclass
class Dose:
    medicine: Medicine
    when: datetime
    taken_at: datetime | None = None

    @property
    def taken(self) -> bool:
        return self.taken_at is not None

    def minutes_overdue(self, now: datetime) -> int:
        return max(0, int((now - self.when).total_seconds() // 60))

    def is_due_now(self, now: datetime) -> bool:
        return (
            not self.taken
            and self.when <= now < self.when + BADLY_OVERDUE_AFTER
        )

    def is_overdue(self, now: datetime) -> bool:
        return not self.taken and now >= self.when + OVERDUE_AFTER

    def is_badly_overdue(self, now: datetime) -> bool:
        return not self.taken and now >= self.when + BADLY_OVERDUE_AFTER

    @property
    def clock(self) -> str:
        return self.when.strftime("%H:%M")

    @property
    def label(self) -> str:
        dose = f" {self.medicine.dose}" if self.medicine.dose else ""
        return f"{self.clock} {self.medicine.name}{dose}"


@dataclass
class DayStatus:
    now: datetime
    doses: list[Dose] = field(default_factory=list)
    low: list[Medicine] = field(default_factory=list)
    out: list[Medicine] = field(default_factory=list)
    emergency_low: list[Medicine] = field(default_factory=list)
    emergency_out: list[Medicine] = field(default_factory=list)
    color: str = COLOR_NEUTRAL
    wizard_done: bool = False

    @property
    def total(self) -> int:
        return len(self.doses)

    @property
    def taken(self) -> int:
        return sum(1 for dose in self.doses if dose.taken)

    @property
    def pending(self) -> list[Dose]:
        return [dose for dose in self.doses if not dose.taken]

    @property
    def due_now(self) -> list[Dose]:
        return [dose for dose in self.doses if dose.is_due_now(self.now)]

    @property
    def overdue(self) -> list[Dose]:
        return [dose for dose in self.doses if dose.is_overdue(self.now)]

    @property
    def badly_overdue(self) -> list[Dose]:
        return [dose for dose in self.doses if dose.is_badly_overdue(self.now)]

    @property
    def low_count(self) -> int:
        return len(self.low)

    @property
    def emergency_issues(self) -> list[Medicine]:
        return self.emergency_out + [
            medicine for medicine in self.emergency_low if medicine not in self.emergency_out
        ]


def build_doses(
    medicines: Sequence[Medicine], now: datetime, history: Sequence[HistoryEntry]
) -> list[Dose]:
    day = now.date()
    doses: list[Dose] = []
    for medicine in medicines:
        if not medicine.active:
            continue
        for clock in medicine.parsed_times():
            doses.append(
                Dose(medicine=medicine, when=datetime.combine(day, clock, now.tzinfo))
            )
    doses.sort(key=lambda dose: (dose.when, dose.medicine.name))

    taken_entries = [
        entry
        for entry in history
        if entry.action == "taken" and entry.ts.date() == day
    ]
    taken_entries.sort(key=lambda entry: entry.ts)

    used: set[int] = set()
    for entry in taken_entries:
        candidates = [
            index
            for index, dose in enumerate(doses)
            if index not in used and dose.medicine.name == entry.medicine
        ]
        if not candidates:
            continue
        eligible = [
            index for index in candidates if doses[index].when <= entry.ts + PAIRING_GRACE
        ]
        pick = (
            max(eligible, key=lambda index: doses[index].when)
            if eligible
            else min(candidates, key=lambda index: doses[index].when)
        )
        used.add(pick)
        doses[pick].taken_at = entry.ts
    return doses


def evaluate(
    medicines: Sequence[Medicine],
    now: datetime,
    history: Sequence[HistoryEntry],
    wizard_done: bool,
) -> DayStatus:
    active = [medicine for medicine in medicines if medicine.active]
    doses = build_doses(active, now, history)
    low = [medicine for medicine in active if medicine.is_low()]
    out = [medicine for medicine in active if medicine.is_out()]
    emergency_low = [medicine for medicine in low if medicine.is_emergency]
    emergency_out = [medicine for medicine in out if medicine.is_emergency]
    status = DayStatus(
        now=now,
        doses=doses,
        low=low,
        out=out,
        emergency_low=emergency_low,
        emergency_out=emergency_out,
        wizard_done=wizard_done,
    )
    status.color = _color_for(status)
    return status


def _color_for(status: DayStatus) -> str:
    if not status.wizard_done:
        return COLOR_NEUTRAL
    if status.badly_overdue or status.emergency_issues:
        return COLOR_RED
    if status.due_now:
        return COLOR_AMBER
    if status.total > 0 and status.taken == status.total:
        return COLOR_GREEN
    return COLOR_NEUTRAL


def next_pending_dose(status: DayStatus) -> Dose | None:
    pending = sorted(status.pending, key=lambda dose: dose.when)
    if not pending:
        return None
    due = [dose for dose in pending if dose.when <= status.now]
    return due[0] if due else pending[0]


def adherence(
    medicines: Sequence[Medicine],
    now: datetime,
    history: Sequence[HistoryEntry],
    days: int,
) -> float | None:
    scheduled = 0
    taken = 0
    taken_by_day: dict[date, int] = {}
    for entry in history:
        if entry.action == "taken":
            taken_by_day[entry.ts.date()] = taken_by_day.get(entry.ts.date(), 0) + 1
    for offset in range(days):
        day = now.date() - timedelta(days=offset)
        day_remaining = taken_by_day.get(day, 0)
        for medicine in medicines:
            if not medicine.active:
                continue
            for clock in medicine.parsed_times():
                if datetime.combine(day, clock, now.tzinfo) > now:
                    continue
                scheduled += 1
                if day_remaining > 0:
                    day_remaining -= 1
                    taken += 1
    if scheduled == 0:
        return None
    return round(100.0 * taken / scheduled, 1)


def streaks(
    medicines: Sequence[Medicine], now: datetime, history: Sequence[HistoryEntry]
) -> dict[str, int]:
    taken_by_day: dict[str, dict[date, int]] = {}
    skipped_by_day: dict[str, dict[date, int]] = {}
    for entry in history:
        bucket = taken_by_day if entry.action == "taken" else skipped_by_day
        if entry.action not in ("taken", "skipped"):
            continue
        per_day = bucket.setdefault(entry.medicine, {})
        per_day[entry.ts.date()] = per_day.get(entry.ts.date(), 0) + 1

    result: dict[str, int] = {}
    for medicine in medicines:
        if not medicine.active:
            continue
        schedule_size = len(medicine.parsed_times())
        taken = taken_by_day.get(medicine.name, {})
        skipped = skipped_by_day.get(medicine.name, {})

        def complete(day: date) -> bool:
            return skipped.get(day, 0) == 0 and taken.get(day, 0) >= schedule_size

        streak = 0
        cursor = now.date()
        if complete(cursor):
            streak = 1
        cursor -= timedelta(days=1)
        while (now.date() - cursor).days <= 400:
            if not complete(cursor):
                break
            streak += 1
            cursor -= timedelta(days=1)
        result[medicine.name] = streak
    return result

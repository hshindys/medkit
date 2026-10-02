from __future__ import annotations

from datetime import datetime

from . import engine
from .engine import DayStatus
from .models import Medicine
from .store import (
    MedicineFile,
    HistoryEntry,
    append_history,
    load_medicines,
    read_history,
    save_medicines,
)


class ActionError(Exception):
    pass


def snapshot(now: datetime | None = None) -> tuple[MedicineFile, DayStatus, list[HistoryEntry]]:
    moment = now or datetime.now().astimezone()
    document = load_medicines()
    history = read_history()
    status = engine.evaluate(document.medicines, moment, history, document.wizard_done)
    return document, status, history


def _require(document: MedicineFile, name: str) -> Medicine:
    medicine = document.by_name(name)
    if medicine is None:
        raise ActionError(f"unknown medicine: {name}")
    return medicine


def mark_taken(name: str, now: datetime | None = None) -> str:
    moment = now or datetime.now().astimezone()
    document, status, _ = snapshot(moment)
    medicine = _require(document, name)
    pending = sorted(
        (dose for dose in status.doses if dose.medicine.name == name and not dose.taken),
        key=lambda dose: dose.when,
    )
    if not pending:
        raise ActionError(f"no pending dose for {name} today")
    dose = pending[0]
    append_history("taken", name, moment)
    if medicine.stock is not None:
        medicine.stock = max(0, medicine.stock - 1)
        save_medicines(document)
    stock_note = f", stock={medicine.stock}" if medicine.stock is not None else ""
    return f"marked taken: {dose.label}{stock_note}"


def mark_skipped(name: str, now: datetime | None = None) -> str:
    moment = now or datetime.now().astimezone()
    document, status, _ = snapshot(moment)
    _require(document, name)
    pending = sorted(
        (dose for dose in status.doses if dose.medicine.name == name and not dose.taken),
        key=lambda dose: dose.when,
    )
    if not pending:
        raise ActionError(f"no pending dose for {name} today")
    dose = pending[0]
    append_history("skipped", name, moment)
    return f"marked skipped: {dose.label}"


def set_count(name: str, count: int) -> str:
    if count < 0:
        raise ActionError("count cannot be negative")
    document = load_medicines()
    medicine = _require(document, name)
    medicine.stock = count
    save_medicines(document)
    return f"{name}: stock set to {count}"


def refill_low(target: int = 30) -> str:
    if target < 0:
        raise ActionError("count cannot be negative")
    document = load_medicines()
    refilled: list[str] = []
    for medicine in document.medicines:
        if medicine.stock is None or not (medicine.is_low() or medicine.is_out()):
            continue
        new_count = max(target, medicine.refill_at + 1)
        medicine.stock = new_count
        refilled.append(f"{medicine.name}={new_count}")
    if not refilled:
        raise ActionError("nothing to refill — no medicine is low on stock")
    save_medicines(document)
    return f"refilled {len(refilled)}: {', '.join(refilled)}"


def refill_one(name: str, target: int = 30) -> str:
    if target < 0:
        raise ActionError("count cannot be negative")
    document = load_medicines()
    medicine = _require(document, name)
    new_count = max(target, medicine.refill_at + 1)
    medicine.stock = new_count
    save_medicines(document)
    return f"refilled {name}: stock set to {new_count}"


def complete_setup(counts: dict[str, int]) -> str:
    document = load_medicines()
    for name, count in counts.items():
        medicine = _require(document, name)
        if count < 0:
            raise ActionError(f"negative count for {name}")
        medicine.stock = count
    document.wizard_done = True
    save_medicines(document)
    return f"setup complete for {len(counts)} medicines"


def add_medicine(medicine: Medicine) -> str:
    errors = medicine.validation_errors()
    if errors:
        raise ActionError("; ".join(errors))
    document = load_medicines()
    if document.by_name(medicine.name) is not None:
        raise ActionError(f"medicine already exists: {medicine.name}")
    document.medicines.append(medicine)
    save_medicines(document)
    return f"added {medicine.name}"


def update_medicine(original_name: str, medicine: Medicine) -> str:
    errors = medicine.validation_errors()
    if errors:
        raise ActionError("; ".join(errors))
    document = load_medicines()
    target = _require(document, original_name)
    if medicine.name != original_name and document.by_name(medicine.name) is not None:
        raise ActionError(f"medicine already exists: {medicine.name}")
    index = document.medicines.index(target)
    document.medicines[index] = medicine
    save_medicines(document)
    return f"updated {medicine.name}"


def delete_medicine(name: str) -> str:
    document = load_medicines()
    target = _require(document, name)
    document.medicines.remove(target)
    save_medicines(document)
    return f"deleted {name}"

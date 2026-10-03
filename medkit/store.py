from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from . import paths
from .models import SEED_MEDICINES, Medicine


@dataclass
class MedicineFile:
    wizard_done: bool
    medicines: list[Medicine]

    def active(self) -> list[Medicine]:
        return [medicine for medicine in self.medicines if medicine.active]

    def by_name(self, name: str) -> Medicine | None:
        for medicine in self.medicines:
            if medicine.name == name:
                return medicine
        return None


@dataclass(frozen=True)
class HistoryEntry:
    ts: datetime
    medicine: str
    action: str

    def to_json(self) -> str:
        payload = {
            "ts": self.ts.isoformat(timespec="seconds"),
            "medicine": self.medicine,
            "action": self.action,
        }
        return json.dumps(payload, ensure_ascii=False)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_medicines() -> MedicineFile:
    path = paths.medicines_file()
    if not path.exists():
        seed = MedicineFile(wizard_done=False, medicines=list(SEED_MEDICINES))
        save_medicines(seed)
        return seed
    raw = json.loads(path.read_text(encoding="utf-8"))
    medicines = [Medicine.from_dict(item) for item in raw.get("medicines", [])]
    return MedicineFile(wizard_done=bool(raw.get("wizard_done", False)), medicines=medicines)


def save_medicines(document: MedicineFile) -> None:
    payload = {
        "version": 1,
        "wizard_done": document.wizard_done,
        "medicines": [medicine.to_dict() for medicine in document.medicines],
    }
    _atomic_write(paths.medicines_file(), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_history() -> list[HistoryEntry]:
    path = paths.history_file()
    if not path.exists():
        return []
    entries: list[HistoryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            entries.append(
                HistoryEntry(
                    ts=datetime.fromisoformat(raw["ts"]),
                    medicine=str(raw["medicine"]),
                    action=str(raw["action"]),
                )
            )
        except (ValueError, KeyError, TypeError):
            continue
    return entries


def append_history(action: str, medicine: str, ts: datetime | None = None) -> HistoryEntry:
    paths.ensure_data_dir()
    stamp = ts or datetime.now().astimezone()
    if stamp.tzinfo is None:
        stamp = stamp.astimezone()
    entry = HistoryEntry(ts=stamp, medicine=medicine, action=action)
    with paths.history_file().open("a", encoding="utf-8") as handle:
        handle.write(entry.to_json() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def load_state() -> dict:
    path = paths.state_file()
    if not path.exists():
        return {"version": 1, "sent": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"version": 1, "sent": {}}
    sent = raw.get("sent", {})
    if not isinstance(sent, dict):
        sent = {}
    return {"version": 1, "sent": sent}


def save_state(state: dict) -> None:
    cutoff = (datetime.now().astimezone() - timedelta(days=30)).isoformat(timespec="seconds")
    sent = {key: value for key, value in state.get("sent", {}).items() if str(value) >= cutoff}
    state = {"version": 1, "sent": sent}
    _atomic_write(paths.state_file(), json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def append_emergency_log(medicine: Medicine, stock: int) -> None:
    paths.ensure_data_dir()
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} OUT-OF-STOCK: {medicine.name} (dose={medicine.dose or 'n/a'}) remaining={stock}\n"
    with paths.emergency_log().open("a", encoding="utf-8") as handle:
        handle.write(line)


def history_for_day(entries: Iterable[HistoryEntry], day: date) -> list[HistoryEntry]:
    return [entry for entry in entries if entry.ts.date() == day]


def history_between(
    entries: Iterable[HistoryEntry], start: datetime, end: datetime
) -> list[HistoryEntry]:
    return [entry for entry in entries if start <= entry.ts < end]


# ---- generic local records (side effects, vitals, profile, review) ------
#
# Every health record MedKit keeps beyond the dose log lives in its own file.
# Same rules as the rest of the store: plain JSON on this machine, atomic
# writes for documents, append-only for logs, and a read that never raises —
# a hand-edited file must degrade to "no records" instead of killing the bar.

def read_json(path: Path, default: dict | list | None = None) -> dict | list:
    if not path.exists():
        return {} if default is None else default
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {} if default is None else default
    return raw


def write_json(path: Path, payload: dict | list) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def append_jsonl(path: Path, payload: dict) -> dict:
    paths.ensure_data_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return payload


def load_profile() -> dict:
    """Everything a first responder would need, and nothing else."""
    default = {
        "version": 1,
        "name": "",
        "birth_date": "",
        "blood_type": "",
        "allergies": [],
        "conditions": [],
        "emergency_contact": {"name": "", "phone": ""},
        "doctor": {"name": "", "phone": ""},
        "pharmacy": {"name": "", "phone": ""},
        # none | pregnant | breastfeeding | trying | postpartum
        "status": "none",
        "weight_kg": None,
        "height_cm": None,
        "updated": "",
    }
    raw = read_json(paths.profile_file(), {})
    if not isinstance(raw, dict):
        return default
    profile = dict(default)
    profile.update(raw)
    for key in ("allergies", "conditions"):
        if not isinstance(profile.get(key), list):
            profile[key] = []
    for key in ("emergency_contact", "doctor", "pharmacy"):
        if not isinstance(profile.get(key), dict):
            profile[key] = dict(default[key])
    return profile


def save_profile(profile: dict) -> None:
    profile = dict(profile)
    profile["version"] = 1
    profile["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(paths.profile_file(), profile)


def read_sideeffects() -> list[dict]:
    return read_jsonl(paths.sideeffects_file())


def append_sideeffect(record: dict) -> dict:
    return append_jsonl(paths.sideeffects_file(), record)


def read_vitals() -> list[dict]:
    return read_jsonl(paths.vitals_file())


def append_vital(record: dict) -> dict:
    return append_jsonl(paths.vitals_file(), record)


def load_review() -> dict:
    default = {"version": 1, "last_review": "", "next_review": "", "history": []}
    raw = read_json(paths.review_file(), {})
    if not isinstance(raw, dict):
        return default
    review = dict(default)
    review.update(raw)
    if not isinstance(review.get("history"), list):
        review["history"] = []
    return review


def save_review(review: dict) -> None:
    review = dict(review)
    review["version"] = 1
    write_json(paths.review_file(), review)

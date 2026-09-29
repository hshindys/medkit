from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from . import actions, engine, paths, vault
from .models import Medicine
from .tick import build_notices, run_tick
from .store import load_medicines, read_history


class Harness:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.checks.append((name, bool(condition), detail))

    @property
    def failures(self) -> int:
        return sum(1 for _, ok, _ in self.checks if not ok)

    def report(self) -> None:
        for name, ok, detail in self.checks:
            mark = "PASS" if ok else "FAIL"
            suffix = f" — {detail}" if detail else ""
            print(f"[{mark}] {name}{suffix}")
        total = len(self.checks)
        print(f"\n{total - self.failures}/{total} checks passed")


def _tick(moment: datetime, dispatch: bool = False):
    return run_tick(dispatch=dispatch, now=moment)


def run() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="medkit-headless-"))
    os.environ["MEDKIT_DATA_DIR"] = str(sandbox)
    harness = Harness()

    base = datetime(2026, 9, 28, 8, 0).astimezone()
    morning = base.replace(hour=9, minute=0)
    evening = base.replace(hour=20, minute=0)

    document = load_medicines()
    harness.check(
        "seed medicines created",
        len(document.medicines) == 7,
        f"{len(document.medicines)} medicines in {paths.medicines_file()}",
    )
    harness.check(
        "wizard starts pending",
        document.wizard_done is False,
        "reminders disabled until pill counts are entered",
    )
    harness.check(
        "seed stock is unknown (never guessed)",
        all(medicine.stock is None for medicine in document.medicines),
    )
    harness.check(
        "evening-only medicine has no 09:00 slot",
        all("09:00" not in medicine.times for medicine in document.medicines
            if medicine.name in ("Gamma 10 mg", "Delta 10 mg", "Evening pill",
                                 "Epsilon 10 mg", "Omega sample")),
    )

    before = _tick(morning)
    harness.check(
        "tick is a no-op before setup",
        before.setup_pending and not before.fired,
        before.lines[0] if before.lines else "",
    )

    counts = {medicine.name: 30 for medicine in document.medicines}
    actions.complete_setup(counts)
    harness.check("setup completes", load_medicines().wizard_done is True)

    due = _tick(morning + timedelta(seconds=5))
    reminder_keys = [notice.key for notice in due.fired if notice.kind == "reminder"]
    harness.check(
        "09:00 dose reminder fires for the two morning medicines",
        len(reminder_keys) == 2,
        ", ".join(reminder_keys),
    )
    status = due.status
    harness.check(
        "tray colour is amber while a dose is due",
        status.color == engine.COLOR_AMBER,
        f"color={status.color}, doses={status.taken}/{status.total}",
    )

    again = _tick(morning + timedelta(seconds=30))
    harness.check(
        "duplicate tick fires nothing (deduplicated)",
        not again.fired,
        f"suppressed={len(again.suppressed)} keys",
    )

    second = _tick(morning + timedelta(minutes=15))
    harness.check(
        "second reminder at +15 minutes",
        len([n for n in second.fired if n.kind == "reminder"]) == 2,
        ", ".join(n.key for n in second.fired),
    )
    third = _tick(morning + timedelta(minutes=30))
    harness.check(
        "third reminder at +30 minutes",
        len([n for n in third.fired if n.kind == "reminder"]) == 2,
    )
    fourth = _tick(morning + timedelta(minutes=45))
    harness.check(
        "fourth reminder is never sent (max 3)",
        not fourth.fired,
        f"fired={len(fourth.fired)}",
    )

    overdue = _tick(morning + timedelta(minutes=61))
    overdue_notices = [n for n in overdue.fired if n.kind == "overdue"]
    harness.check(
        "overdue escalates to critical after 60 minutes",
        len(overdue_notices) == 2 and all(n.urgency == "critical" for n in overdue_notices),
        ", ".join(f"{n.summary} ({n.urgency})" for n in overdue_notices),
    )
    harness.check(
        "overdue under 2 hours keeps the tray amber",
        overdue.status.color == engine.COLOR_AMBER,
        f"color={overdue.status.color}",
    )
    badly = _tick(morning + timedelta(minutes=121))
    harness.check(
        "overdue past 2 hours turns the tray red",
        badly.status.color == engine.COLOR_RED,
        f"color={badly.status.color} at +121 minutes",
    )

    taken_message = actions.mark_taken("Alpha 5 mg", now=morning + timedelta(minutes=70))
    history = read_history()
    taken_entries = [entry for entry in history if entry.action == "taken"]
    harness.check(
        "marking a dose taken appends to history.jsonl",
        len(taken_entries) == 1 and taken_entries[0].medicine == "Alpha 5 mg",
        taken_entries[0].to_json() if taken_entries else "no entry",
    )
    harness.check(
        "taking a pill decrements the counted stock",
        load_medicines().by_name("Alpha 5 mg").stock == 29,
        f"stock={load_medicines().by_name('Alpha 5 mg').stock}",
    )
    harness.check(
        "mark taken reports the dose it closed",
        "09:00" in taken_message,
        taken_message,
    )

    after_take = _tick(morning + timedelta(minutes=71))
    harness.check(
        "taken dose stops generating reminders",
        all(n.medicine != "Alpha 5 mg" for n in after_take.fired),
        ", ".join(n.key for n in after_take.fired),
    )

    actions.set_count("Alpha 5 mg", 2)
    restock = _tick(morning + timedelta(minutes=72))
    restock_notices = [n for n in restock.fired if n.kind == "restock"]
    harness.check(
        "restock alert fires at the refill threshold",
        len(restock_notices) == 1,
        restock_notices[0].summary if restock_notices else "no restock notice",
    )
    harness.check(
        "restock alert is logged in history as action=restock",
        any(entry.action == "restock" for entry in read_history()),
    )
    restock_twice = _tick(morning + timedelta(minutes=73))
    harness.check(
        "restock alert re-fires at most once per day",
        not [n for n in restock_twice.fired if n.kind == "restock"],
    )

    refill_message = actions.refill_low(30)
    harness.check(
        "refill tops low medicines back to 30 pills",
        load_medicines().by_name("Alpha 5 mg").stock == 30,
        refill_message,
    )

    actions.add_medicine(
        Medicine(
            name="Rescue tablet",
            dose="0.5 mg",
            times=["08:00"],
            stock=0,
            refill_at=2,
            category="emergency",
            emergency_contacts="اتصل بالإسعاف 123",
            days=5,
        )
    )
    emergency = _tick(morning + timedelta(minutes=74))
    emergency_notices = [n for n in emergency.fired if n.kind == "emergency"]
    harness.check(
        "emergency medicine at 0 pills fires a critical notice",
        len(emergency_notices) == 1 and emergency_notices[0].urgency == "critical",
        emergency_notices[0].summary if emergency_notices else "missing",
    )
    log_path = paths.emergency_log()
    harness.check(
        "emergency.log got a timestamped line",
        log_path.exists() and "OUT-OF-STOCK" in log_path.read_text(encoding="utf-8"),
        log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        if log_path.exists() else "no log",
    )
    harness.check(
        "emergency low stock forces the tray colour to red",
        emergency.status.color == engine.COLOR_RED,
        f"color={emergency.status.color}",
    )
    harness.check(
        "emergency course days are stored and round-trip",
        load_medicines().by_name("Rescue tablet").days == 5,
        f"days={load_medicines().by_name('Rescue tablet').days}",
    )

    evening_take = _tick(evening)
    harness.check(
        "20:00 evening slot becomes due in the evening",
        any(dose.when.hour == 20 for dose in evening_take.status.due_now),
        f"due now: {', '.join(d.label for d in evening_take.status.due_now)}",
    )

    actions.mark_taken("Evening pill", now=evening + timedelta(minutes=5))
    streaks = engine.streaks(
        load_medicines().medicines, evening, read_history()
    )
    harness.check(
        "per-medicine streak is tracked",
        streaks.get("Evening pill", 0) >= 1,
        f"sample streak={streaks.get('Evening pill')}",
    )

    seven = engine.adherence(load_medicines().medicines, evening, read_history(), 7)
    harness.check(
        "7-day adherence percentage is computed",
        seven is not None and 0 < seven < 100,
        f"7-day={seven}%",
    )

    notices = build_notices(evening_take.status, evening)
    harness.check(
        "notification plan is stable and typed",
        all(notice.kind in ("reminder", "overdue", "restock", "emergency") for notice in notices),
        f"{len(notices)} notices planned",
    )

    patched_vault = sandbox / "لوحة-الصحة.md"
    patched_vault.write_text("# لوحة الصحة\n", encoding="utf-8")
    original_vault = paths.VAULT_FILE
    paths.VAULT_FILE = patched_vault
    try:
        appended, message = vault.append_daily_summary(evening)
        appended_twice, _ = vault.append_daily_summary(evening)
    finally:
        paths.VAULT_FILE = original_vault
    harness.check(
        "daily vault summary is appended once",
        appended and not appended_twice,
        message,
    )
    harness.check(
        "vault summary content is a short adherence block",
        "MedKit" in patched_vault.read_text(encoding="utf-8"),
        patched_vault.read_text(encoding="utf-8").strip().splitlines()[-1],
    )

    sandbox_files = sorted(path.name for path in sandbox.iterdir())
    harness.check(
        "every data file lives inside the sandbox",
        paths.medicines_file().is_relative_to(sandbox)
        and paths.history_file().is_relative_to(sandbox)
        and paths.state_file().is_relative_to(sandbox),
        f"files={sandbox_files}",
    )

    harness.report()
    print("\n--- history.jsonl ---")
    print(paths.history_file().read_text(encoding="utf-8").strip())
    print("\n--- emergency.log ---")
    print(paths.emergency_log().read_text(encoding="utf-8").strip())
    print("\n--- medicines.json (first medicine) ---")
    print(load_medicines().medicines[0].to_dict())
    return 1 if harness.failures else 0

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from . import actions, engine, paths, vault
from .models import Medicine
from .tick import build_notices, run_tick
from .store import load_medicines, read_history, save_medicines


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

    from .cli import build_parser

    parser = build_parser()
    refill_one_args = parser.parse_args(["--refill", "Omega sample"])
    refill_all_args = parser.parse_args(["--refill"])
    add_args = parser.parse_args(["--add-medicine"])
    edit_args = parser.parse_args(["--edit", "banadoll"])
    delete_args = parser.parse_args(["--delete", "banadoll"])
    harness.check(
        "refill, add-medicine, edit and delete flags parse",
        refill_one_args.refill == "Omega sample"
        and refill_all_args.refill == ""
        and add_args.add_medicine is True
        and edit_args.edit == "banadoll"
        and delete_args.delete == "banadoll"
        and parser.parse_args([]).edit is None
        and parser.parse_args([]).delete is None,
        f"one={refill_one_args.refill!r} all={refill_all_args.refill!r} "
        f"add={add_args.add_medicine} edit={edit_args.edit!r} "
        f"delete={delete_args.delete!r}",
    )

    low_one = load_medicines().medicines[-1]
    actions.set_count(low_one.name, 1)
    refilled = actions.refill_one(low_one.name)
    expected_stock = max(30, low_one.refill_at + 1)
    harness.check(
        "refill tops a single medicine back up",
        load_medicines().by_name(low_one.name).stock == expected_stock,
        f"{refilled} (expected {expected_stock})",
    )

    actions.add_medicine(
        Medicine(name="Selftest discard", dose="1 mg", times=["12:00"])
    )
    removed = actions.delete_medicine("Selftest discard")
    unknown_error = ""
    try:
        actions.delete_medicine("Selftest discard")
    except actions.ActionError as error:
        unknown_error = str(error)
    harness.check(
        "delete drops a medicine and refuses an unknown name",
        load_medicines().by_name("Selftest discard") is None
        and removed == "deleted Selftest discard"
        and "unknown medicine" in unknown_error,
        f"{removed} / error={unknown_error!r}",
    )

    # ---- safety, health records and reports --------------------------
    from . import (
        adherence as adherence_mod,
        emergency as emergency_mod,
        food as food_mod,
        interactions as interactions_mod,
        missed as missed_mod,
        panel_data,
        pregnancy as pregnancy_mod,
        refill as refill_mod,
        review as review_mod,
        sideeffects as sideeffects_mod,
        tick as tick_mod,
        vitals as vitals_mod,
    )
    from .knowledge import load as load_knowledge

    book = load_knowledge()
    harness.check(
        "knowledge snapshot carries its sources",
        book.disclaimer.startswith("This is not medical advice")
        and len(book.sources) >= 3
        and book.updated,
        f"{len(book.sources)} sources, updated {book.updated}",
    )
    resolved = book.resolve("Concor", "")
    harness.check(
        "brand name resolves to a generic ingredient",
        resolved.generic == "bisoprolol",
        f"Concor -> {resolved.generic!r}",
    )

    document = load_medicines()
    document.by_name("Alpha 5 mg").generic = "amlodipine"
    document.by_name("Beta 40 mg").generic = "ibuprofen"
    document.by_name("Gamma 10 mg").generic = "warfarin"
    save_medicines(document)
    active = [medicine for medicine in document.medicines if medicine.active]

    findings = interactions_mod.check(active)
    nsaid_bp = [finding for finding in findings if finding.is_nsaid_bp]
    harness.check(
        "an NSAID against a blood-pressure tablet is flagged",
        len(nsaid_bp) >= 1
        and all(finding.effect and finding.advice for finding in findings),
        ", ".join(f"{f.a}+{f.b}[{f.severity}]" for f in findings),
    )
    summary = interactions_mod.summarize(findings)
    harness.check(
        "interaction summary counts every severity bucket",
        summary["total"] == len(findings) and summary["worst"] in ("mild", "moderate", "severe"),
        f"{summary['total']} findings, worst {summary['worst']}",
    )

    tips = food_mod.tips_for(document.by_name("Beta 40 mg"))
    food_rules = tips["rules"]
    harness.check(
        "meal timing is not phrased as an avoidance",
        any(rule["relation"] == "with" and rule["label"].startswith("take with")
            for rule in food_rules)
        and all(rule["label"] for rule in food_rules),
        "; ".join(rule["label"] for rule in food_rules),
    )
    hint = tick_mod._food_hint(document.by_name("Beta 40 mg"))
    harness.check(
        "the food hint fits inside a notification",
        0 < len(hint) <= 80,
        hint,
    )

    emergency_mod.set_field("blood_type", "O+")
    emergency_mod.set_field("allergies", "penicillin, aspirin")
    emergency_mod.set_field("status", "pregnant")
    pregnancy_state = pregnancy_mod.check(active, emergency_mod.profile())
    harness.check(
        "pregnancy profile flags the NSAID",
        pregnancy_state["active"]
        and any(item["name"] == "Beta 40 mg" for item in pregnancy_state["findings"])
        and all(item["alternative"] for item in pregnancy_state["findings"]),
        ", ".join(f"{i['name']}:{i['risk']}" for i in pregnancy_state["findings"]),
    )
    emergency_mod.set_field("status", "none")

    document = load_medicines()
    document.by_name("Gamma 10 mg").missed_dose_note = "Never double it — ring the clinic"
    save_medicines(document)
    protocol = missed_mod.protocol_for(load_medicines().by_name("Gamma 10 mg"))
    harness.check(
        "a personal missed-dose note wins over the generic rule",
        protocol["source"] == "personal"
        and "ring the clinic" in protocol["text"],
        f"{protocol['sourceLabel']}: {protocol['text']}",
    )

    document = load_medicines()
    document.by_name("Alpha 5 mg").stock = 2
    save_medicines(document)
    refills = refill_mod.check(load_medicines().active(), profile=emergency_mod.profile())
    harness.check(
        "two days of pills counts as a refill warning",
        any(row["name"] == "Alpha 5 mg" and row["warn"] for row in refills["medicines"])
        and refills["warningDays"] == 3,
        ", ".join(f"{r['name']}:{r['daysLeft']}d" for r in refills["medicines"][:3]),
    )

    for _ in range(3):
        sideeffects_mod.log("Beta 40 mg", "drowsiness", "moderate")
    repeats = sideeffects_mod.repeat_alerts()
    harness.check(
        "the third report of one effect raises a repeat alert",
        len(repeats) == 1
        and repeats[0]["count"] == 3
        and repeats[0]["effect"] == "drowsiness",
        str([{k: r[k] for k in ("medicine", "effect", "count", "worst")} for r in repeats]),
    )

    vitals_mod.add("bp", "128/82", now=morning)
    vitals_mod.add("pulse", 71, now=morning)
    vitals_chart = vitals_mod.chart(14, morning)
    correlation = vitals_mod.correlate(active, read_history(), 30, morning)
    harness.check(
        "a blood-pressure reading keeps both numbers",
        vitals_chart["count"] == 2
        and vitals_chart["series"]["bp"][0]["value2"] == 82
        and "bp" in vitals_chart["kinds"],
        f"count={vitals_chart['count']}, bp={vitals_chart['series']['bp'][0]}",
    )
    harness.check(
        "a reading is matched to the dose taken around it",
        correlation["linked"] >= 1 and correlation["windowHours"] == 4,
        f"linked={correlation['linked']}, unlinked={correlation['unlinked']}",
    )

    card = emergency_mod.card(active)
    text_file = emergency_mod.export_wallet(active)
    pdf_file = emergency_mod.export_wallet_pdf(active)
    harness.check(
        "the emergency card carries blood type and allergies",
        card["bloodType"] == "O+"
        and card["allergies"] == ["penicillin", "aspirin"]
        and card["offline"] is True,
        f"blood={card['bloodType']}, allergies={card['allergies']}",
    )
    harness.check(
        "the printable card is written as text and as PDF",
        text_file.read_text(encoding="utf-8").startswith("=")
        and pdf_file.read_bytes()[:5] == b"%PDF-",
        f"{text_file.name}, {pdf_file.name}",
    )
    harness.check(
        "the offline emergency number is always on the card",
        any(row["label"].startswith("Ambulance") and row["uri"] == "tel:123"
            for row in emergency_mod.emergency_numbers()),
        ", ".join(row["label"] for row in emergency_mod.emergency_numbers()),
    )

    review_state = review_mod.status()
    harness.check(
        "the first therapy review is due immediately",
        review_state["due"] and review_state["never"] is True
        and review_state["intervalMonths"] == 3,
        f"last={review_state['lastLabel']}, next={review_state['nextLabel']}",
    )

    payload = panel_data.payload(now=morning + timedelta(minutes=30))
    health = payload["health"]
    expected_sections = (
        "interactions", "food", "pregnancy", "adherence", "sideEffects",
        "vitals", "missed", "refills", "review", "reports", "emergency",
        "profile", "disclaimer", "sources", "updated",
    )
    harness.check(
        "the panel payload carries every health section",
        all(section in health for section in expected_sections)
        and health["interactions"]["count"] >= 1
        and health["sideEffects"]["repeats"][0]["count"] == 3
        and health["emergency"]["bloodType"] == "O+"
        and "lines" in health["reports"]["weekly"],
        f"sections={[key for key in expected_sections if key not in health]}",
    )

    moment = morning + timedelta(minutes=30)
    planned = tick_mod.build_health_notices(load_medicines(), read_history(), moment)
    planned_kinds = {notice.kind for notice in planned}
    harness.check(
        "the health notifier covers every safety signal",
        {"interaction", "food", "sideeffect", "refill", "review"} <= planned_kinds
        and all(notice.summary and notice.body for notice in planned),
        ", ".join(sorted(planned_kinds)),
    )
    harness.check(
        "every health notice declares one of the known kinds",
        all(notice.kind in (
            "reminder", "overdue", "restock", "emergency", "interaction", "food",
            "adherence", "refill", "sideeffect", "missed", "review", "pregnancy",
        ) for notice in planned),
        ", ".join(sorted(planned_kinds)),
    )

    first_tick = tick_mod.run_tick(dispatch=False, now=moment)
    second_tick = tick_mod.run_tick(dispatch=False, now=moment)
    fired_kinds = {notice.kind for notice in first_tick.fired}
    harness.check(
        "safety notices fire beside the dose reminders",
        {"interaction", "food", "sideeffect"} <= fired_kinds,
        ", ".join(sorted(fired_kinds)),
    )
    harness.check(
        "health notices are deduplicated like the dose reminders",
        not second_tick.fired,
        ", ".join(notice.summary for notice in second_tick.fired),
    )

    review_mod.mark_reviewed(now=moment)
    after_review = review_mod.status(moment)
    harness.check(
        "recording a review pushes the next one three months out",
        after_review["due"] is False and after_review["never"] is False,
        f"next={after_review['nextLabel']}",
    )

    harness.report()
    print("\n--- history.jsonl ---")
    print(paths.history_file().read_text(encoding="utf-8").strip())
    print("\n--- emergency.log ---")
    print(paths.emergency_log().read_text(encoding="utf-8").strip())
    print("\n--- medicines.json (first medicine) ---")
    print(load_medicines().medicines[0].to_dict())
    return 1 if harness.failures else 0

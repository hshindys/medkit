from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time

from . import actions, paths, store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medkit",
        description="MedKit — medication tracker with a Wayland system tray icon",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui", action="store_true", help="tray icon + dashboard (default)")
    group.add_argument("--dashboard", action="store_true", help="open the dashboard window")
    group.add_argument(
        "--dashboard-toggle",
        action="store_true",
        help="open the dashboard, or close it when it is already open",
    )
    group.add_argument(
        "--plugin-status",
        action="store_true",
        help="print one JSON status line (for the omarchy bar widget)",
    )
    group.add_argument(
        "--plugin-panel",
        action="store_true",
        help="print the full JSON payload behind the omarchy panel",
    )
    group.add_argument(
        "--notify-due",
        metavar="TAB",
        help="notify about the doses in one panel tab that are due now",
    )
    group.add_argument("--wizard", action="store_true", help="open the pill-count wizard")
    group.add_argument(
        "--refill",
        nargs="?",
        const="",
        metavar="NAME",
        help="top up every medicine that is low, or just one medicine by name",
    )
    group.add_argument(
        "--add-medicine",
        action="store_true",
        help="open the dashboard with the add-medicine dialog ready",
    )
    group.add_argument(
        "--edit",
        metavar="NAME",
        help="open the dashboard with the edit dialog ready for one medicine",
    )
    group.add_argument(
        "--delete",
        metavar="NAME",
        help="open the dashboard with the delete confirmation ready for one medicine",
    )
    group.add_argument("--tick", action="store_true", help="evaluate the schedule and notify")
    group.add_argument("--vault-summary", action="store_true", help="append today's summary to the health vault")
    group.add_argument("--headless-test", action="store_true", help="run the logic self test")
    group.add_argument("--test-notify", action="store_true", help="fire one real test notification")
    group.add_argument("--take", metavar="NAME", help="mark the next dose as taken")
    group.add_argument("--skip", metavar="NAME", help="mark the next dose as skipped")
    group.add_argument("--set-count", nargs=2, metavar=("NAME", "COUNT"), help="set a pill count")
    group.add_argument("--status", action="store_true", help="print today's status")

    # ---- medical safety, health records and reports --------------------
    safety = parser.add_argument_group("medical safety and health records")
    safety.add_argument(
        "--interactions",
        action="store_true",
        help="check every active medicine against every other one",
    )
    safety.add_argument(
        "--food",
        action="store_true",
        help="food and meal-timing advice for each active medicine",
    )
    safety.add_argument(
        "--pregnancy",
        action="store_true",
        help="flag medicines that are unsafe for the current profile status",
    )
    safety.add_argument(
        "--missed",
        action="store_true",
        help="today's missed doses plus the per-medicine protocol for each",
    )
    safety.add_argument(
        "--refill-status",
        action="store_true",
        help="remaining pills, days of supply and what is close to running out",
    )
    safety.add_argument(
        "--adherence",
        action="store_true",
        help="daily adherence, the 7-day graph, the streak and the monthly score",
    )
    safety.add_argument(
        "--report",
        metavar="PERIOD",
        choices=("weekly", "monthly"),
        help="print the weekly or monthly health report",
    )
    safety.add_argument(
        "--review",
        action="store_true",
        help="medication therapy review status (every 3 months)",
    )
    safety.add_argument(
        "--review-export",
        action="store_true",
        help="export the therapy review as a PDF for the doctor",
    )
    safety.add_argument(
        "--review-done",
        action="store_true",
        help="record that the review happened; next one is due in 3 months",
    )
    safety.add_argument(
        "--emergency-card",
        action="store_true",
        help="print the emergency medical card (blood type, allergies, medicines)",
    )
    safety.add_argument(
        "--emergency-export",
        nargs="?",
        const="txt",
        choices=("txt", "pdf"),
        help="write the emergency card to a printable file (default: txt)",
    )
    safety.add_argument(
        "--emergency-call",
        metavar="TARGET",
        help="dial emergency contact, doctor or pharmacy (works offline)",
    )
    safety.add_argument(
        "--call-pharmacy",
        action="store_true",
        help="dial the pharmacy number saved on the emergency card",
    )
    safety.add_argument(
        "--profile-show",
        action="store_true",
        help="show the emergency profile stored on this machine",
    )
    safety.add_argument(
        "--profile-set",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="set a profile field, e.g. blood_type 'O+' or allergies 'penicillin, aspirin'",
    )
    safety.add_argument(
        "--side-effect",
        nargs=3,
        metavar=("NAME", "EFFECT", "SEVERITY"),
        help="log a side effect: mild, moderate or severe (or 1-3)",
    )
    safety.add_argument(
        "--side-effect-list",
        action="store_true",
        help="list logged side effects and any reported 3+ times",
    )
    safety.add_argument(
        "--vital",
        nargs="+",
        metavar="ARG",
        help="vitals: 'add bp 120/80', 'add glucose 112', 'list', 'import FILE.csv'",
    )
    safety.add_argument(
        "--set-generic",
        nargs=2,
        metavar=("NAME", "GENERIC"),
        help="set the generic name of a medicine for safety matching",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --tick: evaluate and report without sending notifications",
    )
    parser.add_argument("--data-dir", metavar="PATH", help="override the data directory")
    return parser


def _dashboard_pid_file():
    return paths.data_dir() / "dashboard.pid"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _dashboard_pid() -> int | None:
    try:
        pid = int(_dashboard_pid_file().read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _pid_alive(pid) else None


def _spawn_dashboard() -> int:
    bin_path = paths.medkit_bin()
    command = (
        [str(bin_path), "--dashboard"]
        if bin_path.exists()
        else [sys.executable, "-m", "medkit", "--dashboard"]
    )
    paths.ensure_data_dir()
    with open(paths.data_dir() / "dashboard.log", "a") as log:
        child = subprocess.Popen(
            command,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
    return child.pid


def _dashboard_toggle() -> int:
    pid = _dashboard_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.05)
        _dashboard_pid_file().unlink(missing_ok=True)
        print("dashboard closed")
        return 0
    _dashboard_pid_file().unlink(missing_ok=True)
    child_pid = _spawn_dashboard()
    if _dashboard_pid() is None:
        _dashboard_pid_file().write_text(str(child_pid))
    print("dashboard opened")
    return 0


def _request_dashboard_action(action: str) -> int:
    # The dashboard is a separate GTK process, so the request travels as a
    # one-shot file it polls: written before the process exists, consumed by
    # whichever instance is alive (or the one this call is about to start).
    paths.ensure_data_dir()
    paths.dashboard_command_file().write_text(action + "\n")
    if _dashboard_pid() is None:
        _dashboard_pid_file().unlink(missing_ok=True)
        child_pid = _spawn_dashboard()
        _dashboard_pid_file().write_text(str(child_pid))
    print(f"dashboard action requested: {action}")
    return 0


def _run_dashboard() -> int:
    from .tray import run_tray

    pid_file = _dashboard_pid_file()
    existing = _dashboard_pid()
    if existing is not None and existing != os.getpid():
        print(f"dashboard already open (pid {existing})")
        return 0
    paths.ensure_data_dir()
    pid_file.write_text(str(os.getpid()))
    try:
        return run_tray(mode="dashboard")
    finally:
        try:
            if int(pid_file.read_text().strip()) == os.getpid():
                pid_file.unlink()
        except (OSError, ValueError):
            pass


def _plugin_status() -> int:
    document, status, _ = actions.snapshot()
    pending = sorted(status.pending, key=lambda dose: dose.when)
    print(
        json.dumps(
            {
                "color": status.color,
                "next": pending[0].clock if pending else "",
                "taken": status.taken,
                "total": status.total,
                "low": status.low_count,
                "wizard": document.wizard_done,
            }
        )
    )
    return 0


def _print_status() -> int:
    from . import engine, tick

    document, status, history = actions.snapshot()
    print(f"data file : {paths.medicines_file()}")
    print(f"wizard    : {'done' if document.wizard_done else 'PENDING — reminders disabled'}")
    for line in tick.describe(status):
        print(line)
    seven = engine.adherence(document.medicines, status.now, history, 7)
    thirty = engine.adherence(document.medicines, status.now, history, 30)
    print(f"adherence : 7d={'—' if seven is None else str(seven) + '%'} "
          f"30d={'—' if thirty is None else str(thirty) + '%'}")
    for name, days in engine.streaks(document.medicines, status.now, history).items():
        print(f"streak    : {name}: {days} day(s)")
    return 0


def _test_notify() -> int:
    command = [
        "notify-send",
        "-a", paths.APP_NAME,
        "-u", "normal",
        "-i", "appointment-soon",
        "-h", "string:x-canonical-private-synchronous:medkit-selftest",
        "-p",
        "MedKit test notification",
        "If you can read this, the notification path works.",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print("$ " + " ".join(command))
    print(f"exit={result.returncode} notification-id={result.stdout.strip() or 'none'}")
    if result.stderr.strip():
        print(f"stderr={result.stderr.strip()}")
    return 0 if result.returncode == 0 else 1


def _print_lines(lines) -> int:
    for line in lines:
        print(line)
    return 0


def _open_uri(uri: str) -> int:
    """Hand a tel:/ URI to whatever handles calls here. Offline by nature."""
    if not uri:
        print("error: no phone number saved for that target", file=sys.stderr)
        return 1
    for command in (["xdg-open", uri], ["gio", "open", uri]):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError:
            continue
        if result.returncode == 0:
            print(f"dialling {uri}")
            return 0
    # No handler on this machine: printing the number still beats nothing.
    print(uri.replace("tel:", ""))
    return 0


def _snapshot():
    return actions.snapshot()


def _cmd_interactions() -> int:
    from . import interactions

    document, _, _ = _snapshot()
    active = [m for m in document.medicines if m.active]
    findings = interactions.check(active)
    summary = interactions.summarize(findings)
    if not findings:
        print("No interactions found between your active medicines.")
    else:
        for finding in findings:
            print(f"[{finding.severity.upper()}] {finding.a} + {finding.b}")
            print(f"    {finding.effect}")
            print(f"    → {finding.advice}")
            print()
        print(
            f"{summary['total']} finding(s): "
            f"{summary['bySeverity']['severe']} severe, "
            f"{summary['bySeverity']['moderate']} moderate, "
            f"{summary['bySeverity']['mild']} mild"
        )
    print("\nThis is not medical advice.")
    from .knowledge import load

    book = load()
    print(f"Local knowledge snapshot {book.updated}. Sources: {'; '.join(book.sources)}")
    return 0


def _cmd_food() -> int:
    from . import food

    document, _, _ = _snapshot()
    active = [m for m in document.medicines if m.active]
    rows = food.check(active)
    if not rows:
        print("No food guidance matched your active medicines.")
    for row in rows:
        print(f"{row['name']}" + (f" ({row['generic']})" if row["generic"] else ""))
        if row["timing"]:
            print(f"    when: {row['timing']}")
        for rule in row["rules"]:
            print(f"    [{rule['severity']}] {rule['label']}")
            print(f"        {rule['tip']}")
            if rule["timing"]:
                print(f"        {rule['timing']}")
        if not row["rules"] and not row["timing"]:
            print("    no specific food guidance")
        print()
    print("This is not medical advice.")
    return 0


def _cmd_pregnancy() -> int:
    from . import pregnancy, store

    document, _, _ = _snapshot()
    active = [m for m in document.medicines if m.active]
    state = pregnancy.check(active, store.load_profile())
    print(f"Profile status: {state['statusLabel']}")
    if not state["active"]:
        print("Set the status first: --profile-set status pregnant|breastfeeding|trying")
        return 0
    if not state["findings"]:
        print("Nothing on your list is flagged for this status.")
    for finding in state["findings"]:
        print(f"[{finding['risk'].upper()}] {finding['name']} ({finding['generic']})")
        print(f"    {finding['note']}")
        print(f"    safer: {finding['alternative']}")
        print()
    print(state["consult"])
    print("This is not medical advice.")
    return 0


def _cmd_missed() -> int:
    from . import missed

    document, status, history = _snapshot()
    state = missed.summary(document.medicines, status.now, history)
    if state["missed"]:
        print(f"{state['count']} dose(s) missed today:")
        for item in state["missed"]:
            print(f"  - {item['clock']} {item['name']} ({item['minutesLate']} min late)")
        print()
    else:
        print("Nothing missed today.")
    print("Protocol:")
    for row in state["protocols"]:
        print(f"  {row['name']} [{row['sourceLabel']}]")
        print(f"    {row['text']}")
    print()
    print("This is not medical advice.")
    return 0


def _cmd_refill_status() -> int:
    from . import refill, store

    document, _, _ = _snapshot()
    state = refill.check(document.medicines, profile=store.load_profile())
    if not state["medicines"]:
        print("No medicine has a pill count yet — enter counts in the wizard.")
        return 0
    for row in state["medicines"]:
        left = "unknown" if row["daysLeft"] is None else f"{row['daysLeft']} day(s)"
        flag = " OUT" if row["out"] else (" ← refill now" if row["warn"] else "")
        print(f"{row['name']}: {row['stock']} pills ({left}) @ {row['perDay']}/day{flag}")
    pharmacy = state["pharmacy"]
    if pharmacy.get("phone"):
        print(f"\nPharmacy: {pharmacy.get('name', '')} {pharmacy['phone']}".rstrip())
        print("  dial with: medkit --call-pharmacy")
    return 0


def _cmd_adherence() -> int:
    from . import adherence

    document, _, history = _snapshot()
    now = None
    day = adherence.daily(document.medicines, history, now)
    week = adherence.weekly(document.medicines, history, now)
    month = adherence.monthly(document.medicines, history, now)
    streak = adherence.overall_streak(document.medicines, history, now)
    print(f"today   {day['label']} ({day['taken']}/{day['scheduled']})")
    print(f"7 days  {week['label']}  threshold {week['threshold']}%"
          + ("  BELOW TARGET" if week["below"] else ""))
    for line in week["graph"]:
        print("  " + line)
    print(f"30 days {month['label']}  ({month['missed']} missed, "
          f"{month['belowDays']} day(s) under {month['threshold']}%)")
    print(f"streak  {streak['label']}")
    return 0


def _cmd_report(period: str) -> int:
    from . import reporting

    document, _, history = _snapshot()
    data = reporting.render(period, document.medicines, history)
    return _print_lines(data["lines"])


def _cmd_review(export: bool = False, done: bool = False) -> int:
    from . import review

    document, _, history = _snapshot()
    state = review.status()
    if done:
        data = review.report(document.medicines, history)
        review.mark_reviewed()
        print(f"review recorded — next one due {review.status()['nextLabel']}")
        return 0
    if export:
        data, path = review.full_review(document.medicines, history)
        print(f"PDF written: {path}")
        print(f"next review: {review.status()['nextLabel']}")
        return 0
    print(f"last review : {state['lastLabel']}")
    print(f"next review : {state['nextLabel']}")
    print(f"status      : {'DUE NOW' if state['due'] else 'scheduled'}")
    print(f"interval    : every {state['intervalMonths']} months")
    dupes = review.duplicates(document.medicines)
    if dupes:
        print(f"\nduplicates to ask about ({len(dupes)}):")
        for row in dupes:
            print(f"  [{row['severity']}] {row['text']}")
    else:
        print("\nno duplicates found")
    print("\nExport for the appointment: medkit --review-export")
    print("This is not medical advice.")
    return 0


def _cmd_emergency(export: str | None = None) -> int:
    from . import emergency

    document, _, _ = _snapshot()
    if export == "pdf":
        path = emergency.export_wallet_pdf(document.medicines)
        print(f"written: {path}")
        return 0
    if export == "txt":
        path = emergency.export_wallet(document.medicines)
        print(f"written: {path}")
        return 0
    print(emergency.card_text(document.medicines))
    return 0


def _cmd_emergency_call(target: str) -> int:
    from . import emergency

    wanted = str(target).strip().lower()
    for row in emergency.emergency_numbers():
        if wanted in (row["label"].lower(), "contact" if wanted == "emergency" else "",
                      "doctor" if wanted == "doc" else ""):
            return _open_uri(row["uri"])
    for row in emergency.emergency_numbers():
        if wanted and wanted in row["label"].lower():
            return _open_uri(row["uri"])
    print(f"error: unknown target {target!r} — try: "
          + ", ".join(row["label"] for row in emergency.emergency_numbers()),
          file=sys.stderr)
    return 1


def _cmd_call_pharmacy() -> int:
    from . import emergency

    profile = emergency.profile()
    phone = (profile.get("pharmacy") or {}).get("phone", "")
    if not phone:
        print("error: no pharmacy phone saved — "
              "--profile-set pharmacy 'Name | +20 100 000 0000'", file=sys.stderr)
        return 1
    return _open_uri(emergency.call_uri(phone))


def _cmd_profile(setter: list[str] | None = None, show: bool = False) -> int:
    from . import emergency

    if setter:
        key, value = setter
        emergency.set_field(key, value)
        print(f"{key} saved")
        return 0
    data = emergency.profile()
    print(f"name              : {data.get('name', '')}")
    print(f"blood type        : {data.get('blood_type', '') or 'not set'}")
    print(f"allergies         : {', '.join(data.get('allergies', [])) or 'none recorded'}")
    print(f"chronic conditions: {', '.join(data.get('conditions', [])) or 'none recorded'}")
    for key in ("emergency_contact", "doctor", "pharmacy"):
        entry = data.get(key) or {}
        print(f"{key:<17}: {entry.get('name', '')} {entry.get('phone', '')}".rstrip())
    print(f"status            : {data.get('status', 'none')}")
    print(f"updated           : {data.get('updated', 'never')}")
    print(f"\nAll of it stays in {paths.profile_file()}")
    return 0


def _cmd_side_effect(args) -> int:
    from . import sideeffects

    if args.side_effect_list:
        rows = sideeffects.all_records()
        if not rows:
            print("No side effects logged.")
        for row in rows:
            print(f"{row.get('date', '')}  [{row.get('severity', '')}] "
                  f"{row.get('medicine', '')} ({row.get('dose', '')}) — {row.get('effect', '')}")
        repeats = sideeffects.repeat_alerts()
        if repeats:
            print("\nReported 3 or more times:")
            for row in repeats:
                print(f"  {row['effect']} with {row['medicine']} — {row['count']} times "
                      f"(worst {row['worst']}, last {row['last']})")
        week = sideeffects.weekly_summary()
        print("\nWeekly summary:")
        print("  " + "\n  ".join(week["lines"]))
        return 0

    name, effect, severity = args.side_effect
    try:
        record = sideeffects.log(name, effect, severity)
    except sideeffects.SideEffectError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"logged: [{record['severity']}] {record['medicine']} ({record['dose']}) "
          f"— {record['effect']} at {record['ts']}")
    for repeat in sideeffects.repeat_alerts():
        if repeat["medicine"] == name:
            print(f"REPEAT: {repeat['effect']} now reported {repeat['count']} times — "
                  "tell your doctor or pharmacist.")
    print("This is not medical advice.")
    return 0


def _cmd_vital(args) -> int:
    from . import vitals

    parts = list(args.vital)
    action = parts[0].lower() if parts else "list"
    if action in ("list", "show"):
        rows = vitals.readings(30)
        if not rows:
            print("No readings yet. Try: medkit --vital add bp 120/80")
            return 0
        for row in rows[-40:]:
            value = str(row["value"])
            if row.get("value2") is not None:
                value = f"{row['value']}/{row['value2']}"
            print(f"{row['date']} {row['clock']}  {row['label']}: {value} {row['unit']} "
                  f"({row['source']})")
        return 0
    if action == "import":
        if len(parts) < 2:
            print("error: --vital import FILE.csv", file=sys.stderr)
            return 1
        try:
            result = vitals.import_csv(parts[1])
        except (OSError, vitals.VitalError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"imported {result['imported']} reading(s), skipped {result['skipped']}")
        return 0
    if action == "add":
        if len(parts) < 3:
            print("error: --vital add KIND VALUE   (e.g. add bp 120/80)", file=sys.stderr)
            return 1
        try:
            record = vitals.add(parts[1], " ".join(parts[2:]))
        except vitals.VitalError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        value = str(record["value"])
        if record.get("value2") is not None:
            value = f"{record['value']}/{record['value2']}"
        print(f"recorded: {record['label']} {value} {record['unit']} at {record['clock']}")
        return 0
    print(f"error: unknown --vital action {action!r} (add|list|import)", file=sys.stderr)
    return 1


def _cmd_set_generic(pair: list[str]) -> int:
    name, generic = pair
    document = store.load_medicines()
    medicine = document.by_name(name)
    if medicine is None:
        print(f"error: unknown medicine: {name}", file=sys.stderr)
        return 1
    medicine.generic = generic
    store.save_medicines(document)
    print(f"{name}: generic set to {generic}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ["MEDKIT_DATA_DIR"] = os.path.expanduser(args.data_dir)
    paths.ensure_data_dir()

    if args.headless_test:
        from . import selftest

        return selftest.run()
    if args.test_notify:
        return _test_notify()
    if args.tick:
        from . import art, tick

        art.purge_stale()
        report = tick.run_tick(dispatch=not args.dry_run)
        stamp = report.now.strftime("%Y-%m-%d %H:%M:%S")
        print(f"medkit tick {stamp}")
        for line in report.lines:
            print(f"  {line}")
        if report.ids:
            print(f"  notification ids: {', '.join(report.ids)}")
        if report.suppressed and args.dry_run:
            print(f"  already sent today: {len(report.suppressed)}")
        return 0
    if args.vault_summary:
        from . import vault

        appended, message = vault.append_daily_summary()
        print(("appended: " if appended else "skipped: ") + message)
        return 0
    if args.take:
        try:
            print(actions.mark_taken(args.take))
        except actions.ActionError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0
    if args.skip:
        try:
            print(actions.mark_skipped(args.skip))
        except actions.ActionError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0
    if args.set_count:
        name, raw_count = args.set_count
        if not raw_count.isdigit():
            print("error: COUNT must be a non-negative integer", file=sys.stderr)
            return 1
        try:
            print(actions.set_count(name, int(raw_count)))
        except actions.ActionError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0
    if args.refill is not None:
        try:
            message = (
                actions.refill_one(args.refill)
                if args.refill
                else actions.refill_low()
            )
        except actions.ActionError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(message)
        return 0
    if args.add_medicine:
        return _request_dashboard_action("add")
    if args.edit:
        return _request_dashboard_action(f"edit:{args.edit}")
    if args.delete:
        return _request_dashboard_action(f"delete:{args.delete}")
    if args.dashboard_toggle:
        return _dashboard_toggle()
    if args.plugin_panel:
        from . import art, panel_data

        art.purge_stale()
        print(json.dumps(panel_data.payload(), ensure_ascii=False))
        return 0
    if args.notify_due:
        from . import panel_data

        print(json.dumps(panel_data.notify_due(args.notify_due), ensure_ascii=False))
        return 0
    if args.plugin_status:
        return _plugin_status()
    if args.status:
        return _print_status()
    if args.interactions:
        return _cmd_interactions()
    if args.food:
        return _cmd_food()
    if args.pregnancy:
        return _cmd_pregnancy()
    if args.missed:
        return _cmd_missed()
    if args.refill_status:
        return _cmd_refill_status()
    if args.adherence:
        return _cmd_adherence()
    if args.report:
        return _cmd_report(args.report)
    if args.review:
        return _cmd_review()
    if args.review_export:
        return _cmd_review(export=True)
    if args.review_done:
        return _cmd_review(done=True)
    if args.emergency_card:
        return _cmd_emergency()
    if args.emergency_export is not None:
        return _cmd_emergency(export=args.emergency_export)
    if args.emergency_call:
        return _cmd_emergency_call(args.emergency_call)
    if args.call_pharmacy:
        return _cmd_call_pharmacy()
    if args.profile_set:
        return _cmd_profile(setter=args.profile_set)
    if args.profile_show:
        return _cmd_profile()
    if args.side_effect or args.side_effect_list:
        return _cmd_side_effect(args)
    if args.vital:
        return _cmd_vital(args)
    if args.set_generic:
        return _cmd_set_generic(args.set_generic)

    from .tray import run_tray

    if args.dashboard:
        return _run_dashboard()
    if args.wizard:
        return run_tray(mode="wizard")
    return run_tray(mode="gui")


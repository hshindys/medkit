from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time

from . import actions, paths


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
    group.add_argument("--wizard", action="store_true", help="open the pill-count wizard")
    group.add_argument("--tick", action="store_true", help="evaluate the schedule and notify")
    group.add_argument("--vault-summary", action="store_true", help="append today's summary to the health vault")
    group.add_argument("--headless-test", action="store_true", help="run the logic self test")
    group.add_argument("--test-notify", action="store_true", help="fire one real test notification")
    group.add_argument("--take", metavar="NAME", help="mark the next dose as taken")
    group.add_argument("--skip", metavar="NAME", help="mark the next dose as skipped")
    group.add_argument("--set-count", nargs=2, metavar=("NAME", "COUNT"), help="set a pill count")
    group.add_argument("--status", action="store_true", help="print today's status")
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
        from . import tick

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
    if args.dashboard_toggle:
        return _dashboard_toggle()
    if args.plugin_status:
        return _plugin_status()
    if args.status:
        return _print_status()

    from .tray import run_tray

    if args.dashboard:
        return _run_dashboard()
    if args.wizard:
        return run_tray(mode="wizard")
    return run_tray(mode="gui")


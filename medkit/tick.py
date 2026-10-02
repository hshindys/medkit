from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import art, engine
from .engine import DayStatus, Dose, TAB_LABELS
from .notify import Notice, Notifier
from .store import append_history, load_medicines, read_history


@dataclass
class TickReport:
    now: datetime
    status: DayStatus
    fired: list[Notice] = field(default_factory=list)
    suppressed: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    setup_pending: bool = False
    lines: list[str] = field(default_factory=list)


def pill_icon(name: str, size: int = 64) -> str:
    """This medicine's own pill image, or "" when it cannot be rendered."""
    try:
        return str(art.pill_png(name, size))
    except Exception:  # art needs PIL; a missing icon must never block a reminder
        return ""


def _dose_body(dose: Dose) -> str:
    parts = [f"due {dose.clock}"]
    if dose.medicine.dose:
        parts.append(dose.medicine.dose)
    if dose.medicine.notes:
        parts.append(dose.medicine.notes)
    return " · ".join(parts)


def build_notices(status: DayStatus, now: datetime) -> list[Notice]:
    if not status.wizard_done:
        return []
    day = now.date().isoformat()
    notices: list[Notice] = []

    for medicine in status.emergency_out:
        contacts = f"\nContacts: {medicine.emergency_contacts}" if medicine.emergency_contacts else ""
        notices.append(
            Notice(
                key=f"emo|{medicine.name}|{day}",
                kind="emergency",
                medicine=medicine.name,
                summary=f"EMERGENCY: {medicine.name} OUT OF STOCK",
                body=f"0 pills remaining. Refill now.{contacts}",
                urgency="critical",
                icon=pill_icon(medicine.name),
                emergency_line=(
                    f"{now.isoformat(timespec='seconds')} OUT-OF-STOCK "
                    f"{medicine.name} dose={medicine.dose or 'n/a'} remaining=0\n"
                ),
            )
        )

    for dose in status.overdue:
        minutes = dose.minutes_overdue(now)
        notices.append(
            Notice(
                key=f"ovd|{dose.medicine.name}|{day}|{dose.clock}",
                kind="overdue",
                medicine=dose.medicine.name,
                summary=f"OVERDUE: {dose.medicine.name}",
                body=f"Was due {dose.clock}, {minutes} min ago · {_dose_body(dose)}",
                urgency="critical",
                icon=pill_icon(dose.medicine.name),
            )
        )

    for dose in status.doses:
        if dose.taken:
            continue
        for number in range(1, engine.MAX_REMINDERS + 1):
            fire_at = dose.when + engine.REMINDER_STEP * (number - 1)
            if now < fire_at or now >= dose.when + engine.OVERDUE_AFTER:
                continue
            title = (
                f"Time for {dose.medicine.name}"
                if number == 1
                else f"Reminder {number}/{engine.MAX_REMINDERS}: {dose.medicine.name}"
            )
            notices.append(
                Notice(
                    key=f"rem|{dose.medicine.name}|{day}|{dose.clock}|{number}",
                    kind="reminder",
                    medicine=dose.medicine.name,
                    summary=title,
                    body=_dose_body(dose),
                    urgency="normal",
                    icon=pill_icon(dose.medicine.name),
                )
            )

    for medicine in status.low:
        contacts = (
            f"\nEmergency contacts: {medicine.emergency_contacts}"
            if medicine.is_emergency and medicine.emergency_contacts
            else ""
        )
        notices.append(
            Notice(
                key=f"rsk|{medicine.name}|{day}",
                kind="restock",
                medicine=medicine.name,
                summary=f"RESTOCK: {medicine.name}",
                body=(
                    f"Only {medicine.stock} pill(s) left "
                    f"(refill at {medicine.refill_at}).{contacts}"
                ),
                urgency="critical",
                icon=pill_icon(medicine.name),
            )
        )
    return notices


def build_tab_notices(status: DayStatus, now: datetime, tab: str) -> list[Notice]:
    """One notice for the doses in a panel tab that are due or overdue now.

    The bar panel calls this when you open a tab, so the screen says what that
    window of the day still owes you without your reading every card. Keyed per
    dose per day, so reopening the same tab stays silent.
    """
    if not status.wizard_done or tab not in engine.TABS:
        return []
    day = now.date().isoformat()
    notices: list[Notice] = []
    for dose in status.doses:
        if dose.taken or dose.tab != tab or dose.when > now:
            continue
        overdue = dose.is_overdue(now)
        minutes = dose.minutes_overdue(now)
        label = TAB_LABELS.get(tab, tab)
        lead = f"Was due {dose.clock}, {minutes} min ago · " if overdue else f"Due {dose.clock} · "
        notices.append(
            Notice(
                key=f"tab|{tab}|{dose.medicine.name}|{day}|{dose.clock}",
                kind="overdue" if overdue else "reminder",
                medicine=dose.medicine.name,
                summary=(
                    f"OVERDUE: {dose.medicine.name}"
                    if overdue
                    else f"Time for {dose.medicine.name}"
                ),
                body=f"{label} tab · {lead}{_dose_body(dose)}",
                urgency="critical" if overdue else "normal",
                icon=pill_icon(dose.medicine.name),
            )
        )
    return notices


def run_tick(dispatch: bool = True, now: datetime | None = None) -> TickReport:
    moment = now or datetime.now().astimezone()
    document = load_medicines()
    history = read_history()
    status = engine.evaluate(document.medicines, moment, history, document.wizard_done)
    report = TickReport(now=moment, status=status)

    if not document.wizard_done:
        report.setup_pending = True
        report.lines.append("setup pending: enter pill counts to enable reminders")
        return report

    notifier = Notifier(dispatch=dispatch)
    for notice in build_notices(status, moment):
        if not notifier.fire(notice):
            continue
        report.fired.append(notice)
        if notice.kind == "restock":
            append_history("restock", notice.medicine, moment)
        report.lines.append(f"notified[{notice.urgency}] {notice.summary}")

    report.suppressed = notifier.suppressed
    report.ids = notifier.ids
    if not report.fired:
        report.lines.append(f"nothing new due ({status.taken}/{status.total} taken)")
    return report


def describe(status: DayStatus) -> list[str]:
    rows = [
        f"color={status.color} ({engine.COLOR_LABELS[status.color]})",
        f"doses today: {status.taken}/{status.total} taken",
    ]
    for dose in status.doses:
        state = "taken" if dose.taken else ("OVERDUE" if dose.is_overdue(status.now) else "pending")
        rows.append(f"  {dose.label} [{state}]")
    if status.low:
        rows.append("low stock: " + ", ".join(f"{m.name}={m.stock}" for m in status.low))
    if status.emergency_issues:
        rows.append(
            "emergency: " + ", ".join(f"{m.name}={m.stock}" for m in status.emergency_issues)
        )
    return rows

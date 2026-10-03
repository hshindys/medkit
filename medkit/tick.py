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
    hint = _food_hint(dose.medicine)
    if hint:
        parts.append(hint)
    return " · ".join(parts)


def _food_hint(medicine) -> str:
    """The one line about eating around this tablet, when it is short enough
    to sit inside a notification without pushing the buttons off screen."""
    try:
        from . import food

        timing = food.tips_for(medicine)["timing"]
    except Exception:  # a missing knowledge file must never block a reminder
        return ""
    return timing if 0 < len(timing) <= 80 else ""


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


def build_health_notices(
    document, history, now: datetime
) -> list[Notice]:
    """Everything the safety net says that is not "your dose is due".

    Each kind is keyed so a 60-second timer cannot turn one problem into a
    hundred notifications; the state file prunes keys after 30 days, which is
    also the right rhythm for re-surfacing a standing interaction.
    """
    from . import (
        adherence,
        food,
        interactions,
        missed,
        pregnancy,
        refill,
        review,
        sideeffects,
    )

    if not document.wizard_done:
        return []
    medicines = document.medicines
    active = [m for m in medicines if m.active]
    notices: list[Notice] = []

    # 1 — drug–drug interactions, NSAID against blood-pressure tablets first.
    findings = interactions.check(active)
    for finding in findings:
        if finding.severity == "mild":
            continue  # shown in the panel, not worth interrupting for
        notices.append(
            Notice(
                key=f"int|{finding.a}|{finding.b}",
                kind="interaction",
                medicine=finding.a,
                summary=f"INTERACTION [{finding.severity.upper()}]: {finding.a} + {finding.b}",
                body=f"{finding.effect}\n\n{finding.advice}\n\nThis is not medical advice.",
                urgency="critical" if finding.severity == "severe" else "normal",
                icon="dialog-warning",
            )
        )

    # 2 — food that fights a medicine (grapefruit, vitamin K, dairy...) and the
    # meal timing that must not be skipped (sulfonylurea + meal).
    for row in food.alerts(active):
        if row["severity"] != "severe":
            continue  # moderate food advice waits in the panel
        is_timing = row.get("relation") == "with"
        notices.append(
            Notice(
                key=f"fud|{row['medicine']}|{row.get('label', row['tip'])[:40]}",
                kind="food",
                medicine=row["medicine"],
                summary=(
                    f"TAKE WITH FOOD: {row['medicine']}"
                    if is_timing
                    else f"FOOD WARNING: {row['medicine']}"
                ),
                body=f"{row.get('label', '')} — {row['tip']}\n\nThis is not medical advice.",
                urgency="critical" if is_timing else "normal",
                icon="dialog-information",
            )
        )

    # 3 — adherence under the target, judged on yesterday.
    adherence_state = adherence.alert_state(active, history, now)
    if adherence_state["firing"]:
        notices.append(
            Notice(
                key=f"adx|{adherence_state['date']}",
                kind="adherence",
                summary=f"ADHERENCE {adherence_state['label']} — below target",
                body=(
                    f"Yesterday {adherence_state['label']} of doses were taken "
                    f"(target {adherence_state['threshold']}%). Take the next dose on time "
                    "to start rebuilding the streak."
                ),
                urgency="normal",
                icon="appointment-soon",
            )
        )

    # 4 — running out, three days ahead of the box emptying.
    refills = refill.check(active, now)
    week = now.isocalendar()[:2]
    for row in refills["warnings"] + refills["out"]:
        if row["out"]:
            body = "Zero pills left. Refill now."
        else:
            body = (
                f"{row['stock']} pills left — about {row['daysLeft']} day(s) at "
                f"{row['perDay']}/day. Runs out {row['runOut']}."
            )
        phone = row.get("pharmacyPhone") or ""
        if phone:
            body += f"\nPharmacy: {row['pharmacyName'] or 'call'} {phone}"
        notices.append(
            Notice(
                key=f"rfl|{row['name']}|{week[0]}-{week[1]}",
                kind="refill",
                medicine=row["name"],
                summary=(
                    f"OUT OF STOCK: {row['name']}"
                    if row["out"]
                    else f"REFILL SOON: {row['name']} ({row['daysLeft']} days left)"
                ),
                body=body,
                urgency="critical" if row["out"] else "normal",
                icon=pill_icon(row["name"]),
            )
        )

    # 5 — a day that has slipped, not a single dose.
    missed_state = missed.summary(active, now, history)
    if missed_state["alert"]:
        names = ", ".join(item["name"] for item in missed_state["missed"][:4])
        notices.append(
            Notice(
                key=f"msd|{now.date().isoformat()}",
                kind="missed",
                summary=f"{missed_state['count']} DOSES MISSED TODAY",
                body=(
                    f"{names}.\n\n"
                    + (missed_state["forMissed"][0]["text"] if missed_state["forMissed"] else "")
                    + "\n\nThis is not medical advice."
                ),
                urgency="critical",
                icon="dialog-warning",
            )
        )

    # 6 — the same side effect, reported for the third time.
    for repeat in sideeffects.repeat_alerts():
        notices.append(
            Notice(
                key=f"sef|{repeat['medicine']}|{repeat['effectKey']}",
                kind="sideeffect",
                medicine=repeat["medicine"],
                summary=f"REPEATED SIDE EFFECT: {repeat['effect']}",
                body=(
                    f"{repeat['medicine']} ({repeat['dose'] or 'dose not recorded'}) — "
                    f"reported {repeat['count']} times, first {repeat['first']}, "
                    f"worst {repeat['worst']}.\n\n"
                    "Report this to your doctor or pharmacist at the next visit.\n"
                    "This is not medical advice."
                ),
                urgency="critical" if repeat["worst"] == "severe" else "normal",
                icon="dialog-warning",
            )
        )

    # 7 — the quarterly therapy review.
    state = review.status(now)
    if state["due"]:
        when = state["nextLabel"] if state["next"] else "now"
        notices.append(
            Notice(
                key=f"rvw|{when}",
                kind="review",
                summary="MEDICATION REVIEW DUE",
                body=(
                    f"Every {state['intervalMonths']} months: review every medicine, dose and "
                    "duplicate with your doctor. Export the PDF from the MedKit panel "
                    "(Reports → Export PDF).\n\nThis is not medical advice."
                ),
                urgency="normal",
                icon="x-office-calendar",
            )
        )

    # 8 — a medicine that should not be taken right now.
    pregnancy_state = pregnancy.check(active)
    for finding in pregnancy_state["flagged"]:
        notices.append(
            Notice(
                key=f"prg|{finding['name']}",
                kind="pregnancy",
                medicine=finding["name"],
                summary=f"{finding['risk'].upper()}: {finding['name']} in pregnancy",
                body=(
                    f"{finding['note']}\n\nSafer option: {finding['alternative']}\n\n"
                    f"{pregnancy_state['consult']}\nThis is not medical advice."
                ),
                urgency="critical" if finding["risk"] == "contraindicated" else "normal",
                icon="dialog-error",
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

    for notice in build_health_notices(document, history, moment):
        if not notifier.fire(notice):
            continue
        report.fired.append(notice)
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

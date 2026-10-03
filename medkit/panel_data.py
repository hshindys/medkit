from __future__ import annotations

from datetime import datetime

from . import actions, art, engine, tick
from .engine import COLOR_LABELS, TAB_LABELS, TABS, Dose
from .notify import Notice, Notifier

# Tab accents. Four hues that stay readable on the panel background and stay
# apart from each other, so a glance at the tab row says which window of the
# day you are looking at before you read a single label.
TAB_COLORS = {
    "morning": "#f59e0b",
    "evening": "#38bdf8",
    "night": "#a78bfa",
    "emergency": "#ef4444",
}

# One glyph per window of the day, and a pill for the as-needed shelf. The
# codes are Nerd Font ones (md-* for the day cycle, md-pill for emergency),
# so they render in the theme's monospace font.
TAB_ICONS = {
    "morning": "󰖨",
    "evening": "󰖛",
    "night": "󰖔",
    "emergency": "󰐂",
}

STATE_COLORS = {
    "taken": "#22c55e",
    "due": "#f59e0b",
    "overdue": "#ef4444",
    "pending": "#64748b",
}

STATE_LABELS = {
    "taken": "taken",
    "due": "due now",
    "overdue": "overdue",
    "pending": "later",
}


def dose_state(dose: Dose, now: datetime) -> str:
    if dose.taken:
        return "taken"
    if dose.is_overdue(now):
        return "overdue"
    if dose.is_due_now(now):
        return "due"
    return "pending"


def _pill(name: str) -> dict:
    """Colour and shape for a medicine — the two things that make one card
    look unlike the next."""
    color, shape = art.style_for(name)
    return {
        "color": color,
        "shape": shape,
        "icon": str(art.pill_gif(name, 40)),
        "iconLarge": str(art.pill_gif(name, 64)),
        "iconPng": str(art.pill_png(name, 64)),
    }


def health_payload(
    moment: datetime | None = None,
    snapshot: tuple | None = None,
) -> dict:
    """The safety, health and report half of the panel.

    Everything here is read from local files only — no network, so the panel
    still fills in with the Wi-Fi off and, more importantly, so nothing about
    your medicines leaves this machine.
    """
    from . import (
        adherence,
        emergency,
        food,
        interactions,
        missed,
        pregnancy,
        refill,
        reporting,
        review,
        sideeffects,
        store,
        vitals,
    )
    from .knowledge import load

    moment = moment or datetime.now().astimezone()
    document, status, history = snapshot or actions.snapshot(moment)
    active = [medicine for medicine in document.medicines if medicine.active]
    book = load()
    profile = store.load_profile()

    findings = interactions.check(active, book)
    food_rows = food.check(active, book)
    pregnancy_state = pregnancy.check(active, profile, book)
    week = adherence.weekly(active, history, moment)
    day = adherence.daily(active, history, moment)
    streak = adherence.overall_streak(active, history, moment)
    month = adherence.monthly(active, history, moment)
    effects = sideeffects.since(30, moment)
    repeats = sideeffects.repeat_alerts()
    vitals_chart = vitals.chart(14, moment)
    correlation = vitals.correlate(active, history, 30, moment)
    vital_summary = vitals.summarize(7, moment)
    missed_state = missed.summary(active, moment, history, book)
    refills = refill.check(active, moment, profile)
    review_state = {**review.status(moment), "duplicates": review.duplicates(active)}
    card = emergency.card(active)
    numbers = emergency.emergency_numbers()

    return {
        "disclaimer": book.disclaimer,
        "sources": book.sources,
        "updated": book.updated,
        "interactions": {
            "items": [finding.to_dict() for finding in findings],
            "count": len(findings),
            "nsaidBp": [
                finding.to_dict() for finding in findings if finding.is_nsaid_bp
            ],
            "worst": interactions.summarize(findings)["worst"],
        },
        "food": {
            "medicines": food_rows,
            "alerts": food.alerts(active, book),
        },
        "pregnancy": pregnancy_state,
        "adherence": {
            "daily": day,
            "weekly": week,
            "monthly": month,
            "streak": streak,
            "threshold": adherence.ADHERENCE_THRESHOLD,
        },
        "sideEffects": {
            "recent": effects[-20:],
            "count": len(effects),
            "repeats": repeats,
            "week": sideeffects.weekly_summary(moment),
        },
        "vitals": {
            "chart": vitals_chart,
            "correlation": correlation,
            "summary": vital_summary,
        },
        "missed": missed_state,
        "refills": refills,
        "review": review_state,
        "reports": {
            "weekly": reporting.weekly(active, history, moment),
            "monthly": reporting.monthly(active, history, moment),
        },
        "emergency": {**card, "numbers": numbers},
        "profile": profile,
    }


def payload(now: datetime | None = None) -> dict:
    moment = now or datetime.now().astimezone()
    document, status, history = actions.snapshot(moment)

    doses: list[dict] = []
    counts = {tab: {"total": 0, "taken": 0, "due": 0, "overdue": 0, "pending": 0} for tab in TABS}
    for dose in status.doses:
        state = dose_state(dose, moment)
        tab = dose.tab
        if tab in counts:
            counts[tab]["total"] += 1
            counts[tab][state] += 1
        entry = {
            "name": dose.medicine.name,
            "dose": dose.medicine.dose,
            "clock": dose.clock,
            "hour": dose.hour,
            "tab": tab,
            "state": state,
            "stateLabel": STATE_LABELS[state],
            "stateColor": STATE_COLORS[state],
            "takenAt": dose.taken_at.strftime("%H:%M") if dose.taken_at else "",
            "overdueMin": dose.minutes_overdue(moment) if not dose.taken else 0,
            "notes": dose.medicine.notes,
            "category": dose.medicine.category,
            "days": dose.medicine.days,
            "stock": dose.medicine.stock,
            "refillAt": dose.medicine.refill_at,
            "low": dose.medicine.is_low(),
            "out": dose.medicine.is_out(),
            "tabColor": TAB_COLORS.get(tab, "#64748b"),
        }
        entry.update(_pill(dose.medicine.name))
        doses.append(entry)

    pending = sorted(status.pending, key=lambda dose: dose.when)
    next_dose = engine.next_pending_dose(status)

    medicines = []
    for medicine in document.medicines:
        clock = medicine.parsed_times()[0].hour if medicine.parsed_times() else 12
        tab = engine.tab_for(medicine, clock)
        item = {
            "name": medicine.name,
            "dose": medicine.dose,
            "times": list(medicine.times),
            "stock": medicine.stock,
            "refillAt": medicine.refill_at,
            "low": medicine.is_low(),
            "out": medicine.is_out(),
            "category": medicine.category,
            "days": medicine.days,
            "notes": medicine.notes,
            "active": medicine.active,
            "tab": tab,
            "tabColor": TAB_COLORS.get(tab, "#64748b"),
        }
        item.update(_pill(medicine.name))
        medicines.append(item)

    tabs = []
    for tab in TABS:
        data = counts[tab]
        tabs.append(
            {
                "id": tab,
                "label": TAB_LABELS[tab],
                "color": TAB_COLORS[tab],
                "icon": TAB_ICONS[tab],
                **data,
            }
        )

    return {
        "version": 2,
        "now": moment.strftime("%H:%M"),
        "wizard": document.wizard_done,
        "color": status.color,
        "colorLabel": COLOR_LABELS.get(status.color, status.color),
        "taken": status.taken,
        "total": status.total,
        "pending": len(pending),
        "next": next_dose.clock if next_dose else "",
        "nextName": next_dose.medicine.name if next_dose else "",
        "low": status.low_count,
        "emergency": len(status.emergency_issues),
        "adherence7": engine.adherence(document.medicines, moment, history, 7),
        "adherence30": engine.adherence(document.medicines, moment, history, 30),
        "tabs": tabs,
        "doses": doses,
        "medicines": medicines,
        "health": health_payload(moment, (document, status, history)),
    }


def notify_due(tab: str) -> dict:
    """Fire the due/overdue notice for one tab, once per dose per day."""
    now = datetime.now().astimezone()
    document, status, _ = actions.snapshot(now)
    notices: list[Notice] = tick.build_tab_notices(status, now, tab)
    if not notices or not document.wizard_done:
        return {"fired": 0, "suppressed": 0, "tab": tab}
    notifier = Notifier(dispatch=True)
    fired = 0
    for notice in notices:
        if notifier.fire(notice):
            fired += 1
    return {"fired": fired, "suppressed": len(notifier.suppressed), "tab": tab}

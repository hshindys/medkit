from __future__ import annotations

from datetime import datetime

from . import engine, paths
from .actions import snapshot
from .store import load_state, save_state


def build_summary(now: datetime, wizard_done: bool) -> str:
    document, status, history = snapshot(now)
    adherence_7 = engine.adherence(document.medicines, now, history, 7)
    adherence_30 = engine.adherence(document.medicines, now, history, 30)
    lines = [f"## {now.date().isoformat()} — MedKit"]
    if not wizard_done:
        lines.append("- إعداد عدّ الأقراص لم يكتمل بعد")
        return "\n".join(lines) + "\n"

    lines.append(f"- جرعات اليوم: {status.taken}/{status.total}")
    if adherence_7 is not None:
        lines.append(f"- الالتزام (7 أيام): {adherence_7}%")
    if adherence_30 is not None:
        lines.append(f"- الالتزام (30 يومًا): {adherence_30}%")
    if status.low:
        low = ", ".join(f"{medicine.name} ({medicine.stock})" for medicine in status.low)
        lines.append(f"- مخزون منخفض: {low}")
    else:
        lines.append("- مخزون منخفض: لا يوجد")
    if status.emergency_issues:
        lines.append(
            "- طوارئ: " + ", ".join(medicine.name for medicine in status.emergency_issues)
        )
    return "\n".join(lines) + "\n"


def append_daily_summary(now: datetime | None = None) -> tuple[bool, str]:
    moment = now or datetime.now().astimezone()
    key = f"vault|{moment.date().isoformat()}"
    state = load_state()
    if key in state.get("sent", {}):
        return False, f"summary for {moment.date()} already appended"
    if not paths.VAULT_FILE.parent.is_dir():
        return False, f"vault folder missing: {paths.VAULT_FILE.parent}"
    document, _, _ = snapshot(moment)
    text = build_summary(moment, document.wizard_done)
    with paths.VAULT_FILE.open("a", encoding="utf-8") as handle:
        handle.write("\n" + text)
    state.setdefault("sent", {})[key] = moment.isoformat(timespec="seconds")
    save_state(state)
    return True, f"appended {len(text.splitlines())} lines to {paths.VAULT_FILE.name}"

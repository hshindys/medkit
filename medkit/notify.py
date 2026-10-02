from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import paths
from .store import load_state, save_state

URGENCIES = ("low", "normal", "critical")


@dataclass(frozen=True)
class Notice:
    key: str
    kind: str
    summary: str
    body: str
    medicine: str = ""
    urgency: str = "normal"
    emergency_line: str | None = None
    # Path to this medicine's own pill image. Notifications that carry it are
    # recognisable at a glance — the same capsule, tablet or bottle the panel
    # draws on the card — instead of one generic clock for every reminder.
    icon: str = ""

    def validate(self) -> None:
        if self.urgency not in URGENCIES:
            raise ValueError(f"unsupported urgency: {self.urgency}")
        if self.kind not in ("reminder", "overdue", "restock", "emergency"):
            raise ValueError(f"unsupported kind: {self.kind}")


def _slug(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


class Notifier:
    def __init__(self, dispatch: bool = True) -> None:
        self.dispatch = dispatch
        self.state = load_state()
        self.fired: list[Notice] = []
        self.suppressed: list[str] = []
        self.ids: list[str] = []

    def seen(self, key: str) -> bool:
        return key in self.state.get("sent", {})

    def fire(self, notice: Notice) -> bool:
        notice.validate()
        if self.seen(notice.key):
            self.suppressed.append(notice.key)
            return False
        notification_id = ""
        if self.dispatch:
            notification_id = self._send(notice)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        self.state.setdefault("sent", {})[notice.key] = stamp
        save_state(self.state)
        self.fired.append(notice)
        self.ids.append(notification_id)
        if notice.emergency_line is not None:
            paths.ensure_data_dir()
            with paths.emergency_log().open("a", encoding="utf-8") as handle:
                handle.write(notice.emergency_line)
        return True

    def _send(self, notice: Notice) -> str:
        icon = notice.icon if notice.icon and Path(notice.icon).exists() else ""
        if not icon:
            icon = "dialog-warning" if notice.urgency == "critical" else "appointment-soon"
        command = [
            "notify-send",
            "-a",
            paths.APP_NAME,
            "-u",
            notice.urgency,
            "-i",
            icon,
            "-h",
            f"string:x-canonical-private-synchronous:{_slug(notice.key)}",
            "-p",
            notice.summary,
            notice.body,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError:
            return ""
        return result.stdout.strip()

from __future__ import annotations

import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

from . import actions, paths, render
from .dashboard import Dashboard
from .engine import DayStatus
from .wizard import Wizard

REFRESH_SECONDS = 15
APP_ID = "com.medkit.Tray"
DASHBOARD_APP_ID = "com.medkit.Dashboard"


class TrayApp(Gtk.Application):
    def __init__(self, mode: str = "gui") -> None:
        flags = getattr(
            Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE
        )
        app_id = DASHBOARD_APP_ID if mode == "dashboard" else APP_ID
        super().__init__(application_id=app_id, flags=flags)
        self.mode = mode
        self.indicator: AyatanaAppIndicator3.Indicator | None = None
        self.dashboard: Dashboard | None = None
        self.wizard: Wizard | None = None
        self.menu_signature: str | None = None
        self.ever_activated = False

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.hold()
        if self.mode != "dashboard":
            self._ensure_indicator()
        self._refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._refresh_tick)
        if self.mode == "dashboard":
            # A CLI request (e.g. `medkit --add-medicine`) travels as a
            # one-shot file; pick it up promptly instead of on the 15s tick.
            GLib.timeout_add(400, self._poll_pending_command)

    def do_activate(self) -> None:
        if self.mode != "dashboard":
            self._ensure_indicator()
        self._refresh()
        document, _, _ = actions.snapshot()
        if self.mode == "wizard":
            self.open_wizard()
        elif self.mode == "dashboard":
            self.open_dashboard()
            self._poll_pending_command()
        elif not self.ever_activated and not document.wizard_done:
            self.open_wizard()
        elif not self.ever_activated:
            self._spawn_dashboard("--dashboard")
        self.ever_activated = True

    def _ensure_indicator(self) -> None:
        if self.indicator is not None:
            return
        indicator = AyatanaAppIndicator3.Indicator.new(
            "MedKit",
            render.icon_name("neutral"),
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_icon_theme_path(str(paths.icon_dir()))
        indicator.set_title("MedKit")
        indicator.connect("activate", self._on_indicator_activate)
        indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator = indicator

    def _on_indicator_activate(self, _indicator, _x: int, _y: int) -> None:
        self._spawn_dashboard("--dashboard-toggle")

    def _spawn_dashboard(self, argument: str) -> None:
        subprocess.Popen(
            [str(paths.medkit_bin()), argument],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _refresh_tick(self) -> bool:
        self._refresh()
        return True

    def _refresh(self) -> None:
        if self.dashboard is not None and self.dashboard.get_mapped():
            self.dashboard.refresh()
        if self.indicator is None:
            return
        _, status, _ = actions.snapshot()
        color = render.icon_name(status.color, status.low_count)
        render.icon_file(status.color, status.low_count)
        self.indicator.set_icon_full(color, f"MedKit: {status.color}")
        title = "MedKit"
        if status.low_count:
            title = f"MedKit — {status.low_count} low on stock"
        if not status.wizard_done:
            title = "MedKit — setup required"
        self.indicator.set_title(title)
        self._rebuild_menu(status)

    def _signature(self, status: DayStatus) -> str:
        pending = [dose.label for dose in sorted(status.pending, key=lambda d: d.when)]
        return f"{status.wizard_done}|{'|'.join(pending)}"

    def _rebuild_menu(self, status: DayStatus) -> None:
        if self.indicator is None:
            return
        signature = self._signature(status)
        if signature == self.menu_signature:
            return
        self.menu_signature = signature

        menu = Gtk.Menu()
        today = Gtk.MenuItem(label="Today's status")
        today.connect("activate", lambda *_: self._spawn_dashboard("--dashboard-toggle"))
        menu.append(today)

        mark = Gtk.MenuItem(label="Mark dose taken")
        submenu = Gtk.Menu()
        if not status.wizard_done:
            pending_item = Gtk.MenuItem(label="Run setup first")
            pending_item.set_sensitive(False)
            submenu.append(pending_item)
        elif not status.pending:
            pending_item = Gtk.MenuItem(label="Nothing pending today")
            pending_item.set_sensitive(False)
            submenu.append(pending_item)
        else:
            for dose in sorted(status.pending, key=lambda item: item.when):
                item = Gtk.MenuItem(label=dose.label)
                item.connect("activate", self._on_mark_taken, dose.medicine.name)
                submenu.append(item)
        mark.set_submenu(submenu)
        menu.append(mark)

        manage = Gtk.MenuItem(label="Manage medicines")
        manage.connect("activate", lambda *_: self._spawn_dashboard("--dashboard-toggle"))
        menu.append(manage)

        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: self.quit())
        menu.append(quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def _on_mark_taken(self, _item: Gtk.MenuItem, name: str) -> None:
        try:
            actions.mark_taken(name)
        except actions.ActionError:
            return
        self._refresh()
        if self.dashboard is not None:
            self.dashboard.refresh()

    def open_dashboard(self) -> None:
        if self.dashboard is None:
            self.dashboard = Dashboard(application=self)
            self.dashboard.connect("destroy", self._on_dashboard_destroyed)
            if self.mode == "dashboard":
                self.dashboard.connect("destroy", lambda *_: self.quit())
        self.dashboard.refresh()
        self.dashboard.present()

    def _poll_pending_command(self) -> bool:
        path = paths.dashboard_command_file()
        try:
            raw = path.read_text().strip()
        except OSError:
            return True
        if not raw:
            return True
        try:
            path.unlink()
        except OSError:
            pass
        if raw == "add":
            self.open_dashboard()
            if self.dashboard is not None:
                self.dashboard.show_add_dialog()
        elif raw.startswith("edit:"):
            name = raw.split(":", 1)[1].strip()
            self.open_dashboard()
            if self.dashboard is not None and name:
                self.dashboard.show_edit_dialog(name)
        elif raw.startswith("delete:"):
            name = raw.split(":", 1)[1].strip()
            self.open_dashboard()
            if self.dashboard is not None and name:
                self.dashboard.show_delete_confirm(name)
        return True

    def _on_dashboard_destroyed(self, window: Gtk.Window) -> None:
        if self.dashboard is window:
            self.dashboard = None

    def open_wizard(self) -> None:
        if self.wizard is not None and self.wizard.get_mapped():
            self.wizard.present()
            return
        self.wizard = Wizard(None, on_done=self._wizard_done)
        self.wizard.connect("destroy", self._on_wizard_destroyed)
        self.wizard.present()

    def _on_wizard_destroyed(self, window: Gtk.Window) -> None:
        if self.wizard is window:
            self.wizard = None

    def _wizard_done(self) -> None:
        if self.wizard is not None:
            self.wizard.destroy()
        self.wizard = None
        self._refresh()


def run_tray(mode: str = "gui") -> int:
    app = TrayApp(mode=mode)
    return app.run([sys.argv[0]])

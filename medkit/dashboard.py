from __future__ import annotations

from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from . import actions, art, engine
from .engine import COLOR_LABELS, DayStatus, Dose
from .models import Medicine
from .store import MedicineFile

CSS = """
window {
  background-color: #0f1219;
  color: #e6ebf5;
  font-family: "Inter", "Cantarell", "DejaVu Sans";
}
label { color: #e6ebf5; }
.title { font-size: 20px; font-weight: bold; color: #f5f8ff; }
.subtitle { color: #94a3bd; font-size: 13px; }
.section { font-size: 12px; font-weight: bold; color: #6d7d99; }
.muted { color: #8794ab; }
.hint { color: #7dd3fc; font-size: 12px; padding: 6px 20px; }
.hint.hint-error { color: #fca5a5; }
.hint.hint-ok { color: #86efac; }
.card {
  background-color: #161b26;
  border: 1px solid #232c3d;
  border-radius: 16px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}
.card.card-danger {
  background-color: #1d1420;
  border-color: #5b1e2c;
}
.row {
  background-color: #1b2231;
  border: 1px solid #27303f;
  border-radius: 14px;
}
.row:hover { background-color: #212a3b; border-color: #3d4c66; }
.row.row-off { opacity: 0.5; }
.accent-taken { background-color: #22c55e; border-radius: 4px; }
.accent-due { background-color: #f59e0b; border-radius: 4px; }
.accent-late { background-color: #ef4444; border-radius: 4px; }
.accent-idle { background-color: #3f4a63; border-radius: 4px; }
.chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: bold;
}
.chip.chip-time { background-color: #1e293b; color: #7dd3fc; }
.chip.chip-taken { background-color: #14532d; color: #4ade80; }
.chip.chip-due { background-color: #7c4a06; color: #fde68a; }
.chip.chip-late { background-color: #7f1d1d; color: #fecaca; }
.chip.chip-idle { background-color: #232a3a; color: #8794ab; }
.chip.chip-danger { background-color: #7f1d1d; color: #fca5a5; }
.chip.chip-stock { background-color: #1e293b; color: #93c5fd; }
.badge { padding: 4px 13px; border-radius: 999px; font-size: 12px; font-weight: bold; }
.badge.badge-taken { background-color: #14532d; color: #4ade80; }
.badge.badge-due { background-color: #7c4a06; color: #fde68a; }
.badge.badge-late { background-color: #7f1d1d; color: #fecaca; }
.badge.badge-idle { background-color: #232a3a; color: #8794ab; }
button {
  background-color: #232c3d;
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  color: #cbd5e1;
  border: 1px solid #303b50;
  border-radius: 8px;
  padding: 3px 8px;
  font-weight: bold;
  font-size: 11px;
}
button:hover { background-color: #2c374b; }
button:disabled { opacity: 0.45; }
.btn-refill { background-color: #f59e0b; color: #14181f; border-color: #f59e0b; }
.btn-refill:hover { background-color: #fbbf24; }
.btn-take { background-color: #16a34a; color: #ffffff; border-color: #16a34a; }
.btn-take:hover { background-color: #22c55e; }
.btn-skip { background-color: #1b212f; color: #8794ab; border-color: #2c3546; }
.btn-skip:hover { background-color: #242c3d; color: #cbd5e1; }
.btn-edit { background-color: #2563eb; color: #ffffff; border-color: #2563eb; }
.btn-edit:hover { background-color: #3b82f6; }
.btn-del { background-color: #2a1520; color: #f87171; border-color: #5b1e2c; }
.btn-del:hover { background-color: #3a1a26; color: #fecaca; }
.btn-add { background-color: #7c3aed; color: #ffffff; border-color: #7c3aed; }
.btn-add:hover { background-color: #8b5cf6; }
.btn-danger { background-color: #dc2626; color: #ffffff; border-color: #dc2626; }
.btn-danger:hover { background-color: #ef4444; }
.btn-ghost { background-color: transparent; color: #94a3b8; border-color: #2c374b; }
.btn-ghost:hover { background-color: #1b2231; color: #e6ebf5; }
progressbar { min-height: 12px; border-radius: 9px; background-color: #1b2231; }
progressbar trough { min-height: 12px; border-radius: 9px; background-color: #1b2231; }
progressbar progress { min-height: 12px; border-radius: 9px; background-color: #22c55e; }
progressbar.lvl-amber progress { background-color: #f59e0b; }
progressbar.lvl-red progress { background-color: #ef4444; }
entry {
  background-color: #121722;
  border: 1px solid #2c374b;
  border-radius: 9px;
  color: #e6ebf5;
  padding: 7px 10px;
}
entry:focus { border-color: #3b82f6; }
combobox {
  background-color: #121722;
  border: 1px solid #2c374b;
  border-radius: 9px;
  padding: 4px 8px;
}
combobox button, spinbutton button, spinbutton button:hover {
  background: transparent;
  border: none;
  box-shadow: none;
}
scrollbar trough { background-color: #121722; }
scrollbar slider { background-color: #2c374b; border-radius: 6px; min-width: 10px; }
"""

STATE_LABELS = {
    "taken": "taken ✔",
    "late": "overdue",
    "due": "due now",
    "idle": "pending",
}


def _clear(container: Gtk.Container) -> None:
    for child in container.get_children():
        container.remove(child)


def _add_class(widget: Gtk.Widget, css: str) -> None:
    context = widget.get_style_context()
    for name in css.split():
        context.add_class(name)


def _label(text: str, css: str = "", ltr: bool = False, ellipsize: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    if css:
        _add_class(label, css)
    if ltr:
        label.set_direction(Gtk.TextDirection.LTR)
    if ellipsize:
        label.set_ellipsize(Pango.EllipsizeMode.END)
    return label


def _button(text: str, handler, css: str = "") -> Gtk.Button:
    button = Gtk.Button(label=text)
    if css:
        _add_class(button, css)
    button.connect("clicked", handler)
    return button


def _state_of(dose: Dose, status: DayStatus) -> str:
    if dose.taken:
        return "taken"
    if dose.is_overdue(status.now):
        return "late"
    if dose.is_due_now(status.now):
        return "due"
    return "idle"


class Dashboard(Gtk.Window):
    def __init__(self, application: Gtk.Application | None = None) -> None:
        super().__init__(title="MedKit")
        if application is not None:
            self.set_application(application)
        self.set_default_size(880, 940)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(shell)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.body.set_border_width(18)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.body)
        self.scroll = scroll
        shell.pack_start(scroll, True, True, 0)

        self.hint = _label("", "hint")
        self.hint.set_no_show_all(True)
        shell.pack_end(self.hint, False, False, 0)
        self._hint_source: int | None = None

        self.refresh()

    def refresh(self) -> None:
        document, status, history = actions.snapshot()
        scroll_value = self.scroll.get_vadjustment().get_value()
        _clear(self.body)
        for widget in (
            self._header(document, status),
            self._emergency(document),
            self._doses(status),
            self._medicines(document, status),
            self._adherence(document, history),
            self._toolbar(document),
        ):
            self.body.pack_start(widget, False, False, 0)
        self.show_all()
        self.scroll.get_vadjustment().set_value(scroll_value)
        if self._hint_source is None:
            self.hint.hide()

    def _say(self, message: str, error: bool = False) -> None:
        self.hint.set_text(message)
        context = self.hint.get_style_context()
        context.remove_class("hint-error")
        context.remove_class("hint-ok")
        context.add_class("hint-error" if error else "hint-ok")
        self.hint.show()
        if self._hint_source is not None:
            GLib.source_remove(self._hint_source)
        self._hint_source = GLib.timeout_add_seconds(6, self._hide_hint)

    def _hide_hint(self) -> bool:
        self.hint.hide()
        self._hint_source = None
        return False

    def _card(self, title: str, css: str = "card") -> tuple[Gtk.Box, Gtk.Box]:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        _add_class(card, css)
        card.set_border_width(14)
        if title:
            card.pack_start(_label(title, "section"), False, False, 0)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.pack_start(content, False, False, 0)
        return card, content

    def _pill(self, name: str, size: int = 30) -> Gtk.Widget:
        try:
            animation = GdkPixbuf.PixbufAnimation.new_from_file(str(art.pill_gif(name, size)))
            image = Gtk.Image.new_from_animation(animation)
        except Exception:
            image = Gtk.Label(label="●")
            image.set_markup(f'<span foreground="{art.color_for(name)}">●</span>')
        image.set_valign(Gtk.Align.CENTER)
        return image

    def _chip(self, text: str, css: str) -> Gtk.Label:
        label = _label(text, f"chip {css}")
        label.set_valign(Gtk.Align.CENTER)
        return label

    def _header(self, document: MedicineFile, status: DayStatus) -> Gtk.Widget:
        card, content = self._card("")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        dot = Gtk.Label()
        dot.set_markup(f'<span foreground="{_hex(status.color)}" size="26pt">●</span>')
        dot.set_valign(Gtk.Align.START)
        head.pack_start(dot, False, False, 0)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = _label(f"MedKit · {datetime.now():%A %d %B %Y}", "title", ellipsize=True)
        title.set_max_width_chars(24)
        titles.pack_start(title, False, False, 0)
        if not document.wizard_done:
            subtitle = "Setup needed — enter your real pill counts to enable reminders"
        else:
            subtitle = f"{status.taken}/{status.total} doses taken · {COLOR_LABELS[status.color]}"
            if status.low_count:
                subtitle += f" · {status.low_count} low on stock"
        sub = _label(subtitle, "subtitle", ellipsize=True)
        titles.pack_start(sub, False, False, 0)
        head.pack_start(titles, True, True, 0)
        content.pack_start(head, False, False, 0)

        bar = Gtk.ProgressBar()
        bar.set_fraction(0.0 if status.total == 0 else status.taken / status.total)
        _add_class(bar, _bar_class(status))
        content.pack_start(bar, False, False, 0)
        return card

    def _emergency(self, document: MedicineFile) -> Gtk.Widget:
        card, content = self._card("EMERGENCY", "card card-danger")
        emergencies = [medicine for medicine in document.medicines if medicine.is_emergency]
        if not emergencies:
            content.pack_start(
                _label("No emergency medicine defined yet.", "muted"), False, False, 0
            )
        for medicine in emergencies:
            content.pack_start(self._stock_row(medicine), False, False, 0)
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_row.pack_start(
            _button("EMERGENCY", lambda *_: EmergencyWindow(self).show_all(), "btn-danger"),
            True,
            True,
            0,
        )
        actions_row.pack_start(
            _button("＋ Add medicine", self._add_emergency, "btn-add"),
            True,
            True,
            0,
        )
        content.pack_start(actions_row, False, False, 0)
        return card

    def _doses(self, status: DayStatus) -> Gtk.Widget:
        card, content = self._card("TODAY'S DOSES")
        if not status.doses:
            content.pack_start(_label("No doses scheduled today.", "muted"), False, False, 0)
        for dose in status.doses:
            content.pack_start(self._dose_row(dose, status), True, True, 0)
        return card

    def _dose_row(self, dose: Dose, status: DayStatus) -> Gtk.Widget:
        state = _state_of(dose, status)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_border_width(10)

        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        accent.set_size_request(5, -1)
        _add_class(accent, f"accent-{state}")
        box.pack_start(accent, False, True, 0)

        box.pack_start(self._pill(dose.medicine.name, 30), False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        line.pack_start(self._chip(dose.clock, "chip-time"), False, False, 0)
        line.pack_start(_label(dose.medicine.name, ellipsize=True), False, True, 0)
        if dose.medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(_label(dose.medicine.dose, ltr=True), False, False, 0)
        info.pack_start(line, False, False, 0)

        state_text = STATE_LABELS[state]
        if state == "late":
            state_text = f"overdue {dose.minutes_overdue(status.now)}m"
        line2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if dose.medicine.notes:
            line2.pack_start(
                _label(dose.medicine.notes, "muted", ellipsize=True), True, True, 0
            )
        badge = _label(state_text, f"badge badge-{state}")
        badge.set_valign(Gtk.Align.CENTER)
        line2.pack_end(badge, False, False, 0)
        info.pack_start(line2, False, True, 0)
        box.pack_start(info, True, True, 0)

        if not dose.taken:
            actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            name = dose.medicine.name
            actions_box.pack_end(
                _button("Skip", lambda *_: self._act(actions.mark_skipped, name), "btn-skip"),
                False,
                False,
                0,
            )
            actions_box.pack_end(
                _button("Take", lambda *_: self._act(actions.mark_taken, name), "btn-take"),
                False,
                False,
                0,
            )
            box.pack_end(actions_box, False, False, 0)

        wrap = Gtk.EventBox()
        wrap.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        _add_class(wrap, "row")
        if dose.taken:
            _add_class(wrap, "row-off")
        wrap.set_tooltip_text("Log this dose with Take, or ignore it with Skip")
        wrap.add(box)
        return wrap

    def _medicines(self, document: MedicineFile, status: DayStatus) -> Gtk.Widget:
        card, content = self._card("MEDICINES")
        if status.low:
            content.pack_start(
                _button(
                    f"↻ Refill low ({len(status.low)})",
                    lambda *_: self._refill(),
                    "btn-refill",
                ),
                False,
                False,
                0,
            )
        for medicine in document.medicines:
            content.pack_start(self._medicine_row(medicine), True, True, 0)
        if not document.medicines:
            content.pack_start(_label("No medicines yet.", "muted"), False, False, 0)
        if status.low:
            for medicine in status.low:
                content.pack_start(
                    _label(
                        f"low stock: {medicine.name} — {medicine.stock} left "
                        f"(refill at {medicine.refill_at})",
                        "muted",
                    ),
                    False,
                    False,
                    0,
                )
        content.pack_start(
            _button("＋ Add medicine", lambda *_: self._edit_medicine(None), "btn-add"),
            False,
            False,
            0,
        )
        return card

    def _medicine_row(self, medicine: Medicine) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_border_width(10)

        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        accent.set_size_request(5, -1)
        _add_class(accent, f"accent-{self._stock_state(medicine)}")
        box.pack_start(accent, False, True, 0)
        box.pack_start(self._pill(medicine.name, 26), False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        line.pack_start(_label(medicine.name, ellipsize=True), False, True, 0)
        if medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(_label(medicine.dose, ltr=True), False, False, 0)
        if medicine.is_emergency:
            line.pack_start(self._chip("emergency", "chip-danger"), False, False, 0)
        if not medicine.active:
            line.pack_start(self._chip("paused", "chip-idle"), False, False, 0)
        name = medicine.name
        line.pack_end(
            _button("Delete", lambda *_: self._delete_medicine(name), "btn-del"),
            False,
            False,
            0,
        )
        line.pack_end(
            _button("Edit", lambda *_: self._edit_medicine(name), "btn-edit"),
            False,
            False,
            0,
        )
        info.pack_start(line, False, True, 0)

        times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for clock in medicine.times:
            times.pack_start(self._chip(clock, "chip-time"), False, False, 0)
        if medicine.days:
            times.pack_start(self._chip(f"{medicine.days}-day course", "chip-time"), False, False, 0)
        if medicine.notes:
            times.pack_start(_label(medicine.notes, "muted", ellipsize=True), True, True, 0)
        times.pack_end(self._stock_chip(medicine), False, False, 0)
        info.pack_start(times, False, True, 0)
        box.pack_start(info, True, True, 0)

        wrap = Gtk.EventBox()
        wrap.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        _add_class(wrap, "row")
        if not medicine.active:
            _add_class(wrap, "row-off")
        wrap.set_tooltip_text("Edit changes dose, times, stock and notes")
        wrap.add(box)
        return wrap

    def _stock_state(self, medicine: Medicine) -> str:
        if medicine.is_out():
            return "late"
        if medicine.is_low():
            return "due"
        if medicine.stock is None:
            return "idle"
        return "taken"

    def _stock_chip(self, medicine: Medicine) -> Gtk.Label:
        if medicine.stock is None:
            return self._chip("not counted", "chip-idle")
        if medicine.is_out():
            return self._chip("OUT · 0 left", "chip-late")
        if medicine.is_low():
            return self._chip(f"low · {medicine.stock}", "chip-due")
        return self._chip(f"{medicine.stock} pills", "chip-stock")

    def _stock_row(self, medicine: Medicine) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_border_width(8)
        box.pack_start(self._pill(medicine.name, 24), False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        line.pack_start(_label(medicine.name), False, False, 0)
        if medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(_label(medicine.dose, ltr=True), False, False, 0)
        text.pack_start(line, False, False, 0)
        if medicine.emergency_contacts:
            text.pack_start(_label(f"☎ {medicine.emergency_contacts}", "muted"), False, False, 0)
        clocks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for clock in medicine.times:
            clocks.pack_start(self._chip(clock, "chip-time"), False, False, 0)
        text.pack_start(clocks, False, False, 0)
        box.pack_start(text, True, True, 0)
        box.pack_end(self._stock_chip(medicine), False, False, 0)
        if medicine.days:
            box.pack_end(self._chip(f"for {medicine.days} days", "chip-time"), False, False, 0)
        return box

    def _adherence(self, document: MedicineFile, history) -> Gtk.Widget:
        card, content = self._card("ADHERENCE")
        now = datetime.now().astimezone()
        for title, days in (("Last 7 days", 7), ("Last 30 days", 30)):
            value = engine.adherence(document.medicines, now, history, days)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.pack_start(_label(title, "muted"), False, False, 0)
            bar = Gtk.ProgressBar()
            bar.set_hexpand(True)
            bar.set_fraction(0.0 if value is None else max(0.0, min(1.0, value / 100)))
            _add_class(bar, _adh_class(value))
            row.pack_start(bar, True, True, 0)
            row.pack_end(
                _label("—" if value is None else f"{value}%", ltr=True), False, False, 0
            )
            content.pack_start(row, False, False, 0)

        streaks = engine.streaks(document.medicines, now, history)
        if streaks:
            grid = Gtk.Grid(column_spacing=16, row_spacing=6)
            for index, (name, days) in enumerate(streaks.items(), start=1):
                grid.attach(_label(name), 0, index, 1, 1)
                css = "chip chip-taken" if days > 0 else "chip chip-idle"
                grid.attach(_label(f"{days} day streak", css), 1, index, 1, 1)
            content.pack_start(grid, False, False, 0)
        return card

    def _toolbar(self, document: MedicineFile) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        if not document.wizard_done:
            from .wizard import Wizard

            box.pack_start(
                _button("Run pill-count setup", lambda *_: Wizard(self), "btn-add"),
                False,
                False,
                0,
            )
        box.pack_start(
            _button("＋ Add medicine", lambda *_: self._edit_medicine(None), "btn-add"),
            False,
            False,
            0,
        )
        box.pack_end(_button("Close", lambda *_: self.close(), "btn-ghost"), False, False, 0)
        box.pack_end(_button("Refresh", lambda *_: self.refresh(), "btn-ghost"), False, False, 0)
        return box

    def _act(self, handler, name: str) -> None:
        try:
            message = handler(name)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._say(message)
        self.refresh()

    def _refill(self, *_ignored) -> None:
        try:
            message = actions.refill_low(30)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._say(message)
        self.refresh()

    def _edit_medicine(self, name: str | None, *_ignored, emergency: bool = False) -> None:
        document, _, _ = actions.snapshot()
        existing = document.by_name(name) if name else None
        form = MedicineForm(self, existing, emergency=emergency)
        response = form.run()
        medicine = form.value()
        form.destroy()
        if response != Gtk.ResponseType.OK or medicine is None:
            return
        try:
            if existing is None:
                message = actions.add_medicine(medicine)
            else:
                message = actions.update_medicine(existing.name, medicine)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._say(message)
        self.refresh()

    def _add_emergency(self, *_ignored) -> None:
        form = EmergencyAddForm(self)
        response = form.run()
        medicine = form.value()
        form.destroy()
        if response != Gtk.ResponseType.OK or medicine is None:
            return
        try:
            message = actions.add_medicine(medicine)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._say(message)
        self.refresh()

    def _delete_medicine(self, name: str, *_ignored) -> None:
        confirm = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete {name}?",
        )
        confirm.format_secondary_text("Its dose history stays in the log.")
        answer = confirm.run()
        confirm.destroy()
        if answer != Gtk.ResponseType.YES:
            return
        try:
            message = actions.delete_medicine(name)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._say(message)
        self.refresh()


def _hex(color: str) -> str:
    return {
        "neutral": "#64748b",
        "green": "#22c55e",
        "amber": "#f59e0b",
        "red": "#ef4444",
    }.get(color, "#64748b")


def _bar_class(status: DayStatus) -> str:
    if status.color == "red":
        return "lvl-red"
    if status.color == "amber":
        return "lvl-amber"
    return ""


def _adh_class(value: float | None) -> str:
    if value is None or value >= 70:
        return ""
    if value >= 40:
        return "lvl-amber"
    return "lvl-red"


class EmergencyWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window | None = None) -> None:
        super().__init__(title="MedKit — EMERGENCY")
        self.set_default_size(480, 380)
        if parent is not None:
            self.set_transient_for(parent)
        self._parent_win = parent

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        shell.set_border_width(16)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        head.pack_start(_label("EMERGENCY MEDICINES", "section"), True, True, 0)
        head.pack_end(_button("＋ Add medicine", self._add_medicine, "btn-add"), False, False, 0)
        shell.pack_start(head, False, False, 0)
        self._rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        shell.pack_start(self._rows, True, True, 0)
        shell.pack_end(_button("Close", lambda *_: self.close(), "btn-ghost"), False, False, 0)
        self.add(shell)
        self._rebuild()

    def _add_medicine(self, *_ignored) -> None:
        if self._parent_win is not None:
            self._parent_win._add_emergency()
            self._rebuild()

    def _rebuild(self) -> None:
        for child in self._rows.get_children():
            self._rows.remove(child)
        document, _, _ = actions.snapshot()
        emergencies = [medicine for medicine in document.medicines if medicine.is_emergency]
        if not emergencies:
            self._rows.pack_start(
                _label("No emergency medicine defined.", "muted"), False, False, 0
            )
        for medicine in emergencies:
            self._rows.pack_start(self._card(medicine), False, False, 0)
        self._rows.show_all()

    def _card(self, medicine: Medicine) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        _add_class(card, "card card-danger")
        card.set_border_width(10)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        head.pack_start(self._pill(medicine.name), False, False, 0)
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        name_box.pack_start(_label(medicine.name), False, False, 0)
        detail = medicine.dose or "—"
        name_box.pack_start(_label(detail, "muted", ltr=True), False, False, 0)
        if medicine.times:
            for clock in medicine.times:
                name_box.pack_start(self._chip(clock, "chip-time"), False, False, 0)
        head.pack_start(name_box, True, True, 0)
        state = "OUT OF STOCK" if medicine.is_out() else ("LOW" if medicine.is_low() else "ok")
        chip_css = "chip-late" if medicine.is_out() else ("chip-due" if medicine.is_low() else "chip-taken")
        head.pack_end(self._chip(state, chip_css), False, False, 0)
        stock = "not counted" if medicine.stock is None else str(medicine.stock)
        head.pack_end(self._chip(f"{stock} pills", "chip-stock"), False, False, 0)
        if medicine.days:
            head.pack_end(self._chip(f"for {medicine.days} days", "chip-time"), False, False, 0)
        card.pack_start(head, False, False, 0)
        if medicine.notes:
            card.pack_start(_label(f"Note: {medicine.notes}", "muted"), False, False, 0)
        card.pack_start(
            _label(f"Contacts: {medicine.emergency_contacts or '—'}", "muted"),
            False,
            False,
            0,
        )
        return card

    def _pill(self, name: str) -> Gtk.Widget:
        try:
            animation = GdkPixbuf.PixbufAnimation.new_from_file(str(art.pill_gif(name, 26)))
            image = Gtk.Image.new_from_animation(animation)
        except Exception:
            image = Gtk.Label(label="●")
            image.set_markup(f'<span foreground="{art.color_for(name)}">●</span>')
        image.set_valign(Gtk.Align.CENTER)
        return image

    def _chip(self, text: str, css: str) -> Gtk.Label:
        label = _label(text, f"chip {css}")
        label.set_valign(Gtk.Align.CENTER)
        return label


class EmergencyAddForm(Gtk.Dialog):
    """Quick EMERGENCY add: medicine name, time and course length."""

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            title="Add emergency medicine",
            transient_for=parent,
            modal=True,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(380, 240)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10, column_homogeneous=False)
        grid.set_border_width(14)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("e.g. Rescue tablet")
        self.times_entry = Gtk.Entry()
        self.times_entry.set_placeholder_text("08:00, 20:00")
        self.days_entry = Gtk.SpinButton.new_with_range(0, 365, 1)

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Medicine", self.name_entry),
            ("Time (HH:MM, comma separated)", self.times_entry),
            ("For how many days (0 = ongoing)", self.days_entry),
        ]
        for index, (title, widget) in enumerate(rows):
            grid.attach(_label(title, "muted"), 0, index, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, index, 1, 1)
        self.get_content_area().pack_start(grid, True, True, 0)
        self.show_all()

    def value(self) -> Medicine | None:
        times = [
            chunk.strip()
            for chunk in self.times_entry.get_text().replace(";", ",").split(",")
            if chunk.strip()
        ]
        return Medicine(
            name=self.name_entry.get_text().strip(),
            times=times,
            days=int(self.days_entry.get_value()),
            category="emergency",
        )


class MedicineForm(Gtk.Dialog):
    def __init__(
        self, parent: Gtk.Window, medicine: Medicine | None, emergency: bool = False
    ) -> None:
        super().__init__(
            title="Medicine" if medicine else "New medicine",
            transient_for=parent,
            modal=True,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(440, 500)
        self.medicine = medicine

        grid = Gtk.Grid(column_spacing=12, row_spacing=10, column_homogeneous=False)
        grid.set_border_width(14)

        self.name_entry = Gtk.Entry()
        self.dose_entry = Gtk.Entry()
        self.times_entry = Gtk.Entry()
        self.stock_entry = Gtk.Entry()
        self.refill_entry = Gtk.SpinButton.new_with_range(0, 999, 1)
        self.days_entry = Gtk.SpinButton.new_with_range(0, 365, 1)
        self.notes_entry = Gtk.Entry()
        self.contacts_entry = Gtk.Entry()
        self.category_combo = Gtk.ComboBoxText()
        for category in ("normal", "emergency"):
            self.category_combo.append_text(category)
        self.active_toggle = Gtk.CheckButton(label="active")
        self.active_toggle.set_active(True)

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Name", self.name_entry),
            ("Dose", self.dose_entry),
            ("Times (HH:MM, comma separated)", self.times_entry),
            ("Stock pills (empty = not counted)", self.stock_entry),
            ("Refill at", self.refill_entry),
            ("Course days (0 = ongoing)", self.days_entry),
            ("Notes", self.notes_entry),
            ("Category", self.category_combo),
            ("Emergency contacts", self.contacts_entry),
            ("", self.active_toggle),
        ]
        for index, (title, widget) in enumerate(rows):
            if title:
                grid.attach(_label(title, "muted"), 0, index, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, index, 1, 1)
        self.get_content_area().pack_start(grid, True, True, 0)

        if medicine is not None:
            self.name_entry.set_text(medicine.name)
            self.dose_entry.set_text(medicine.dose)
            self.times_entry.set_text(", ".join(medicine.times))
            if medicine.stock is not None:
                self.stock_entry.set_text(str(medicine.stock))
            self.refill_entry.set_value(medicine.refill_at)
            self.days_entry.set_value(medicine.days)
            self.notes_entry.set_text(medicine.notes)
            self.contacts_entry.set_text(medicine.emergency_contacts)
            self.category_combo.set_active(0 if medicine.category == "normal" else 1)
            self.active_toggle.set_active(medicine.active)
        else:
            self.days_entry.set_value(0)
            self.category_combo.set_active(1 if emergency else 0)
        self.show_all()

    def value(self) -> Medicine | None:
        times = [
            chunk.strip()
            for chunk in self.times_entry.get_text().replace(";", ",").split(",")
            if chunk.strip()
        ]
        stock_text = self.stock_entry.get_text().strip()
        stock = None if stock_text == "" else int(stock_text) if stock_text.isdigit() else -1
        return Medicine(
            name=self.name_entry.get_text().strip(),
            dose=self.dose_entry.get_text().strip(),
            times=times,
            stock=stock,
            refill_at=int(self.refill_entry.get_value()),
            days=int(self.days_entry.get_value()),
            notes=self.notes_entry.get_text().strip(),
            category=self.category_combo.get_active_text() or "normal",
            active=self.active_toggle.get_active(),
            emergency_contacts=self.contacts_entry.get_text().strip(),
        )

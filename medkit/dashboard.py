from __future__ import annotations

from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from . import actions, art, engine
from .engine import COLOR_LABELS, DayStatus, Dose
from .models import Medicine
from .store import MedicineFile, load_medicines, save_medicines

RESPONSE_DELETE = 100

BG0 = "#0a0b0d"
BG1 = "#101114"
BG2 = "#16181c"
BG3 = "#1d2025"
LINE = "#25292f"
FG0 = "#f2f4f7"
FG1 = "#c3c8d0"
FG2 = "#8b919b"
FG3 = "#5a6068"
ACCENT = "#e6e8ec"
ACCENT_DIM = "#9aa0a8"

STATE_OK = FG1
STATE_DUE = FG0
STATE_LATE = FG2
STATE_IDLE = FG3
STATE_COLORS = {
    "taken": STATE_OK,
    "due": STATE_DUE,
    "late": STATE_LATE,
    "idle": STATE_IDLE,
}

CHART_LINE = FG1
CHART_GRID = LINE
CHART_FILL = BG3

TWEEN_TICK_MS = 16
TWEEN_MS = 300
TOAST_MS = 3000
TOAST_MAX = 4
DRAG_TARGET = "text/plain"

CSS = """
window {
  background-color: #101114;
  color: #f2f4f7;
  font-family: "Inter", "Cantarell", "DejaVu Sans";
}
dialog, messagedialog {
  background-color: #0a0b0d;
  color: #f2f4f7;
}
headerbar, headerbar title, headerbar button {
  background-color: #101114;
  background-image: none;
  color: #c3c8d0;
  border: none;
  box-shadow: none;
  text-shadow: none;
}
headerbar { border-bottom: 1px solid #25292f; }
.title { font-size: 20px; font-weight: bold; color: #f2f4f7; }
.subtitle { color: #c3c8d0; font-size: 13px; }
.section { font-size: 11px; font-weight: bold; letter-spacing: 1.4px; color: #8b919b; }
.muted { color: #8b919b; }
.hint { color: #8b919b; font-size: 12px; padding: 6px 20px; }
.hint.hint-error { color: #f2f4f7; font-weight: bold; }
.hint.hint-ok { color: #c3c8d0; }
.card {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 12px;
  padding: 16px;
  box-shadow: none;
}
.card.card-danger {
  background-color: #16181c;
  border: 2px solid #e6e8ec;
  border-radius: 12px;
}
.content-card {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 14px;
  padding: 16px;
  box-shadow: none;
}
.sidebar {
  background-color: #16181c;
  border-right: 1px solid #25292f;
}
.nav-item {
  color: #8b919b;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  transition: background-color 140ms ease, border-color 140ms ease;
}
.nav-item:hover { background-color: #1d2025; color: #c3c8d0; }
.nav-item.active {
  background-color: #1d2025;
  color: #f2f4f7;
  border: 1px solid #25292f;
  border-left-width: 3px;
  border-left-color: #e6e8ec;
}
.row {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 12px;
  transition: background-color 140ms ease, border-color 140ms ease;
}
.row:hover { background-color: #1d2025; border-color: #5a6068; }
.row.row-open { background-color: #1d2025; border-color: #9aa0a8; }
.row.row-off { opacity: 0.5; }
.accent-taken { background-color: #c3c8d0; border-radius: 4px; }
.accent-due { background-color: #f2f4f7; border-radius: 4px; }
.accent-late { background-color: #8b919b; border-radius: 4px; }
.accent-idle { background-color: #5a6068; border-radius: 4px; }
.chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: bold;
  border: 1px solid #25292f;
}
.chip.chip-time { background-color: #16181c; color: #c3c8d0; }
.chip.chip-taken { background-color: #1d2025; color: #c3c8d0; }
.chip.chip-due { background-color: #1d2025; color: #f2f4f7; border-color: #9aa0a8; }
.chip.chip-late { background-color: #16181c; color: #8b919b; border-color: #5a6068; }
.chip.chip-idle { background-color: #16181c; color: #5a6068; }
.chip.chip-danger { background-color: #1d2025; color: #f2f4f7; border-color: #e6e8ec; }
.chip.chip-stock { background-color: #16181c; color: #c3c8d0; }
.chip.chip-out { background-color: #1d2025; color: #f2f4f7; border-color: #e6e8ec; }
.badge {
  padding: 4px 13px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: bold;
  border: 1px solid #25292f;
}
.badge.badge-taken { background-color: #1d2025; color: #c3c8d0; }
.badge.badge-due { background-color: #1d2025; color: #f2f4f7; border-color: #9aa0a8; }
.badge.badge-late { background-color: #16181c; color: #8b919b; border-color: #5a6068; }
.badge.badge-idle { background-color: #16181c; color: #5a6068; }
button {
  background-color: #16181c;
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  color: #c3c8d0;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 4px 10px;
  font-weight: bold;
  font-size: 11px;
  transition: background-color 140ms ease, border-color 140ms ease;
}
button:hover { background-color: #1d2025; border-color: #8b919b; color: #f2f4f7; }
button:focus { border-color: #e6e8ec; box-shadow: none; }
button:disabled { opacity: 0.45; }
.btn-take { background-color: #e6e8ec; color: #0a0b0d; border-color: #e6e8ec; }
.btn-take:hover { background-color: #f2f4f7; border-color: #f2f4f7; color: #0a0b0d; }
.btn-add { background-color: #e6e8ec; color: #0a0b0d; border-color: #e6e8ec; }
.btn-add:hover { background-color: #f2f4f7; border-color: #f2f4f7; color: #0a0b0d; }
.btn-refill { background-color: #1d2025; color: #f2f4f7; border-color: #9aa0a8; }
.btn-refill:hover { background-color: #25292f; border-color: #e6e8ec; color: #f2f4f7; }
.btn-skip { background-color: transparent; color: #8b919b; border-color: #25292f; }
.btn-skip:hover { background-color: #1d2025; border-color: #8b919b; color: #c3c8d0; }
.btn-edit { background-color: #16181c; color: #c3c8d0; border-color: #25292f; }
.btn-edit:hover { background-color: #1d2025; border-color: #8b919b; color: #f2f4f7; }
.btn-del { background-color: #1d2025; color: #f2f4f7; border-color: #8b919b; }
.btn-del:hover { background-color: #1d2025; border-color: #e6e8ec; color: #f2f4f7; }
.btn-danger { background-color: #1d2025; color: #f2f4f7; border: 2px solid #e6e8ec; }
.btn-danger:hover { background-color: #25292f; border-color: #f2f4f7; color: #f2f4f7; }
.btn-ghost { background-color: transparent; color: #8b919b; border-color: #25292f; }
.btn-ghost:hover { background-color: #1d2025; border-color: #8b919b; color: #f2f4f7; }
progressbar { min-height: 12px; border-radius: 9px; background-color: #16181c; border: 1px solid #25292f; color: #c3c8d0; }
progressbar trough { min-height: 12px; border-radius: 9px; background-color: #16181c; }
progressbar progress { min-height: 12px; border-radius: 9px; background-color: #c3c8d0; }
progressbar.lvl-amber progress { background-color: #f2f4f7; }
progressbar.lvl-red progress { background-color: #8b919b; }
entry {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 8px;
  color: #f2f4f7;
  padding: 7px 10px;
  box-shadow: none;
  transition: border-color 140ms ease;
}
entry:focus { border-color: #e6e8ec; box-shadow: none; }
entry selection { background-color: #9aa0a8; color: #0a0b0d; }
combobox {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 4px 8px;
  color: #f2f4f7;
}
combobox button, spinbutton button, spinbutton button:hover {
  background-color: transparent;
  border: none;
  box-shadow: none;
  color: #c3c8d0;
}
spinbutton {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 4px 8px;
  color: #f2f4f7;
}
spinbutton:focus { border-color: #e6e8ec; box-shadow: none; }
spinbutton button:hover { color: #f2f4f7; }
check, radio {
  min-width: 16px;
  min-height: 16px;
  border: 1px solid #5a6068;
  background-color: #16181c;
  background-image: none;
  color: #0a0b0d;
}
check { border-radius: 4px; }
radio { border-radius: 999px; }
check:hover, radio:hover { border-color: #8b919b; }
check:checked, radio:checked {
  background-color: #e6e8ec;
  background-image: none;
  border-color: #e6e8ec;
  color: #0a0b0d;
}
check:indeterminate {
  background-color: #9aa0a8;
  background-image: none;
  border-color: #9aa0a8;
  color: #0a0b0d;
}
.titlebar {
  background-color: #0a0b0d;
  border-bottom: 1px solid #25292f;
  box-shadow: none;
}
tooltip {
  background-color: #1d2025;
  border: 1px solid #5a6068;
  border-radius: 8px;
  color: #f2f4f7;
  padding: 6px 8px;
}
treeview { background-color: #16181c; color: #c3c8d0; }
treeview header { background-color: #1d2025; border-bottom: 1px solid #25292f; }
treeview header button {
  background: transparent;
  border: none;
  box-shadow: none;
  color: #8b919b;
  font-size: 11px;
  font-weight: bold;
  letter-spacing: 1.4px;
}
treeview row { background-color: #16181c; border-bottom: 1px solid #25292f; }
treeview row:hover { background-color: #1d2025; }
treeview row:selected { background-color: #1d2025; color: #f2f4f7; }
scrollbar trough { background-color: #101114; }
scrollbar slider { background-color: #25292f; border-radius: 6px; min-width: 10px; }
scrollbar slider:hover { background-color: #5a6068; }
.timeline { background-color: transparent; }
.detail {
  background-color: #101114;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 10px 12px;
}
.empty-glyph { color: #5a6068; font-size: 30px; }
.empty-line { color: #8b919b; font-size: 12px; }
.toast {
  background-color: #1d2025;
  border: 1px solid #25292f;
  border-radius: 8px;
  color: #f2f4f7;
  font-size: 12px;
  padding: 10px 14px;
}
.toast-stack { background-color: transparent; }
"""

STATE_LABELS = {
    "taken": "taken ✔",
    "late": "! overdue",
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


def _rgb(value: str) -> tuple[float, float, float]:
    digits = value.lstrip("#")
    return (
        int(digits[0:2], 16) / 255.0,
        int(digits[2:4], 16) / 255.0,
        int(digits[4:6], 16) / 255.0,
    )


def _paint(context, value: str, alpha: float = 1.0) -> None:
    """Point the Cairo context at one ramp colour (and nothing else)."""
    red, green, blue = _rgb(value)
    context.set_source_rgba(red, green, blue, alpha)


def _tween(start, end, duration_ms, on_value, on_done=None):
    """GTK has no animation API: drive the value ourselves on GLib ticks.

    Ease-out over `duration_ms`, ~16 ms per tick, and it cancels itself the
    moment it reaches the end — so the caller only has to drop the source id
    it gets back when the widget underneath goes away.
    """
    start = float(start)
    end = float(end)
    if duration_ms <= 0 or abs(end - start) < 1e-9:
        on_value(end)
        if on_done is not None:
            on_done()
        return 0
    begun = GLib.get_monotonic_time()

    def step() -> bool:
        elapsed = (GLib.get_monotonic_time() - begun) / 1000.0
        progress = min(1.0, elapsed / float(duration_ms))
        eased = 1.0 - (1.0 - progress) ** 2
        on_value(start + (end - start) * eased)
        if progress >= 1.0:
            if on_done is not None:
                on_done()
            return False
        return True

    return GLib.timeout_add(TWEEN_TICK_MS, step)


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

        self._query = ""
        self._expanded: str | None = None
        self._details: dict[str, Gtk.Box] = {}
        self._pending: set[str] = set()
        self._tweens: dict[str, int] = {}
        self._last_taken: int | None = None
        self._last_fractions: dict[str, float] = {}
        self._toast_timers: dict[Gtk.Widget, int] = {}
        self._press: tuple | None = None
        self._dragging = False
        self._timeline_points: list[tuple[datetime, str]] = []
        self._timeline_now = datetime.now().astimezone()
        self._clock_source: int | None = None

        overlay = Gtk.Overlay()
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        overlay.add(shell)
        self.add(overlay)

        top_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        top_wrap.set_margin_start(18)
        top_wrap.set_margin_end(18)
        top_wrap.set_margin_top(18)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        _add_class(top, "content-card")
        top.pack_start(_label("TODAY", "section"), False, False, 0)
        self.timeline = self._build_timeline()
        top.pack_start(self.timeline, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search medicines, doses, times, notes")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", self._on_search)
        top.pack_start(self.search, False, False, 0)
        top_wrap.pack_start(top, False, False, 0)
        shell.pack_start(top_wrap, False, False, 0)

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
        self._form_open = False

        self.toasts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        _add_class(self.toasts, "toast-stack")
        self.toasts.set_halign(Gtk.Align.END)
        self.toasts.set_valign(Gtk.Align.END)
        self.toasts.set_margin_end(18)
        self.toasts.set_margin_bottom(18)
        overlay.add_overlay(self.toasts)
        overlay.set_overlay_pass_through(self.toasts, True)

        self._clock_source = GLib.timeout_add_seconds(30, self._redraw_timeline)
        self.connect("destroy", self._on_destroy)

        self.refresh()

    def _on_destroy(self, *_ignored) -> None:
        if self._clock_source is not None:
            GLib.source_remove(self._clock_source)
            self._clock_source = None
        for key in list(self._tweens):
            self._stop_tween(key)
        for revealer in list(self._toast_timers):
            self._forget_toast(revealer)

    def _stop_tween(self, key: str) -> None:
        source = self._tweens.pop(key, None)
        if source:
            GLib.source_remove(source)

    def _start_tween(self, key: str, start, end, on_value, on_done=None) -> None:
        """One live tween per key — starting a new one drops the old one."""
        self._stop_tween(key)

        def finished() -> None:
            self._tweens.pop(key, None)
            if on_done is not None:
                on_done()

        source = _tween(start, end, TWEEN_MS, on_value, finished)
        if source:
            self._tweens[key] = source

    def _animate_fraction(self, key: str, bar: Gtk.ProgressBar, target: float) -> None:
        previous = self._last_fractions.get(key)
        self._last_fractions[key] = target
        if previous is None or abs(previous - target) < 1e-6:
            bar.set_fraction(target)
            return
        bar.set_fraction(previous)

        def apply(value: float) -> None:
            bar.set_fraction(max(0.0, min(1.0, value)))

        self._start_tween(key, previous, target, apply)

    def _on_search(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip().lower()
        if query == self._query:
            return
        self._query = query
        self.refresh()

    def _matches(self, *parts) -> bool:
        if not self._query:
            return True
        haystack = " ".join(str(part) for part in parts if part).lower()
        return self._query in haystack

    def _medicine_matches(self, medicine: Medicine) -> bool:
        return self._matches(
            medicine.name, medicine.dose, medicine.notes, " ".join(medicine.times)
        )

    def _dose_matches(self, dose: Dose) -> bool:
        return self._matches(
            dose.medicine.name,
            dose.medicine.dose,
            dose.clock,
            dose.medicine.notes,
            " ".join(dose.medicine.times),
        )

    def _empty_state(self, glyph: str, line: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        head = _label(glyph, "empty-glyph")
        head.set_halign(Gtk.Align.CENTER)
        head.set_justify(Gtk.Justification.CENTER)
        text = _label(line, "empty-line")
        text.set_halign(Gtk.Align.CENTER)
        text.set_justify(Gtk.Justification.CENTER)
        box.pack_start(head, False, False, 0)
        box.pack_start(text, False, False, 0)
        return box

    def _toast(self, message: str) -> None:
        """Monochrome confirmation, bottom-right, gone after ~3 seconds."""
        if not message:
            return
        while len(self.toasts.get_children()) >= TOAST_MAX:
            self._forget_toast(self.toasts.get_children()[0])

        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        revealer.set_transition_duration(200)
        label = Gtk.Label(label=message, xalign=0)
        label.set_line_wrap(True)
        label.set_max_width_chars(44)
        frame = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _add_class(frame, "toast")
        frame.pack_start(label, True, True, 0)
        revealer.add(frame)
        self.toasts.pack_start(revealer, False, False, 0)
        self.toasts.show_all()
        revealer.set_reveal_child(True)
        self._toast_timers[revealer] = GLib.timeout_add(TOAST_MS, self._dismiss_toast, revealer)

    def _dismiss_toast(self, revealer: Gtk.Revealer) -> bool:
        self._toast_timers.pop(revealer, None)
        if revealer.get_child() is None:
            return False
        revealer.set_reveal_child(False)
        delay = revealer.get_transition_duration() + 60
        self._toast_timers[revealer] = GLib.timeout_add(delay, self._drop_toast, revealer)
        return False

    def _drop_toast(self, revealer: Gtk.Revealer) -> bool:
        self._toast_timers.pop(revealer, None)
        parent = revealer.get_parent()
        if parent is not None:
            parent.remove(revealer)
        return False

    def _forget_toast(self, revealer: Gtk.Widget) -> None:
        source = self._toast_timers.pop(revealer, None)
        if source:
            GLib.source_remove(source)
        parent = revealer.get_parent()
        if parent is not None:
            parent.remove(revealer)

    def _build_timeline(self) -> Gtk.DrawingArea:
        area = Gtk.DrawingArea()
        area.set_size_request(-1, 64)
        _add_class(area, "timeline")
        area.connect("draw", self._draw_timeline)
        return area

    def _redraw_timeline(self) -> bool:
        self.timeline.queue_draw()
        return True

    def _draw_timeline(self, area: Gtk.Widget, context) -> bool:
        """24-hour axis: hour ticks, one dot per dose, vertical now-marker."""
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        if width < 60 or height < 30:
            return False

        inset = 14
        x0, x1 = float(inset), float(width - inset)
        span = max(1.0, x1 - x0)
        axis_y = float(int(height) - 17)
        top_y = 13.0

        counts = [0] * 24
        for when, _state in self._timeline_points:
            counts[when.hour] += 1
        peak = max(counts)

        def curve_y(value: float) -> float:
            if peak <= 0:
                return axis_y
            return axis_y - (axis_y - top_y) * (value / float(peak))

        xs = [x0 + span * index / 24.0 for index in range(25)]
        ys = [curve_y(counts[index] if index < 24 else 0) for index in range(25)]

        context.new_path()
        context.move_to(xs[0], axis_y)
        for x_value, y_value in zip(xs, ys):
            context.line_to(x_value, y_value)
        context.line_to(xs[-1], axis_y)
        context.close_path()
        _paint(context, CHART_FILL)
        context.fill_preserve()
        context.new_path()
        context.move_to(xs[0], ys[0])
        for x_value, y_value in zip(xs[1:], ys[1:]):
            context.line_to(x_value, y_value)
        context.set_line_width(1.4)
        _paint(context, CHART_LINE)
        context.stroke()

        _paint(context, CHART_GRID)
        context.rectangle(x0, axis_y, span, 1.0)
        context.fill()
        for hour in range(25):
            x_value = xs[hour]
            major = hour % 3 == 0
            length = 6.0 if major else 3.0
            context.rectangle(x_value - 0.5, axis_y + 2, 1.0, length)
        context.fill()

        context.set_font_size(9)
        _paint(context, FG3)
        for hour in (0, 3, 6, 9, 12, 15, 18, 21):
            text = f"{hour:02d}"
            extents = context.text_extents(text)
            centre = xs[hour]
            left = centre - (extents.width / 2.0)
            context.move_to(left, height - 4)
            context.show_text(text)

        for when, state in self._timeline_points:
            position = when.hour + when.minute / 60.0 + when.second / 3600.0
            index = min(24, int(position))
            fraction = position - index
            x_value = x0 + span * (position / 24.0)
            y_value = ys[index] + (ys[min(24, index + 1)] - ys[index]) * fraction
            context.new_path()
            context.arc(x_value, y_value, 4.5, 0, 6.283185307179586)
            _paint(context, STATE_COLORS.get(state, STATE_IDLE))
            context.fill_preserve()
            _paint(context, BG1)
            context.set_line_width(1.5)
            context.stroke()

        now = self._timeline_now
        position = now.hour + now.minute / 60.0 + now.second / 3600.0
        x_now = x0 + span * (position / 24.0)
        if x0 <= x_now <= x1:
            _paint(context, ACCENT)
            context.rectangle(x_now - 0.75, top_y - 6, 1.5, axis_y - top_y + 8)
            context.fill()
            context.new_path()
            context.arc(x_now, top_y - 6, 3.0, 0, 6.283185307179586)
            context.fill()

        if not self._timeline_points:
            context.set_font_size(9)
            _paint(context, FG3)
            extents = context.text_extents("nothing scheduled today")
            context.move_to((width - extents.width) / 2.0, top_y + 4)
            context.show_text("nothing scheduled today")
        return False

    def refresh(self) -> None:
        for key in list(self._tweens):
            self._stop_tween(key)
        document, status, history = actions.snapshot()
        scroll_value = self.scroll.get_vadjustment().get_value()

        self._details = {}
        self._pending = {dose.medicine.name for dose in status.doses if not dose.taken}
        self._timeline_now = status.now
        self._timeline_points = [(dose.when, _state_of(dose, status)) for dose in status.doses]
        self.timeline.queue_draw()

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
        for name, detail in self._details.items():
            if name != self._expanded:
                detail.hide()
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
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        _add_class(card, css)
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
            image.set_markup(f'<span foreground="{FG1}">●</span>')
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
            subtitle = _label(
                "Setup needed — enter your real pill counts to enable reminders",
                "subtitle",
                ellipsize=True,
            )
            titles.pack_start(subtitle, False, False, 0)
            self._last_taken = status.taken
        else:
            tail = f" doses taken · {COLOR_LABELS[status.color]}"
            if status.low_count:
                tail += f" · {status.low_count} low on stock"

            def render(value: int) -> str:
                return f"{value}{tail}"

            subtitle = _label("", "subtitle", ellipsize=True)
            previous = self._last_taken
            if previous is None or previous == status.taken:
                subtitle.set_text(render(status.taken))
            else:
                subtitle.set_text(render(previous))
                self._start_tween(
                    "taken",
                    previous,
                    status.taken,
                    lambda value: subtitle.set_text(render(int(round(value)))),
                )
            self._last_taken = status.taken
            titles.pack_start(subtitle, False, False, 0)
        head.pack_start(titles, True, True, 0)
        content.pack_start(head, False, False, 0)

        bar = Gtk.ProgressBar()
        fraction = 0.0 if status.total == 0 else status.taken / status.total
        _add_class(bar, _bar_class(status))
        self._animate_fraction("adh-day", bar, fraction)
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
            return card
        doses = [dose for dose in status.doses if self._dose_matches(dose)]
        if not doses:
            content.pack_start(
                self._empty_state("∅", f'No doses match "{self._query}"'),
                False,
                False,
                0,
            )
            return card
        for dose in doses:
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
            state_text = f"! overdue {dose.minutes_overdue(status.now)}m"
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

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = dose.medicine.name
        actions_box.pack_end(
            _button("Delete", lambda *_: self._delete_medicine(name), "btn-del"),
            False,
            False,
            0,
        )
        actions_box.pack_end(
            _button("Edit", lambda *_: self._edit_medicine(name), "btn-edit"),
            False,
            False,
            0,
        )
        if not dose.taken:
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
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        _add_class(wrap, "row")
        if dose.taken:
            _add_class(wrap, "row-off")
        wrap.set_tooltip_text(
            "Edit time/dose/course · Take logs the dose · Skip ignores it · Delete removes the medicine"
        )
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
        medicines = [medicine for medicine in document.medicines if self._medicine_matches(medicine)]
        if not document.medicines:
            content.pack_start(_label("No medicines yet.", "muted"), False, False, 0)
        elif not medicines:
            content.pack_start(
                self._empty_state("∅", f'No medicines match "{self._query}"'),
                False,
                False,
                0,
            )
        for medicine in medicines:
            content.pack_start(self._medicine_row(medicine), True, True, 0)
        if status.low:
            for medicine in status.low:
                if not self._medicine_matches(medicine):
                    continue
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
        name = medicine.name
        expanded = self._expanded == name

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_border_width(10)

        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        accent.set_size_request(5, -1)
        _add_class(accent, f"accent-{self._stock_state(medicine)}")
        box.pack_start(accent, False, True, 0)

        arrow = _label("▾" if expanded else "▸", "muted")
        arrow.set_valign(Gtk.Align.CENTER)
        box.pack_start(arrow, False, False, 0)
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
        elif medicine.is_emergency:
            times.pack_start(self._chip("ongoing", "chip-idle"), False, False, 0)
        if medicine.notes:
            times.pack_start(_label(medicine.notes, "muted", ellipsize=True), True, True, 0)
        times.pack_end(self._stock_chip(medicine), False, False, 0)
        info.pack_start(times, False, True, 0)
        box.pack_start(info, True, True, 0)

        detail = self._medicine_detail(medicine)
        self._details[name] = detail

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner.pack_start(box, False, True, 0)
        inner.pack_start(detail, False, False, 0)

        wrap = Gtk.EventBox()
        wrap.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        _add_class(wrap, "row")
        if expanded:
            _add_class(wrap, "row-open")
        if not medicine.active:
            _add_class(wrap, "row-off")
        wrap.set_tooltip_text("Edit changes dose, times, stock and notes")
        wrap.add(inner)
        wrap.connect("button-press-event", self._on_row_press, name)
        wrap.connect("button-release-event", self._on_row_release, name)
        self._enable_drag(wrap, name)
        return wrap

    def _medicine_detail(self, medicine: Medicine) -> Gtk.Box:
        """The panel a row opens in place of a dialog: times, stock, notes."""
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        _add_class(detail, "detail")

        clocks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for clock in medicine.times:
            clocks.pack_start(self._chip(clock, "chip-time"), False, False, 0)
        if medicine.days:
            clocks.pack_start(
                self._chip(f"{medicine.days}-day course", "chip-time"), False, False, 0
            )
        elif medicine.is_emergency:
            clocks.pack_start(self._chip("ongoing", "chip-idle"), False, False, 0)
        else:
            clocks.pack_start(self._chip("daily", "chip-time"), False, False, 0)
        clocks.pack_start(self._stock_chip(medicine), False, False, 0)
        detail.pack_start(clocks, False, False, 0)

        if medicine.stock is not None:
            detail.pack_start(
                _label(
                    f"stock {medicine.stock} pills · refill at {medicine.refill_at}",
                    "muted",
                    ltr=True,
                ),
                False,
                False,
                0,
            )

        if medicine.notes:
            detail.pack_start(_label(f"notes: {medicine.notes}", "muted"), False, False, 0)

        name = medicine.name
        pending = name in self._pending
        if pending:
            primary = _button("Take", lambda *_: self._act(actions.mark_taken, name), "btn-take")
        else:
            primary = _button("Refill", lambda *_: self._act(actions.refill_one, name), "btn-refill")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(primary, False, False, 0)
        row.pack_start(
            _button("Edit", lambda *_: self._edit_medicine(name), "btn-edit"), False, False, 0
        )
        row.pack_start(
            _button("Delete", lambda *_: self._delete_medicine(name), "btn-del"), False, False, 0
        )
        detail.pack_start(row, False, False, 0)
        return detail

    def _on_row_press(self, widget: Gtk.Widget, event, name: str) -> bool:
        if event.button != 1:
            return False
        self._press = None if self._dragging else (name, event.x_root, event.y_root)
        return False

    def _on_row_release(self, widget: Gtk.Widget, event, name: str) -> bool:
        press = self._press
        self._press = None
        if event.button != 1 or press is None or self._dragging:
            return False
        pressed_name, origin_x, origin_y = press
        if pressed_name != name:
            return False
        if abs(event.x_root - origin_x) > 8 or abs(event.y_root - origin_y) > 8:
            return False
        self._toggle_expanded(name)
        return False

    def _toggle_expanded(self, name: str) -> None:
        self._expanded = None if self._expanded == name else name
        self.refresh()

    def _enable_drag(self, row: Gtk.Widget, name: str) -> None:
        targets = [Gtk.TargetEntry.new(DRAG_TARGET, 0, 0)]
        row.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, targets, Gdk.DragAction.MOVE)
        row.connect("drag-begin", self._on_drag_begin)
        row.connect("drag-data-get", self._on_drag_get, name)
        row.connect("drag-end", self._on_drag_end)
        row.connect("drag-failed", self._on_drag_failed)
        row.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.MOVE)
        row.connect("drag-data-received", self._on_drag_received, name)

    def _on_drag_begin(self, widget: Gtk.Widget, _context) -> None:
        self._dragging = True

    def _on_drag_end(self, widget: Gtk.Widget, _context, _delete_data) -> None:
        self._dragging = False

    def _on_drag_failed(self, widget: Gtk.Widget, _context, _result) -> bool:
        self._dragging = False
        return False

    def _on_drag_get(self, widget, _context, data, _info, _time, name: str) -> None:
        payload = name.encode("utf-8")
        data.set_text(name, len(payload))

    def _on_drag_received(self, widget, _context, _x, _y, data, _info, _time, target: str) -> None:
        self._dragging = False
        source = (data.get_text() or "").strip()
        if not source or source == target:
            return
        if not self._reorder_medicine(source, target):
            return
        self._toast(f"order saved · {source}")
        self.refresh()

    def _reorder_medicine(self, source_name: str, target_name: str) -> bool:
        """Move one medicine above another and write the new order back."""
        try:
            document = load_medicines()
        except (OSError, ValueError) as error:
            self._say(str(error), error=True)
            return False
        medicines = document.medicines
        if any(medicine.name == source_name for medicine in medicines) is False:
            return False
        if any(medicine.name == target_name for medicine in medicines) is False:
            return False
        source_index = next(
            index for index, medicine in enumerate(medicines) if medicine.name == source_name
        )
        target_index = next(
            index for index, medicine in enumerate(medicines) if medicine.name == target_name
        )
        if source_index == target_index:
            return False
        moved = medicines.pop(source_index)
        target_index = next(
            index for index, medicine in enumerate(medicines) if medicine.name == target_name
        )
        medicines.insert(target_index, moved)
        try:
            save_medicines(document)
        except OSError as error:
            self._say(str(error), error=True)
            return False
        return True

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
            return self._chip("OUT · 0 left", "chip-out")
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
        box.pack_end(
            _button(
                "Delete",
                lambda *_: self._delete_medicine(medicine.name),
                "btn-del",
            ),
            False,
            False,
            0,
        )
        box.pack_end(
            _button("Edit", lambda *_: self._edit_medicine(medicine.name), "btn-edit"),
            False,
            False,
            0,
        )
        box.pack_end(self._stock_chip(medicine), False, False, 0)
        if medicine.is_emergency:
            course = f"for {medicine.days} days" if medicine.days else "ongoing"
            box.pack_end(self._chip(course, "chip-time"), False, False, 0)
        return box

    def _adherence(self, document: MedicineFile, history) -> Gtk.Widget:
        card, content = self._card("ADHERENCE")
        now = datetime.now().astimezone()
        for title, days, key in (
            ("Last 7 days", 7, "adh7"),
            ("Last 30 days", 30, "adh30"),
        ):
            value = engine.adherence(document.medicines, now, history, days)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.pack_start(_label(title, "muted"), False, False, 0)
            bar = Gtk.ProgressBar()
            bar.set_hexpand(True)
            _add_class(bar, _adh_class(value))
            self._animate_fraction(
                key, bar, 0.0 if value is None else max(0.0, min(1.0, value / 100))
            )
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
        self._toast(message)
        self.refresh()

    def _refill(self, *_ignored) -> None:
        try:
            message = actions.refill_low(30)
        except actions.ActionError as error:
            self._say(str(error), error=True)
            return
        self._toast(message)
        self.refresh()

    def show_add_dialog(self) -> None:
        """Open the add-medicine form, on request from the bar panel."""
        self._open_form(None)

    def show_edit_dialog(self, name: str) -> None:
        """Open the edit form for one medicine, on request from the bar panel."""
        self._open_form(name)

    def show_delete_confirm(self, name: str) -> None:
        """Ask before dropping one medicine, on request from the bar panel."""
        self._delete_medicine(name)

    def _open_form(self, name: str | None) -> None:
        if self._form_open:
            return
        self._form_open = True
        try:
            self._edit_medicine(name)
        finally:
            self._form_open = False

    def _edit_medicine(self, name: str | None, *_ignored, emergency: bool = False) -> None:
        document, _, _ = actions.snapshot()
        existing = document.by_name(name) if name else None
        form = MedicineForm(self, existing, emergency=emergency)
        response = form.run()
        medicine = form.value() if response != RESPONSE_DELETE else None
        form.destroy()
        if response == RESPONSE_DELETE:
            if existing is not None:
                self._delete_medicine(existing.name)
            return
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
        self._toast(message)
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
        self._toast(message)
        self.refresh()

    def _delete_medicine(
        self, name: str, *_ignored, transient: Gtk.Window | None = None
    ) -> None:
        confirm = Gtk.MessageDialog(
            transient_for=transient if transient is not None else self,
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
        if self._expanded == name:
            self._expanded = None
        self._toast(message)
        self.refresh()


def _hex(color: str) -> str:
    """Engine state name → a value from the grayscale ramp."""
    return {
        "neutral": STATE_IDLE,
        "green": STATE_OK,
        "amber": STATE_DUE,
        "red": STATE_LATE,
    }.get(color, STATE_IDLE)


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

    def _edit(self, name: str, *_ignored) -> None:
        if self._parent_win is None:
            return
        self._parent_win._edit_medicine(name)
        self._rebuild()

    def _delete(self, name: str, *_ignored) -> None:
        if self._parent_win is None:
            return
        self._parent_win._delete_medicine(name, transient=self)
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
        name = medicine.name
        head.pack_end(_button("Delete", lambda *_: self._delete(name), "btn-del"), False, False, 0)
        head.pack_end(_button("Edit", lambda *_: self._edit(name), "btn-edit"), False, False, 0)
        if medicine.is_out():
            state, chip_css = "OUT OF STOCK", "chip-out"
        elif medicine.is_low():
            state, chip_css = "LOW", "chip-due"
        else:
            state, chip_css = "ok", "chip-taken"
        head.pack_end(self._chip(state, chip_css), False, False, 0)
        stock = "not counted" if medicine.stock is None else str(medicine.stock)
        head.pack_end(self._chip(f"{stock} pills", "chip-stock"), False, False, 0)
        course = f"for {medicine.days} days" if medicine.days else "ongoing"
        head.pack_end(self._chip(course, "chip-time"), False, False, 0)
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
            image.set_markup(f'<span foreground="{FG1}">●</span>')
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
        if medicine is not None:
            delete_button = self.add_button("Delete", RESPONSE_DELETE)
            _add_class(delete_button, "btn-del")
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

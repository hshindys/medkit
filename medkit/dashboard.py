"""The GTK3 dashboard behind `medkit --dashboard`.

Layout language, type scale and motion mirror the bar panel (`plugin/`): one
grayscale ramp, five sections behind a sidebar, a fixed 24-hour timeline above
the list, and 300 ms ease-out motion on anything that changes.
"""

from __future__ import annotations

from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from . import actions, art, emergency, review
from .engine import DayStatus, Dose
from .models import Medicine
from .panel_data import health_payload
from .store import MedicineFile, load_medicines, save_medicines

RESPONSE_DELETE = 100

# --- the ramp. Nothing outside this list may appear anywhere in the app. ---
BG0 = "#0a0b0d"
BG1 = "#101114"
BG2 = "#16181c"
BG3 = "#1d2025"
LINE = "#25292f"
MUTE = "#5a6068"
DIM = "#8b919b"
MID = "#9aa0a8"
FG1 = "#c3c8d0"
ACCENT = "#e6e8ec"
FG0 = "#f2f4f7"

CHART_LINE = FG1
CHART_GRID = LINE
CHART_FILL = BG3

# --- design tokens (GTK has no custom properties, so these are literals) ---
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 14
GAP_XS = 4
GAP_SM = 8
GAP_MD = 12
GAP_LG = 16
PAD_CARD = 16
FONT_DISPLAY = 15
FONT_BODY = 13
FONT_LABEL = 11
FONT_MONO = 12

TWEEN_TICK_MS = 16
TWEEN_MS = 300
TOAST_MS = 2500
TOAST_MAX = 4
DRAG_TARGET = "text/plain"
HEALTH_TTL_US = 10_000_000

# The five sections, in the order the panel's ViewSwitcher shows them.
SECTIONS = ("doses", "safety", "health", "reports", "card")
SECTION_LABELS = {
    "doses": "Doses",
    "safety": "Safety",
    "health": "Health",
    "reports": "Reports",
    "card": "Card",
}
SECTION_GLYPHS = {
    "doses": "󰐂",    # pill
    "safety": "󰒃",   # shield / safety
    "health": "󰈸",   # heart-pulse
    "reports": "󰈙",  # file-document
    "card": "󰈞",     # card-account-details
}

# Nerd Font (Material) glyphs, all verified present in JetBrainsMono NF.
GLYPH = {
    "check": chr(0xF012C),
    "due": chr(0xF0150),
    "late": chr(0xF0159),
    "skipped": chr(0xF073A),
    "emergency": chr(0xF017B),
    "refill": chr(0xF043D),
    "add": chr(0xF0415),
    "edit": chr(0xF03EB),
    "delete": chr(0xF01B4),
    "close": chr(0xF0156),
    "search": chr(0xF036B),
    "warn": chr(0xF0026),
    "info": chr(0xF02FD),
    "chevron": chr(0xF0142),
    "chevron_open": chr(0xF0140),
    "refresh": chr(0xF04FD),
    "phone": chr(0xF03F2),
    "clipboard": chr(0xF01B6),
    "calendar": chr(0xF019B),
    "chart": chr(0xF020A),
    "trend": chr(0xF0738),
    "minus": chr(0xF015B),
    "square": chr(0xF015C),
    "account": chr(0xF010A),
    "key": chr(0xF0308),
    "water": chr(0xF018C),
    "bandage": chr(0xF0732),
}

STATE_GLYPHS = {
    "taken": GLYPH["check"],
    "due": GLYPH["due"],
    "late": GLYPH["late"],
    "idle": GLYPH["skipped"],
}

STATE_LABELS = {
    "taken": "taken",
    "late": "overdue",
    "due": "due now",
    "idle": "pending",
}

CSS = """
window {
  background-color: #101114;
  color: #f2f4f7;
  font-family: "Inter", "Cantarell", "DejaVu Sans";
  font-size: 13px;
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

/* focus: one ring, 2px, #e6e8ec, offset 2px — never a glow. */
*:focus {
  outline: 2px solid #e6e8ec;
  outline-offset: 2px;
}
button:focus, entry:focus, combobox:focus, spinbutton:focus,
check:focus, radio:focus, .nav-item:focus {
  border-color: #e6e8ec;
  box-shadow: none;
}

/* --- title row ------------------------------------------------------- */
.titlebar {
  background-color: #0a0b0d;
  border-bottom: 1px solid #25292f;
  box-shadow: none;
}
.titlebar .drag { background-color: transparent; padding: 10px 16px; }
.app-name { font-size: 15px; font-weight: 600; color: #f2f4f7; }
.app-date { font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
            color: #8b919b; }
.daybar { min-height: 4px; border-radius: 2px; background-color: #25292f; }
.daybar trough { min-height: 4px; border-radius: 2px; background-color: #25292f;
                 border: none; padding: 0; }
.daybar progress { min-height: 4px; border-radius: 2px; background-color: #e6e8ec; }
.win-btn {
  background-color: transparent;
  background-image: none;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 3px 10px;
  font-family: "Inter", "Cantarell", "DejaVu Sans";
  font-size: 15px;
  font-weight: normal;
  color: #8b919b;
}
.win-btn:hover { background-color: #1d2025; border-color: #25292f; color: #f2f4f7; }
.win-btn.win-close:hover { background-color: #25292f; border-color: #5a6068; }
.grip { background-color: transparent; }
.grip:hover { background-color: rgba(230, 232, 236, 0.06); }

/* --- sidebar --------------------------------------------------------- */
.sidebar {
  background-color: #16181c;
  border-right: 1px solid #25292f;
  min-width: 132px;
}
.nav-item {
  color: #8b919b;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  background-color: transparent;
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  font-size: 13px;
  font-weight: normal;
  min-height: 34px;
  transition: background-color 140ms ease, color 140ms ease;
}
.nav-item:hover { background-color: #1d2025; color: #c3c8d0; }
.nav-item.active {
  background-color: #1d2025;
  color: #f2f4f7;
  border: 1px solid #25292f;
  border-left: 3px solid #e6e8ec;
  padding-left: 10px;
}
.nav-glyph { font-size: 14px; color: inherit; }
.nav-label { font-size: 13px; color: inherit; }
.nav-badge {
  font-size: 11px;
  font-weight: 600;
  color: #0a0b0d;
  background-color: #e6e8ec;
  border-radius: 999px;
  padding: 0 7px;
  min-width: 8px;
}
.sidebar-foot { font-size: 11px; letter-spacing: 0.06em; color: #5a6068; }

/* --- type ------------------------------------------------------------ */
.section {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #8b919b;
}
.title { font-size: 15px; font-weight: 600; color: #f2f4f7; }
.subtitle { color: #c3c8d0; font-size: 13px; }
.mono { font-family: "DejaVu Sans Mono", "JetBrainsMono Nerd Font"; font-size: 12px; }
.muted { color: #8b919b; }
.body { font-size: 13px; }
.hint { color: #8b919b; font-size: 12px; padding: 4px 0; }
.hint.hint-error { color: #f2f4f7; font-weight: 600; }
.hint.hint-ok { color: #c3c8d0; }

/* --- containers ------------------------------------------------------ */
.card {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 14px;
  padding: 16px;
  box-shadow: none;
}
.card.card-danger { border: 2px solid #e6e8ec; }
.detail {
  background-color: #101114;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 10px 12px;
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
.row.row-cursor { border-color: #e6e8ec; background-color: #1d2025; }

.accent-taken { background-color: #c3c8d0; border-radius: 4px; }
.accent-due { background-color: #f2f4f7; border-radius: 4px; }
.accent-late { background-color: #8b919b; border-radius: 4px; }
.accent-idle { background-color: #5a6068; border-radius: 4px; }

.chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
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
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid #25292f;
}
.badge.badge-taken { background-color: #1d2025; color: #c3c8d0; }
.badge.badge-due { background-color: #1d2025; color: #f2f4f7; border-color: #9aa0a8; }
.badge.badge-late { background-color: #16181c; color: #8b919b; border-color: #5a6068; }
.badge.badge-idle { background-color: #16181c; color: #5a6068; }

/* --- controls -------------------------------------------------------- */
button {
  background-color: #16181c;
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  color: #c3c8d0;
  border: 1px solid #25292f;
  border-radius: 8px;
  padding: 5px 11px;
  font-family: "JetBrainsMono Nerd Font", "Inter", "Cantarell", "DejaVu Sans";
  font-weight: 600;
  font-size: 11px;
  transition: background-color 140ms ease, border-color 140ms ease;
}
button:hover { background-color: #1d2025; border-color: #8b919b; color: #f2f4f7; }
button:disabled { opacity: 0.45; }
/* Row chrome stays tight so a dose row never outgrows its card. */
.btn-take, .btn-skip, .btn-edit, .btn-del, .btn-refill {
  padding-left: 8px; padding-right: 8px;
}
.btn-take, .btn-add {
  background-color: #e6e8ec; color: #0a0b0d; border-color: #e6e8ec;
}
.btn-take:hover, .btn-add:hover {
  background-color: #f2f4f7; border-color: #f2f4f7; color: #0a0b0d;
}
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
.btn-primary { background-color: #e6e8ec; color: #0a0b0d; border-color: #e6e8ec; }
.btn-primary:hover { background-color: #f2f4f7; border-color: #f2f4f7; color: #0a0b0d; }

progressbar { min-height: 8px; border-radius: 5px; background-color: #1d2025;
              border: none; color: #c3c8d0; }
progressbar trough { min-height: 8px; border-radius: 5px; background-color: #1d2025;
                     border: none; padding: 0; }
progressbar progress { min-height: 8px; border-radius: 5px; background-color: #c3c8d0; }
progressbar.lvl-amber progress { background-color: #f2f4f7; }
progressbar.lvl-red progress { background-color: #8b919b; }

entry, spinbutton, combobox {
  background-color: #16181c;
  border: 1px solid #25292f;
  border-radius: 8px;
  color: #f2f4f7;
  padding: 7px 10px;
  box-shadow: none;
  transition: border-color 140ms ease;
}
entry:focus, spinbutton:focus, combobox:focus { border-color: #e6e8ec; box-shadow: none; }
entry selection { background-color: #9aa0a8; color: #0a0b0d; }
searchbar { background-color: transparent; }
combobox button, spinbutton button, spinbutton button:hover {
  background-color: transparent;
  border: none;
  box-shadow: none;
  color: #c3c8d0;
}
spinbutton { padding: 4px 8px; }
spinbutton button:hover { color: #f2f4f7; }
check, radio {
  min-width: 16px; min-height: 16px;
  border: 1px solid #5a6068;
  background-color: #16181c;
  background-image: none;
  color: #0a0b0d;
}
check { border-radius: 4px; }
radio { border-radius: 999px; }
check:hover, radio:hover { border-color: #8b919b; }
check:checked, radio:checked {
  background-color: #e6e8ec; background-image: none; border-color: #e6e8ec; color: #0a0b0d;
}
check:indeterminate {
  background-color: #9aa0a8; background-image: none; border-color: #9aa0a8; color: #0a0b0d;
}

/* --- glyph + search -------------------------------------------------- */
.glyph {
  font-family: "JetBrainsMono Nerd Font", "JetBrainsMono NF";
  font-weight: normal;
}
.badge .glyph { font-size: 12px; }
.chip .glyph { font-size: 12px; }
.kbd-hint {
  font-family: "DejaVu Sans Mono";
  font-size: 11px;
  letter-spacing: 0.04em;
  color: #c3c8d0;
}
.shortcut-meaning { font-size: 11px; color: #8b919b; }

/* --- charts + timeline ----------------------------------------------- */
.chart { background-color: transparent; }
.timeline { background-color: transparent; }
.timeline-hit { background-color: transparent; }

.toast {
  background-color: #1d2025;
  border: 1px solid #25292f;
  border-radius: 8px;
  color: #f2f4f7;
  font-size: 12px;
  padding: 10px 14px;
}
.toast-stack { background-color: transparent; }
.empty-glyph {
  color: #5a6068;
  font-size: 28px;
  font-family: "JetBrainsMono Nerd Font", "JetBrainsMono NF";
}
.empty-line { color: #8b919b; font-size: 12px; }
.disclaimer { font-size: 11px; color: #5a6068; }
.mark { color: #f2f4f7; font-weight: 600; }

/* --- chrome that talks to a dialog ----------------------------------- */
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
  background: transparent; border: none; box-shadow: none;
  color: #8b919b; font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
}
treeview row { background-color: #16181c; border-bottom: 1px solid #25292f; }
treeview row:hover { background-color: #1d2025; }
treeview row:selected { background-color: #1d2025; color: #f2f4f7; }
scrollbar trough { background-color: #101114; }
scrollbar slider { background-color: #25292f; border-radius: 6px; min-width: 10px; }
scrollbar slider:hover { background-color: #5a6068; }
scrolledwindow { background-color: transparent; border: none; }
"""


def _clear(container: Gtk.Container) -> None:
    for child in container.get_children():
        container.remove(child)


def _add_class(widget: Gtk.Widget, css: str) -> None:
    context = widget.get_style_context()
    for name in css.split():
        context.add_class(name)


def _flow(label: Gtk.Label, ellipsize: bool) -> Gtk.Label:
    """Prose wraps inside its card; only fixed-width chrome gets ellipsised.

    A single-line paragraph otherwise reports its whole width as a minimum and
    drags every card in the column past the right edge.
    """
    if ellipsize:
        label.set_ellipsize(Pango.EllipsizeMode.END)
    else:
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(56)
    return label


def _label(text: str, css: str = "", ltr: bool = False, ellipsize: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    if css:
        _add_class(label, css)
    if ltr:
        label.set_direction(Gtk.TextDirection.LTR)
    return _flow(label, ellipsize)


def _glyph(char: str, css: str = "") -> Gtk.Label:
    """A Nerd Font glyph, always drawn from the icon face and always LTR."""
    label = Gtk.Label(label=char, xalign=0)
    _add_class(label, f"glyph {css}".strip())
    label.set_direction(Gtk.TextDirection.LTR)
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

    Ease-out-cubic over `duration_ms`, ~16 ms per tick, self-cancelling once
    it reaches the end — the caller only has to drop the source id it gets
    back when the widget underneath goes away.
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
        eased = 1.0 - (1.0 - progress) ** 3
        on_value(start + (end - start) * eased)
        if progress >= 1.0:
            if on_done is not None:
                on_done()
            return False
        return True

    return GLib.timeout_add(TWEEN_TICK_MS, step)


def pill_icon(name: str, size: int = 30) -> Gtk.Widget:
    """Animated pill glyph — APNG where the loader can read it, GIF otherwise.

    Some builds of GdkPixbuf cannot decode APNG at all, so the first candidate
    that actually loads wins and a still PNG is the last resort.
    """
    for path in (_anim_path(art.pill_apng, name, size), _anim_path(art.pill_gif, name, size)):
        if path is None:
            continue
        try:
            animation = GdkPixbuf.PixbufAnimation.new_from_file(str(path))
        except Exception:
            animation = None
        if animation is None:
            continue
        image = Gtk.Image.new_from_animation(animation)
        image.set_valign(Gtk.Align.CENTER)
        return image
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(art.pill_png(name, size)))
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.set_valign(Gtk.Align.CENTER)
        return image
    except Exception:
        label = Gtk.Label()
        label.set_markup(f'<span foreground="{FG1}">●</span>')
        label.set_valign(Gtk.Align.CENTER)
        return label


def _anim_path(generator, name: str, size: int):
    try:
        return generator(name, size)
    except Exception:
        return None


class Dashboard(Gtk.Window):
    def __init__(self, application: Gtk.Application | None = None) -> None:
        super().__init__(title="MedKit")
        if application is not None:
            self.set_application(application)
        self.set_default_size(960, 900)
        # Below the width a half-workspace tile gives us, so the compositor
        # can honour it instead of squeezing the surface into the slot.
        self.set_size_request(560, 460)
        # The window draws its own title row so it can match the panel chrome.
        self.set_decorated(False)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._query = ""
        self._section = "doses"
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
        self._timeline_hits: list[tuple[float, str]] = []
        self._timeline_now = datetime.now().astimezone()
        self._clock_source: int | None = None
        self._dose_rows: dict[str, Gtk.Widget] = {}
        self._row_widgets: dict[str, Gtk.Widget] = {}
        self._row_names: list[str] = []
        self._cursor = -1
        self._hp: dict | None = None
        self._hp_at = 0
        self._form_open = False
        self._hint_source: int | None = None
        self._nav_items: dict[str, tuple[Gtk.Button, Gtk.Label]] = {}

        overlay = Gtk.Overlay()
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        overlay.add(shell)
        self.add(overlay)

        shell.pack_start(self._build_titlebar(), False, False, 0)

        middle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        middle.pack_start(self._build_sidebar(), False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_MD)
        content.set_margin_start(GAP_LG)
        content.set_margin_end(GAP_LG)
        content.set_margin_top(GAP_LG)
        content.set_margin_bottom(GAP_LG)
        middle.pack_start(content, True, True, 0)
        shell.pack_start(middle, True, True, 0)

        timeline_card, timeline_body = self._card("TODAY")
        self.timeline = self._build_timeline()
        timeline_body.pack_start(self.timeline, False, False, 0)
        timeline_body.pack_start(self._timeline_legend(), False, False, 0)
        content.pack_start(timeline_card, False, False, 0)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search medicines, doses, times, notes, state")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", self._on_search)
        search_row.pack_start(self.search, True, True, 0)
        content.pack_start(search_row, False, False, 0)

        self.hint = _label("", "hint")
        self.hint.set_no_show_all(True)
        content.pack_start(self.hint, False, False, 0)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_LG)
        scroll = Gtk.ScrolledWindow()
        # The column decides its own width and the cards fill it: a card that
        # insisted on being wider would push every sibling past the edge.
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.body)
        self.scroll = scroll
        content.pack_start(scroll, True, True, 0)

        self.toasts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_SM)
        _add_class(self.toasts, "toast-stack")
        self.toasts.set_halign(Gtk.Align.END)
        self.toasts.set_valign(Gtk.Align.END)
        self.toasts.set_margin_end(GAP_LG)
        self.toasts.set_margin_bottom(GAP_LG)
        overlay.add_overlay(self.toasts)
        overlay.set_overlay_pass_through(self.toasts, True)

        grip = Gtk.EventBox()
        grip.set_size_request(16, 16)
        grip.set_valign(Gtk.Align.END)
        grip.set_halign(Gtk.Align.END)
        _add_class(grip, "grip")
        grip.connect(
            "button-press-event",
            lambda widget, event: self._begin_resize(event),
        )
        overlay.add_overlay(grip)
        overlay.set_overlay_pass_through(grip, False)

        self.connect("key-press-event", self._on_key)
        self._clock_source = GLib.timeout_add_seconds(30, self._redraw_timeline)
        self.connect("destroy", self._on_destroy)

        self.refresh()
        # Nothing is focused until the user asks for it: no ring on open.
        self.set_focus(None)

    # ------------------------------------------------------------------
    # chrome
    # ------------------------------------------------------------------
    def _build_titlebar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        _add_class(bar, "titlebar")

        drag = Gtk.EventBox()
        _add_class(drag, "drag")
        drag.set_hexpand(True)
        drag.connect("button-press-event", self._on_title_press)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.pack_start(pill_icon("MedKit", 24), False, False, 0)
        row.pack_start(_label("MedKit", "app-name", ellipsize=True), False, False, 0)
        # One line only: a wrapped date pushes the progress bar into the
        # window buttons as soon as the window narrows.
        self.daydate = _label(
            datetime.now().strftime("%A %d %B %Y"), "app-date", ellipsize=True
        )
        self.daydate.set_valign(Gtk.Align.CENTER)
        row.pack_start(self.daydate, False, False, 0)
        self.daybar = Gtk.ProgressBar()
        self.daybar.set_size_request(112, -1)
        self.daybar.set_valign(Gtk.Align.CENTER)
        _add_class(self.daybar, "daybar")
        row.pack_start(self.daybar, False, False, 0)
        drag.add(row)
        bar.pack_start(drag, True, True, 0)

        for text, handler, css in (
            ("×", lambda *_: self.close(), "win-btn win-close"),
            ("□", self._toggle_max, "win-btn"),
            ("–", lambda *_: self.iconify(), "win-btn"),
        ):
            button = _button(text, handler, css)
            # window chrome never takes the keyboard ring
            button.set_can_focus(False)
            bar.pack_end(button, False, False, 0)
        return bar

    def _on_title_press(self, _widget, event) -> bool:
        if event.button != 1:
            return False
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            self._toggle_max()
            return True
        self.begin_move_drag(int(event.button), int(event.x_root), int(event.y_root), event.time)
        return True

    def _begin_resize(self, event) -> bool:
        if event.button != 1:
            return False
        self.begin_resize_drag(
            Gdk.WindowEdge.SOUTH_EAST,
            int(event.button),
            int(event.x_root),
            int(event.y_root),
            event.time,
        )
        return True

    def _toggle_max(self, *_ignored) -> None:
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def _build_sidebar(self) -> Gtk.Widget:
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_XS)
        _add_class(side, "sidebar")
        side.set_margin_top(14)
        side.set_margin_bottom(14)
        side.set_margin_start(10)
        side.set_margin_end(10)

        head = _label("SECTIONS", "section")
        head.set_margin_bottom(GAP_XS)
        side.pack_start(head, False, False, 0)

        for index, sid in enumerate(SECTIONS, start=1):
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            _add_class(button, "nav-item")
            button.set_tooltip_text(
                f"{SECTION_LABELS[sid]} — press {index}" if index < 5 else "Card — press 5"
            )
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.pack_start(_glyph(SECTION_GLYPHS[sid], "nav-glyph"), False, False, 0)
            row.pack_start(_label(SECTION_LABELS[sid], "nav-label"), True, True, 0)
            badge = Gtk.Label(label="", xalign=1)
            _add_class(badge, "nav-badge")
            badge.set_no_show_all(True)
            row.pack_end(badge, False, False, 0)
            button.add(row)
            button.connect("clicked", self._on_nav, sid)
            self._nav_items[sid] = (button, badge)
            side.pack_start(button, False, False, 0)

        side.pack_end(
            _label("LOCAL DATA\nONLY", "sidebar-foot"),
            False,
            False,
            0,
        )
        side.pack_end(self._shortcuts(), False, False, 0)
        return side

    def _shortcuts(self) -> Gtk.Widget:
        """Keyboard map, parked in the sidebar where there is vertical room."""
        grid = Gtk.Grid(column_spacing=10, row_spacing=3)
        grid.set_margin_top(18)
        keys = [
            ("CTRL+F", "search"),
            ("J / K", "move"),
            ("ENTER", "take"),
            ("S", "skip"),
            ("E", "edit"),
            ("D", "delete"),
            ("1 – 5", "sections"),
            ("ESC", "close"),
        ]
        for index, (key, meaning) in enumerate(keys):
            key_label = _label(key, "kbd-hint")
            key_label.set_xalign(1)
            grid.attach(key_label, 0, index, 1, 1)
            grid.attach(_label(meaning, "shortcut-meaning"), 1, index, 1, 1)
        return grid

    def _on_nav(self, _button, sid: str) -> None:
        if sid == self._section:
            return
        self._section = sid
        self._cursor = -1
        self.scroll.get_vadjustment().set_value(0)
        self.refresh()

    def _sync_nav(self, hp: dict) -> None:
        badges = {
            "safety": hp["interactions"]["count"]
            + len(hp["food"]["alerts"])
            + hp["pregnancy"]["countFlagged"]
            + hp["missed"]["count"],
            "health": hp["refills"]["countWarn"] + len(hp["sideEffects"]["repeats"]),
            "reports": 1 if hp["review"]["due"] else 0,
            "card": 1 if hp["emergency"].get("incomplete") else 0,
            "doses": hp["missed"]["count"],
        }
        for sid, (button, badge) in self._nav_items.items():
            context = button.get_style_context()
            context.remove_class("active")
            if sid == self._section:
                context.add_class("active")
            count = badges.get(sid, 0)
            badge.set_text(str(count) if count else "")
            if count:
                badge.show()
            else:
                badge.hide()

    # ------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------
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

    def _health(self, force: bool = False) -> dict:
        moment = GLib.get_monotonic_time()
        if not force and self._hp is not None and moment - self._hp_at < HEALTH_TTL_US:
            return self._hp
        self._hp = health_payload()
        self._hp_at = moment
        return self._hp

    def _on_search(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip().lower()
        if query == self._query:
            return
        self._query = query
        self._cursor = -1
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

    def _dose_matches(self, dose: Dose, status: DayStatus) -> bool:
        state = _state_of(dose, status)
        return self._matches(
            dose.medicine.name,
            dose.medicine.dose,
            dose.clock,
            dose.medicine.notes,
            " ".join(dose.medicine.times),
            STATE_LABELS[state],
            state,
        )

    def _match_label(
        self, text: str, css: str = "", ltr: bool = False, ellipsize: bool = False
    ) -> Gtk.Label:
        """Body label that lights the search hit up in the brightest ramp value."""
        if not text or not self._query:
            return _label(text, css, ltr, ellipsize)
        needle = self._query
        haystack = text.lower()
        pieces: list[str] = []
        cursor = 0
        while True:
            hit = haystack.find(needle, cursor)
            if hit < 0:
                pieces.append(GLib.markup_escape_text(text[cursor:]))
                break
            pieces.append(GLib.markup_escape_text(text[cursor:hit]))
            pieces.append(
                f'<span foreground="{FG0}"><b>'
                f"{GLib.markup_escape_text(text[hit:hit + len(needle)])}"
                "</b></span>"
            )
            cursor = hit + len(needle)
        label = Gtk.Label(xalign=0)
        label.set_markup("".join(pieces))
        if css:
            _add_class(label, css)
        if ltr:
            label.set_direction(Gtk.TextDirection.LTR)
        return _flow(label, ellipsize)

    def _empty_state(self, glyph_char: str, line: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        head = _glyph(glyph_char, "empty-glyph")
        head.set_halign(Gtk.Align.CENTER)
        head.set_justify(Gtk.Justification.CENTER)
        text = _label(line, "empty-line")
        text.set_halign(Gtk.Align.CENTER)
        text.set_justify(Gtk.Justification.CENTER)
        box.pack_start(head, False, False, 0)
        box.pack_start(text, False, False, 0)
        return box

    def _toast(self, message: str) -> None:
        """Monochrome confirmation, bottom-right, gone after 2.5 seconds."""
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
        self._toast_timers[revealer] = GLib.timeout_add(
            TOAST_MS, self._dismiss_toast, revealer
        )

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

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    def _build_timeline(self) -> Gtk.DrawingArea:
        area = Gtk.DrawingArea()
        area.set_size_request(-1, 64)
        area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
        )
        _add_class(area, "timeline")
        area.connect("draw", self._draw_timeline)
        area.connect("button-press-event", self._on_timeline_press)
        return area

    def _timeline_legend(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        for state in ("taken", "due", "idle"):
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            item.pack_start(_glyph(STATE_GLYPHS[state], "muted"), False, False, 0)
            item.pack_start(_label(STATE_LABELS[state], "muted"), False, False, 0)
            row.pack_start(item, False, False, 0)
        row.pack_end(_label("click a tick to jump to the dose", "disclaimer"), False, False, 0)
        return row

    def _redraw_timeline(self) -> bool:
        self.timeline.queue_draw()
        return True

    def _draw_timeline(self, area: Gtk.Widget, context) -> bool:
        """24-hour axis: one tick per dose, vertical now-marker, hour labels."""
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        if width < 60 or height < 30:
            return False

        inset = 16
        x0, x1 = float(inset), float(width - inset)
        span = max(1.0, x1 - x0)
        axis_y = float(int(height) - 16)
        top_y = 14.0
        tick_h = axis_y - top_y

        _paint(context, CHART_GRID)
        context.rectangle(x0, axis_y, span, 1.0)
        context.fill()
        for hour in range(25):
            x_value = x0 + span * hour / 24.0
            major = hour % 3 == 0
            context.rectangle(x_value - 0.5, axis_y + 2, 1.0, 6.0 if major else 3.0)
        context.fill()

        context.set_font_size(9)
        _paint(context, MUTE)
        for hour in (0, 3, 6, 9, 12, 15, 18, 21):
            text = f"{hour:02d}"
            extents = context.text_extents(text)
            centre = x0 + span * hour / 24.0
            context.move_to(centre - (extents.width / 2.0), height - 3)
            context.show_text(text)

        # doses that share a clock would sit on top of each other: spread the
        # stack sideways so every tick stays visible and clickable.
        ticks: list[list] = []
        for when, state in self._timeline_points:
            position = when.hour + when.minute / 60.0 + when.second / 3600.0
            ticks.append([x0 + span * (position / 24.0), state, when])
        ticks.sort(key=lambda item: item[0])
        gap = 7.0
        for index in range(1, len(ticks)):
            if ticks[index][0] - ticks[index - 1][0] < gap:
                ticks[index][0] = ticks[index - 1][0] + gap
        if ticks and ticks[-1][0] > x1:
            shift = ticks[-1][0] - x1
            for item in ticks:
                item[0] -= shift

        self._timeline_hits = []
        for x_value, state, when in ticks:
            key = f"{when:%H:%M}|{state}"
            if state == "taken":
                _paint(context, FG1)
                context.rectangle(x_value - 2.5, top_y, 5.0, tick_h)
                context.fill()
            elif state in ("due", "late"):
                _paint(context, FG0 if state == "due" else DIM)
                context.set_line_width(1.5)
                context.rectangle(x_value - 2.5, top_y, 5.0, tick_h)
                context.stroke()
            elif state == "idle":
                _paint(context, MUTE, 0.9)
                context.set_line_width(1.2)
                context.rectangle(x_value - 2.0, top_y, 4.0, tick_h)
                context.stroke()
            else:
                # skipped: half-height, deliberately dimmed
                _paint(context, MUTE, 0.55)
                context.rectangle(x_value - 2.0, axis_y - tick_h * 0.5, 4.0, tick_h * 0.5)
                context.fill()
            self._timeline_hits.append((x_value, key))

        now = self._timeline_now
        position = now.hour + now.minute / 60.0 + now.second / 3600.0
        x_now = x0 + span * (position / 24.0)
        if x0 <= x_now <= x1:
            _paint(context, ACCENT)
            context.rectangle(x_now - 0.75, top_y - 7, 1.5, tick_h + 9)
            context.fill()
            context.new_path()
            context.arc(x_now, top_y - 7, 3.0, 0, 6.283185307179586)
            context.fill()

        if not self._timeline_points:
            context.set_font_size(9)
            _paint(context, MUTE)
            text = "nothing scheduled today"
            extents = context.text_extents(text)
            context.move_to((width - extents.width) / 2.0, top_y + 4)
            context.show_text(text)
        return False

    def _on_timeline_press(self, _widget, event) -> bool:
        if event.button != 1 or not self._timeline_hits:
            return False
        best = min(self._timeline_hits, key=lambda hit: abs(hit[0] - event.x))
        if abs(best[0] - event.x) > 14:
            return False
        self._jump_to_dose(best[1].split("|", 1)[0])
        return True

    def _jump_to_dose(self, clock: str) -> None:
        if self._section != "doses":
            self._section = "doses"
            self.refresh()
        widget = self._dose_rows.get(clock)
        if widget is None:
            return
        y = widget.translate_coordinates(self.body, 0, 0)[1]
        adjustment = self.scroll.get_vadjustment()
        adjustment.set_value(max(adjustment.get_lower(), y - 24))

    # ------------------------------------------------------------------
    # keyboard
    # ------------------------------------------------------------------
    def _on_key(self, _widget, event) -> bool:
        keyval = event.keyval
        ctrl = bool(event.get_state() & Gdk.ModifierType.CONTROL_MASK)

        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            self.search.select_region(0, -1)
            return True
        if keyval == Gdk.KEY_Escape:
            if self._query:
                self.search.set_text("")
                return True
            focused = self.get_focus()
            if isinstance(focused, Gtk.Entry) and focused.get_text():
                focused.set_text("")
                return True
            if focused is not None and isinstance(focused, Gtk.Entry):
                self.set_focus(None)
                return True
            self.close()
            return True

        if not ctrl and keyval in (Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_3, Gdk.KEY_4, Gdk.KEY_5):
            sid = SECTIONS[keyval - Gdk.KEY_1]
            if sid != self._section:
                self._section = sid
                self._cursor = -1
                self.scroll.get_vadjustment().set_value(0)
                self.refresh()
            return True
        if ctrl:
            return False

        focused = self.get_focus()
        if isinstance(focused, (Gtk.Entry, Gtk.SpinButton, Gtk.ComboBox, Gtk.TextView)):
            return False

        if keyval in (Gdk.KEY_j, Gdk.KEY_J):
            self._move_cursor(1)
            return True
        if keyval in (Gdk.KEY_k, Gdk.KEY_K):
            self._move_cursor(-1)
            return True
        if not self._row_names:
            return False
        name = self._row_names[self._cursor] if 0 <= self._cursor < len(self._row_names) else ""
        if not name:
            return False
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._act(actions.mark_taken, name)
            return True
        if keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self._act(actions.mark_skipped, name)
            return True
        if keyval in (Gdk.KEY_e, Gdk.KEY_E):
            self._edit_medicine(name)
            return True
        if keyval in (Gdk.KEY_d, Gdk.KEY_D):
            self._delete_medicine(name)
            return True
        return False

    def _move_cursor(self, delta: int) -> None:
        if not self._row_names:
            return
        if self._cursor < 0:
            index = 0 if delta > 0 else len(self._row_names) - 1
        else:
            index = self._cursor + delta
        index = max(0, min(len(self._row_names) - 1, index))
        self._set_cursor(index)

    def _set_cursor(self, index: int) -> None:
        previous = self._row_names[self._cursor] if 0 <= self._cursor < len(self._row_names) else ""
        self._cursor = index
        if previous in self._row_widgets:
            self._row_widgets[previous].get_style_context().remove_class("row-cursor")
        if not (0 <= index < len(self._row_names)):
            return
        name = self._row_names[index]
        widget = self._row_widgets.get(name)
        if widget is None:
            return
        widget.get_style_context().add_class("row-cursor")
        y = widget.translate_coordinates(self.body, 0, 0)[1]
        adjustment = self.scroll.get_vadjustment()
        top = adjustment.get_value()
        height = self.scroll.get_allocated_height()
        if y < top + 8 or y > top + height - 60:
            adjustment.set_value(max(adjustment.get_lower(), y - 90))

    # ------------------------------------------------------------------
    # refresh + dispatch
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        focused = self.get_focus()
        if focused is not None and isinstance(focused, Gtk.Entry) and self.body.is_ancestor(
            focused
        ):
            # Never yank the text out from under someone editing the card.
            return
        for key in list(self._tweens):
            self._stop_tween(key)
        document, status, history = actions.snapshot()
        hp = self._health(force=True)
        scroll_value = self.scroll.get_vadjustment().get_value()

        self._details = {}
        self._pending = {dose.medicine.name for dose in status.doses if not dose.taken}
        self._timeline_now = status.now
        self._timeline_points = [
            (dose.when, self._timeline_state(dose, status, history)) for dose in status.doses
        ]
        self._dose_rows = {}
        self._row_widgets = {}
        self._row_names = []
        self.timeline.queue_draw()
        self.daydate.set_text(status.now.strftime("%A %d %B %Y"))
        self._animate_header(status)

        _clear(self.body)
        for widget in self._build_section(document, status, history, hp):
            self.body.pack_start(widget, False, False, 0)
        self.show_all()
        for name, detail in self._details.items():
            if name != self._expanded:
                detail.hide()
        if 0 <= self._cursor < len(self._row_names):
            self._set_cursor(self._cursor)
        else:
            self._cursor = -1
        self._sync_nav(hp)
        self.scroll.get_vadjustment().set_value(scroll_value)
        if self._hint_source is None:
            self.hint.hide()

    def _timeline_state(self, dose: Dose, status: DayStatus, history) -> str:
        if dose.taken:
            return "taken"
        skipped = any(
            entry.action == "skipped"
            and entry.medicine == dose.medicine.name
            and entry.ts.date() == status.now.date()
            for entry in history
        )
        if skipped:
            return "skipped"
        return _state_of(dose, status)

    def _animate_header(self, status: DayStatus) -> None:
        fraction = 0.0 if status.total == 0 else status.taken / status.total
        self._animate_fraction("title", self.daybar, fraction)

    def _build_section(self, document, status, history, hp) -> list[Gtk.Widget]:
        if self._section == "safety":
            widgets = self._safety(hp)
        elif self._section == "health":
            widgets = self._health_section(hp)
        elif self._section == "reports":
            widgets = self._reports(document, history, hp)
        elif self._section == "card":
            widgets = self._card_section(hp)
        else:
            widgets = [
                self._doses(status),
                self._medicines(document, status),
                self._emergency(document),
            ]
        widgets.append(self._toolbar(document))
        return widgets

    # ------------------------------------------------------------------
    # shared widgets
    # ------------------------------------------------------------------
    def _card(
        self, title: str = "", css: str = "card", right: Gtk.Widget | None = None
    ) -> tuple[Gtk.Box, Gtk.Box]:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_MD)
        _add_class(card, css)
        if title or right is not None:
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            if title:
                head.pack_start(_label(title.upper(), "section"), True, True, 0)
            if right is not None:
                head.pack_end(right, False, False, 0)
            card.pack_start(head, False, False, 0)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_SM)
        card.pack_start(content, False, False, 0)
        return card, content

    def _chip(self, text: str, css: str) -> Gtk.Label:
        label = _label(text, f"chip {css}")
        label.set_valign(Gtk.Align.CENTER)
        return label

    def _glyph_chip(self, char: str, text: str, css: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        _add_class(box, f"chip {css}")
        box.set_valign(Gtk.Align.CENTER)
        box.pack_start(_glyph(char), False, False, 0)
        box.pack_start(_label(text), False, False, 0)
        return box

    def _badge(self, text: str, css: str, char: str = "") -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        _add_class(box, f"badge {css}")
        box.set_valign(Gtk.Align.CENTER)
        if char:
            box.pack_start(_glyph(char), False, False, 0)
        box.pack_start(_label(text), False, False, 0)
        return box

    def _severity_css(self, severity: str) -> str:
        level = str(severity).lower()
        if level in ("severe", "major", "avoid", "high", "danger"):
            return "chip-danger"
        if level in ("moderate", "caution", "warning", "medium"):
            return "chip-due"
        if level in ("mild", "low", "minor"):
            return "chip-late"
        return "chip-taken"

    def _detail(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_XS)
        _add_class(box, "detail")
        return box

    def _count_chip(self, count: int, noun: str) -> Gtk.Label:
        if not count:
            return self._chip(f"0 {noun}", "chip-idle")
        return self._chip(f"{count} {noun}", "chip-due")

    # ------------------------------------------------------------------
    # Doses
    # ------------------------------------------------------------------
    def _doses(self, status: DayStatus) -> Gtk.Widget:
        card, content = self._card("TODAY'S DOSES")
        if not status.doses:
            content.pack_start(
                self._empty_state(GLYPH["calendar"], "No doses scheduled today."),
                False,
                False,
                0,
            )
            return card
        doses = [dose for dose in status.doses if self._dose_matches(dose, status)]
        if not doses:
            content.pack_start(
                self._empty_state(GLYPH["search"], f'No doses match "{self._query}"'),
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
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        box.set_border_width(8)

        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        accent.set_size_request(5, -1)
        _add_class(accent, f"accent-{state}")
        box.pack_start(accent, False, True, 0)

        box.pack_start(pill_icon(dose.medicine.name, 24), False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_XS)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        line.pack_start(self._chip(dose.clock, "chip-time"), False, False, 0)
        line.pack_start(
            self._match_label(dose.medicine.name, ellipsize=True), False, True, 0
        )
        if dose.medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(
                self._match_label(dose.medicine.dose, ltr=True), False, False, 0
            )
        info.pack_start(line, False, False, 0)

        if state == "late":
            state_text = f"overdue {dose.minutes_overdue(status.now)}m"
        else:
            state_text = STATE_LABELS[state]
        line2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        if dose.medicine.notes:
            line2.pack_start(
                self._match_label(dose.medicine.notes, "muted", ellipsize=True),
                True,
                True,
                0,
            )
        line2.pack_end(
            self._badge(state_text, f"badge-{state}", STATE_GLYPHS[state]),
            False,
            False,
            0,
        )
        info.pack_start(line2, False, True, 0)
        box.pack_start(info, True, True, 0)

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        name = dose.medicine.name
        actions_box.pack_end(
            _button(GLYPH["delete"], lambda *_: self._delete_medicine(name), "btn-del"),
            False,
            False,
            0,
        )
        actions_box.pack_end(
            _button(GLYPH["edit"], lambda *_: self._edit_medicine(name), "btn-edit"),
            False,
            False,
            0,
        )
        if not dose.taken:
            actions_box.pack_end(
                _button(
                    "Skip", lambda *_: self._act(actions.mark_skipped, name), "btn-skip"
                ),
                False,
                False,
                0,
            )
            actions_box.pack_end(
                _button(
                    "Take", lambda *_: self._act(actions.mark_taken, name), "btn-take"
                ),
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
        self._dose_rows[dose.clock] = wrap
        return wrap

    def _medicines(self, document: MedicineFile, status: DayStatus) -> Gtk.Widget:
        card, content = self._card(
            "MEDICINES",
            right=_button(GLYPH["add"] + " Add medicine",
                          lambda *_: self._edit_medicine(None), "btn-add"),
        )
        if status.low:
            content.pack_start(
                _button(
                    f"{GLYPH['refill']} Refill low ({len(status.low)})",
                    lambda *_: self._refill(),
                    "btn-refill",
                ),
                False,
                False,
                0,
            )
        medicines = [medicine for medicine in document.medicines if self._medicine_matches(medicine)]
        if not document.medicines:
            content.pack_start(
                self._empty_state(GLYPH["add"], "No medicines yet."), False, False, 0
            )
        elif not medicines:
            content.pack_start(
                self._empty_state(GLYPH["search"], f'No medicines match "{self._query}"'),
                False,
                False,
                0,
            )
        for medicine in medicines:
            content.pack_start(self._medicine_row(medicine), True, True, 0)
        return card

    def _medicine_row(self, medicine: Medicine) -> Gtk.Widget:
        name = medicine.name
        expanded = self._expanded == name

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_MD)
        box.set_border_width(10)

        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        accent.set_size_request(5, -1)
        _add_class(accent, f"accent-{self._stock_state(medicine)}")
        box.pack_start(accent, False, True, 0)

        arrow = _glyph(
            GLYPH["chevron_open"] if expanded else GLYPH["chevron"], "muted"
        )
        arrow.set_valign(Gtk.Align.CENTER)
        box.pack_start(arrow, False, False, 0)
        box.pack_start(pill_icon(medicine.name, 26), False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_XS + 1)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        line.pack_start(self._match_label(medicine.name, ellipsize=True), False, True, 0)
        if medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(self._match_label(medicine.dose, ltr=True), False, False, 0)
        if medicine.is_emergency:
            line.pack_start(
                self._glyph_chip(GLYPH["emergency"], "emergency", "chip-danger"),
                False,
                False,
                0,
            )
        if not medicine.active:
            line.pack_start(self._chip("paused", "chip-idle"), False, False, 0)
        line.pack_end(
            _button(GLYPH["delete"], lambda *_: self._delete_medicine(name), "btn-del"),
            False,
            False,
            0,
        )
        line.pack_end(
            _button(GLYPH["edit"], lambda *_: self._edit_medicine(name), "btn-edit"),
            False,
            False,
            0,
        )
        info.pack_start(line, False, True, 0)

        # Three time chips per line keeps the row narrow; status and notes get
        # a line of their own underneath.
        clocks = list(medicine.times)
        for start in range(0, len(clocks), 3):
            times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_XS + 2)
            for clock in clocks[start : start + 3]:
                times.pack_start(self._chip(clock, "chip-time"), False, False, 0)
            info.pack_start(times, False, True, 0)
        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_XS + 2)
        if medicine.days:
            meta.pack_start(
                self._chip(f"{medicine.days}-day course", "chip-time"),
                False,
                False,
                0,
            )
        elif medicine.is_emergency:
            meta.pack_start(self._chip("ongoing", "chip-idle"), False, False, 0)
        meta.pack_start(self._stock_chip(medicine), False, False, 0)
        if medicine.notes:
            meta.pack_start(
                self._match_label(medicine.notes, "muted", ellipsize=True),
                True,
                True,
                0,
            )
        info.pack_start(meta, False, True, 0)
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
        self._row_widgets[name] = wrap
        self._row_names.append(name)
        return wrap

    def _medicine_detail(self, medicine: Medicine) -> Gtk.Box:
        """The panel a row opens in place of a dialog: times, stock, notes."""
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_SM)
        _add_class(detail, "detail")

        clocks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_XS + 2)
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
            detail.pack_start(
                _label(f"notes: {medicine.notes}", "muted"), False, False, 0
            )

        name = medicine.name
        if name in self._pending:
            primary = _button(
                "Take", lambda *_: self._act(actions.mark_taken, name), "btn-take"
            )
        else:
            primary = _button(
                "Refill", lambda *_: self._act(actions.refill_one, name), "btn-refill"
            )
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        row.pack_start(primary, False, False, 0)
        row.pack_start(
            _button(GLYPH["edit"], lambda *_: self._edit_medicine(name), "btn-edit"),
            False,
            False,
            0,
        )
        row.pack_start(
            _button(GLYPH["delete"], lambda *_: self._delete_medicine(name), "btn-del"),
            False,
            False,
            0,
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
        if not any(medicine.name == source_name for medicine in medicines):
            return False
        if not any(medicine.name == target_name for medicine in medicines):
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

    def _emergency(self, document: MedicineFile) -> Gtk.Widget:
        card, content = self._card("EMERGENCY", "card card-danger")
        emergencies = [medicine for medicine in document.medicines if medicine.is_emergency]
        if not emergencies:
            content.pack_start(
                self._empty_state(GLYPH["emergency"], "No emergency medicine defined yet."),
                False,
                False,
                0,
            )
        for medicine in emergencies:
            content.pack_start(self._stock_row(medicine), False, False, 0)
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        actions_row.pack_start(
            _button(
                f"{GLYPH['emergency']} EMERGENCY",
                lambda *_: EmergencyWindow(self).show_all(),
                "btn-danger",
            ),
            True,
            True,
            0,
        )
        actions_row.pack_start(
            _button(f"{GLYPH['add']} Add medicine", self._add_emergency, "btn-add"),
            True,
            True,
            0,
        )
        content.pack_start(actions_row, False, False, 0)
        return card

    def _stock_row(self, medicine: Medicine) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_border_width(8)
        box.pack_start(pill_icon(medicine.name, 24), False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        line.pack_start(
            self._match_label(medicine.name, ellipsize=True), True, True, 0
        )
        if medicine.dose:
            line.pack_start(_label("·", "muted"), False, False, 0)
            line.pack_start(self._match_label(medicine.dose, ltr=True), False, False, 0)
        text.pack_start(line, False, False, 0)
        if medicine.emergency_contacts:
            contact = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            contact.pack_start(_glyph(GLYPH["phone"], "muted"), False, False, 0)
            contact.pack_start(
                _label(medicine.emergency_contacts, "muted", ltr=True, ellipsize=True),
                True,
                True,
                0,
            )
            text.pack_start(contact, False, False, 0)
        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        meta.pack_start(self._stock_chip(medicine), False, False, 0)
        if medicine.is_emergency:
            course = f"for {medicine.days} days" if medicine.days else "ongoing"
            meta.pack_start(self._chip(course, "chip-time"), False, False, 0)
        text.pack_start(meta, False, False, 0)
        # Time chips wrap onto extra rows instead of forcing the card wide.
        for start in range(0, len(medicine.times), 4):
            clocks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_XS + 2)
            for clock in medicine.times[start : start + 4]:
                clocks.pack_start(self._chip(clock, "chip-time"), False, False, 0)
            text.pack_start(clocks, False, False, 0)
        box.pack_start(text, True, True, 0)
        box.pack_end(
            _button(
                GLYPH["delete"],
                lambda *_: self._delete_medicine(medicine.name),
                "btn-del",
            ),
            False,
            False,
            0,
        )
        box.pack_end(
            _button(
                GLYPH["edit"],
                lambda *_: self._edit_medicine(medicine.name),
                "btn-edit",
            ),
            False,
            False,
            0,
        )
        return box

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
            _button(
                f"{GLYPH['add']} Add medicine",
                lambda *_: self._edit_medicine(None),
                "btn-add",
            ),
            False,
            False,
            0,
        )
        box.pack_end(
            _button(f"{GLYPH['refresh']} Refresh", lambda *_: self.refresh(), "btn-ghost"),
            False,
            False,
            0,
        )
        box.pack_end(
            _button(f"{GLYPH['close']} Close", lambda *_: self.close(), "btn-ghost"),
            False,
            False,
            0,
        )
        return box

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------
    def _safety(self, hp: dict) -> list[Gtk.Widget]:
        out: list[Gtk.Widget] = []

        findings = hp["interactions"]["items"]
        card, content = self._card(
            "DRUG INTERACTIONS", right=self._count_chip(len(findings), "interactions")
        )
        shown = [
            row
            for row in findings
            if self._matches(
                row["a"], row["b"], row["effect"], row["advice"], row["severityLabel"]
            )
        ]
        if not findings:
            content.pack_start(
                self._empty_state(GLYPH["check"], "No drug–drug interactions flagged."),
                False,
                False,
                0,
            )
        elif not shown:
            content.pack_start(
                self._empty_state(GLYPH["search"], f'No interaction matches "{self._query}"'),
                False,
                False,
                0,
            )
        for row in shown:
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(
                self._chip(row["severityLabel"], self._severity_css(row["severity"])),
                False,
                False,
                0,
            )
            pair = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_XS + 2)
            pair.pack_start(self._match_label(row["a"]), False, False, 0)
            pair.pack_start(_label("+", "muted"), False, False, 0)
            pair.pack_start(self._match_label(row["b"]), False, False, 0)
            head.pack_start(pair, True, True, 0)
            if row.get("nsaidBp"):
                head.pack_end(
                    self._glyph_chip(GLYPH["warn"], "BP risk", "chip-danger"),
                    False,
                    False,
                    0,
                )
            detail.pack_start(head, False, False, 0)
            if row.get("effect"):
                detail.pack_start(
                    self._match_label(row["effect"], "muted"), False, False, 0
                )
            if row.get("advice"):
                detail.pack_start(
                    self._match_label(row["advice"], "muted"), False, False, 0
                )
            content.pack_start(detail, False, False, 0)
        out.append(card)

        alerts = hp["food"]["alerts"]
        card, content = self._card(
            "FOOD AND MEAL TIMING", right=self._count_chip(len(alerts), "alerts")
        )
        shown = [
            row
            for row in alerts
            if self._matches(
                row.get("medicine"), row.get("label"), row.get("tip"), row.get("severityLabel")
            )
        ]
        if not alerts:
            content.pack_start(
                self._empty_state(
                    GLYPH["check"], "No meal-timing alerts for your list."
                ),
                False,
                False,
                0,
            )
        elif not shown:
            content.pack_start(
                self._empty_state(GLYPH["search"], f'No food advice matches "{self._query}"'),
                False,
                False,
                0,
            )
        for row in shown:
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(
                self._chip(
                    str(row.get("severityLabel", "")).title(),
                    self._severity_css(row.get("severity", "")),
                ),
                False,
                False,
                0,
            )
            head.pack_start(
                self._match_label(str(row.get("medicine", "")), ellipsize=True),
                True,
                True,
                0,
            )
            if row.get("label"):
                head.pack_end(
                    self._match_label(str(row["label"]), "muted", ltr=True),
                    False,
                    False,
                    0,
                )
            detail.pack_start(head, False, False, 0)
            if row.get("tip"):
                detail.pack_start(self._match_label(str(row["tip"]), "muted"), False, False, 0)
            content.pack_start(detail, False, False, 0)
        out.append(card)

        pregnancy = hp["pregnancy"]
        card, content = self._card(
            "PREGNANCY",
            right=self._count_chip(pregnancy["count"], "findings"),
        )
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        head.pack_start(
            self._chip(pregnancy["statusLabel"], "chip-due" if pregnancy["active"] else "chip-idle"),
            False,
            False,
            0,
        )
        if pregnancy["countFlagged"]:
            head.pack_start(
                self._glyph_chip(
                    GLYPH["warn"], f"{pregnancy['countFlagged']} to avoid", "chip-danger"
                ),
                False,
                False,
                0,
            )
        content.pack_start(head, False, False, 0)
        if not pregnancy["active"]:
            content.pack_start(
                _label(
                    "Profile status is off — nothing to check.",
                    "muted",
                ),
                False,
                False,
                0,
            )
        for row in pregnancy["findings"]:
            if not self._matches(
                row["name"], row["generic"], row["riskLabel"], row["note"], row["alternative"]
            ):
                continue
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(
                self._chip(row["riskLabel"], self._severity_css(row["risk"])),
                False,
                False,
                0,
            )
            head.pack_start(
                self._match_label(row["name"], ellipsize=True), True, True, 0
            )
            detail.pack_start(head, False, False, 0)
            if row.get("note"):
                detail.pack_start(
                    self._match_label(row["note"], "muted"), False, False, 0
                )
            if row.get("alternative"):
                detail.pack_start(
                    self._match_label(f"alternative: {row['alternative']}", "muted"),
                    False,
                    False,
                    0,
                )
            content.pack_start(detail, False, False, 0)
        content.pack_start(
            _label(pregnancy["consult"], "disclaimer"), False, False, 0
        )
        out.append(card)

        missed = hp["missed"]
        card, content = self._card(
            "MISSED DOSE PROTOCOL", right=self._count_chip(missed["count"], "missed")
        )
        if missed["alert"]:
            content.pack_start(
                self._glyph_chip(
                    GLYPH["warn"],
                    f"{missed['count']} missed today — over the {missed['threshold']} alert line",
                    "chip-danger",
                ),
                False,
                False,
                0,
            )
        if not missed["missed"] and not missed["protocols"]:
            content.pack_start(
                self._empty_state(GLYPH["check"], "Nothing missed today."),
                False,
                False,
                0,
            )
        for row in missed["forMissed"]:
            if not self._matches(
                row.get("name"), row.get("dose"), row.get("clock"), row.get("text")
            ):
                continue
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(self._chip(str(row.get("clock", "")), "chip-time"), False, False, 0)
            head.pack_start(
                self._match_label(str(row.get("name", "")), ellipsize=True), True, True, 0
            )
            head.pack_end(
                self._badge(
                    f"{row.get('minutesLate', 0)}m late", "badge-late", GLYPH["late"]
                ),
                False,
                False,
                0,
            )
            detail.pack_start(head, False, False, 0)
            if row.get("text"):
                detail.pack_start(
                    self._match_label(str(row["text"]), "muted"), False, False, 0
                )
            content.pack_start(detail, False, False, 0)
        protocols = [
            row
            for row in missed["protocols"]
            if self._matches(row.get("name"), row.get("text"), row.get("sourceLabel"))
        ]
        if protocols and missed["missed"]:
            content.pack_start(_label("REFERENCE", "section"), False, False, 0)
        for row in protocols[:6]:
            detail = self._detail()
            detail.pack_start(
                self._match_label(
                    f"{row['name']} — {row['sourceLabel']}", ellipsize=True
                ),
                False,
                False,
                0,
            )
            detail.pack_start(
                self._match_label(str(row.get("text", "")), "muted"), False, False, 0
            )
            content.pack_start(detail, False, False, 0)
        content.pack_start(_label(missed["disclaimer"], "disclaimer"), False, False, 0)
        out.append(card)
        return out

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def _health_section(self, hp: dict) -> list[Gtk.Widget]:
        out: list[Gtk.Widget] = []

        adherence = hp["adherence"]
        week = adherence["weekly"]
        month = adherence["monthly"]
        streak = adherence["streak"]
        card, content = self._card(
            "ADHERENCE",
            right=self._chip(
                week["label"] if week["label"] != "—" else "no data",
                "chip-due" if not week["below"] else "chip-danger",
            ),
        )
        summary = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_LG)
        for title, value, sub in (
            ("7 days", week["label"], f"{week['taken']}/{week['scheduled']} taken"),
            ("30 days", month["label"], f"{month['belowDays']} below target"),
            ("streak", str(streak["days"]), streak["label"]),
            ("today", adherence["daily"]["label"], adherence["daily"]["text"]),
        ):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            cell.pack_start(_label(title.upper(), "section"), False, False, 0)
            cell.pack_start(_label(str(value), "title", ltr=True), False, False, 0)
            cell.pack_start(_label(sub, "muted", ltr=True), False, False, 0)
            summary.pack_start(cell, True, True, 0)
        content.pack_start(summary, False, False, 0)
        values = [day["pct"] for day in week["days"]]
        labels = [str(day.get("weekday", ""))[:2] for day in week["days"]]
        content.pack_start(
            self._chart(values, labels, threshold=week["threshold"]), False, False, 0
        )
        content.pack_start(_label("THRESHOLD LINE IS THE TARGET", "disclaimer"), False, False, 0)
        out.append(card)

        vitals = hp["vitals"]
        summary_data = vitals["summary"]
        chart_data = vitals["chart"]
        card, content = self._card(
            "VITALS", right=self._count_chip(summary_data["count"], "readings / 7d")
        )
        if not summary_data["types"]:
            content.pack_start(
                self._empty_state(
                    GLYPH["water"], "No readings in the last 7 days."
                ),
                False,
                False,
                0,
            )
        for row in summary_data["types"]:
            if not self._matches(row["label"], row["unit"]):
                continue
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(self._match_label(row["label"]), True, True, 0)
            latest = "—" if row["latest"] is None else f"{row['latest']}"
            if row.get("latest2"):
                latest = f"{row['latest']} / {row['latest2']}"
            head.pack_end(
                _label(f"{latest} {row['unit']}".strip(), "mono", ltr=True),
                False,
                False,
                0,
            )
            detail.pack_start(head, False, False, 0)
            stats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_MD)
            for tag, key in (("min", "min"), ("avg", "avg"), ("max", "max")):
                value = row.get(key)
                text = "—" if value is None else str(value)
                if key == "avg" and row.get("avg2"):
                    text = f"{value} / {row['avg2']}"
                stats.pack_start(
                    _label(f"{tag} {text}", "muted", ltr=True), False, False, 0
                )
            detail.pack_start(stats, False, False, 0)
            content.pack_start(detail, False, False, 0)
        if chart_data["count"]:
            for kind in sorted(chart_data["series"]):
                points = chart_data["series"][kind]
                spec = chart_data["kinds"].get(kind, {})
                if not self._matches(spec.get("label", kind)):
                    continue
                content.pack_start(
                    _label(str(spec.get("label", kind)).upper(), "section"),
                    False,
                    False,
                    0,
                )
                content.pack_start(
                    self._chart(
                        [p.get("value") for p in points],
                        [str(p.get("clock", "")) for p in points],
                        values2=(
                            [p.get("value2") for p in points]
                            if spec.get("two")
                            else None
                        ),
                        caption=str(spec.get("unit", "")),
                    ),
                    False,
                    False,
                    0,
                )
        out.append(card)

        effects = hp["sideEffects"]
        week_effects = effects["week"]
        card, content = self._card(
            "SIDE EFFECTS",
            right=self._count_chip(effects["count"], "in 30 days"),
        )
        severity_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        for name in ("mild", "moderate", "severe"):
            count = week_effects["bySeverity"].get(name, 0)
            severity_row.pack_start(
                self._chip(f"{name} · {count}", self._severity_css(name)), False, False, 0
            )
        content.pack_start(severity_row, False, False, 0)
        for row in week_effects["byMedicine"]:
            count = week_effects["byMedicine"][row]
            if not self._matches(row):
                continue
            content.pack_start(
                _label(f"{row} — {count} report(s)", "muted"), False, False, 0
            )
        for repeat in effects["repeats"]:
            if not self._matches(repeat["medicine"], repeat["effect"]):
                continue
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(
                self._glyph_chip(
                    GLYPH["warn"],
                    f"repeat {repeat['count']}×",
                    self._severity_css(repeat.get("worst", "")),
                ),
                False,
                False,
                0,
            )
            head.pack_start(
                self._match_label(
                    f"{repeat['effect']} with {repeat['medicine']}", ellipsize=True
                ),
                True,
                True,
                0,
            )
            detail.pack_start(head, False, False, 0)
            detail.pack_start(
                _label(
                    f"first {repeat['first']} · last {repeat['last']}", "muted", ltr=True
                ),
                False,
                False,
                0,
            )
            content.pack_start(detail, False, False, 0)
        if not week_effects["total"] and not effects["repeats"]:
            content.pack_start(
                self._empty_state(
                    GLYPH["check"], "No side effects reported in the last 7 days."
                ),
                False,
                False,
                0,
            )
        content.pack_start(
            _label(
                "This is not medical advice — mention repeats to your doctor or pharmacist.",
                "disclaimer",
            ),
            False,
            False,
            0,
        )
        out.append(card)

        refills = hp["refills"]
        card, content = self._card(
            "SUPPLY",
            right=self._count_chip(refills["countWarn"], "to refill"),
        )
        if refills["out"]:
            content.pack_start(
                self._glyph_chip(
                    GLYPH["emergency"],
                    f"{len(refills['out'])} OUT OF STOCK",
                    "chip-out",
                ),
                False,
                False,
                0,
            )
        rows = refills["medicines"]
        shown = [row for row in rows if self._matches(row["name"], row.get("dose"))]
        if not rows:
            content.pack_start(
                self._empty_state(
                    GLYPH["refill"], "No counted medicine — set a pill count to track supply."
                ),
                False,
                False,
                0,
            )
        elif not shown:
            content.pack_start(
                self._empty_state(GLYPH["search"], f'No medicine matches "{self._query}"'),
                False,
                False,
                0,
            )
        for row in shown[:12]:
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(self._match_label(row["name"], ellipsize=True), True, True, 0)
            head.pack_end(
                self._chip(
                    "OUT · 0 left"
                    if row["out"]
                    else (f"{row['stock']} pills" if row["stock"] is not None else "—"),
                    "chip-out" if row["out"] else ("chip-due" if row["warn"] else "chip-stock"),
                ),
                False,
                False,
                0,
            )
            detail.pack_start(head, False, False, 0)
            days = "unknown pace" if row["daysLeft"] is None else f"{row['daysLeft']}d left"
            detail.pack_start(
                _label(
                    f"{days} · {row['perDay']}/day · refill at {row['refillAt']} · "
                    f"runs out {row['runOut']}",
                    "muted",
                    ltr=True,
                ),
                False,
                False,
                0,
            )
            content.pack_start(detail, False, False, 0)
        if refills["countWarn"]:
            content.pack_start(
                _button(
                    f"{GLYPH['refill']} Refill all low ({refills['countWarn']})",
                    lambda *_: self._refill(),
                    "btn-refill",
                ),
                False,
                False,
                0,
            )
        out.append(card)
        return out

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    def _reports(self, document: MedicineFile, history, hp: dict) -> list[Gtk.Widget]:
        out: list[Gtk.Widget] = []

        state = hp["review"]
        card, content = self._card("MEDICATION REVIEW")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        head.pack_start(
            self._chip(
                "due now" if state["due"] else f"in {state['daysLeft']} days",
                "chip-danger" if state["due"] else "chip-due",
            ),
            False,
            False,
            0,
        )
        head.pack_start(
            _label(f"last {state['lastLabel']} · next {state['nextLabel']}", "muted", ltr=True),
            True,
            True,
            0,
        )
        content.pack_start(head, False, False, 0)
        if state.get("duplicates"):
            for row in state["duplicates"]:
                detail = self._detail()
                head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
                head.pack_start(
                    self._chip(
                        str(row.get("severityLabel", "duplicate")),
                        self._severity_css(str(row.get("severity", ""))),
                    ),
                    False,
                    False,
                    0,
                )
                head.pack_start(
                    self._match_label(str(row.get("concept", "")), ellipsize=True),
                    True,
                    True,
                    0,
                )
                detail.pack_start(head, False, False, 0)
                detail.pack_start(
                    self._match_label(str(row.get("text", "")), "muted"), False, False, 0
                )
                content.pack_start(detail, False, False, 0)
        elif state.get("never"):
            content.pack_start(
                _label("Never reviewed — start with an export.", "muted"),
                False,
                False,
                0,
            )
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        buttons.pack_start(
            _button(f"{GLYPH['clipboard']} Mark reviewed", self._mark_reviewed, "btn-primary"),
            False,
            False,
            0,
        )
        buttons.pack_start(
            _button(f"{GLYPH['chart']} Export PDF", self._export_pdf, "btn-refill"),
            False,
            False,
            0,
        )
        content.pack_start(buttons, False, False, 0)
        if state["history"]:
            content.pack_start(_label("HISTORY", "section"), False, False, 0)
            for entry in state["history"][-6:]:
                text = str(entry.get("date", ""))
                if entry.get("exported"):
                    text += f" · exported"
                content.pack_start(_label(text, "muted", ltr=True), False, False, 0)
        out.append(card)

        for title, report in (
            ("WEEKLY REPORT", hp["reports"]["weekly"]),
            ("MONTHLY REPORT", hp["reports"]["monthly"]),
        ):
            card, content = self._card(title)
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_LG)
            for tag, key in (
                ("window", "end"),
                ("adherence", "label"),
                ("scheduled", "scheduled"),
                ("missed", "missed"),
            ):
                cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                cell.pack_start(_label(tag.upper(), "section"), False, False, 0)
                value = report.get(key)
                cell.pack_start(_label(str(value), "title", ltr=True), False, False, 0)
                head.pack_start(cell, True, True, 0)
            content.pack_start(head, False, False, 0)
            if report.get("below"):
                content.pack_start(
                    self._glyph_chip(
                        GLYPH["warn"],
                        f"below the {report['threshold']}% target",
                        "chip-danger",
                    ),
                    False,
                    False,
                    0,
                )
            if title.startswith("MONTHLY") and report.get("best") and report.get("worst"):
                stats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_MD)
                stats.pack_start(
                    _label(
                        f"best {report['best'].get('date')} · {report['best'].get('label')}",
                        "muted",
                        ltr=True,
                    ),
                    False,
                    False,
                    0,
                )
                stats.pack_start(
                    _label(
                        f"worst {report['worst'].get('date')} · {report['worst'].get('label')}",
                        "muted",
                        ltr=True,
                    ),
                    False,
                    False,
                    0,
                )
                content.pack_start(stats, False, False, 0)
            series = report.get("days") or report.get("series") or []
            if series:
                values = [day["pct"] for day in series]
                labels = [str(day.get("weekday", ""))[:2] for day in series]
                content.pack_start(
                    self._chart(values, labels, threshold=report["threshold"]),
                    False,
                    False,
                    0,
                )
            body = "\n".join(
                line
                for line in report.get("lines", [])
                if line and not line.startswith("This is not medical")
            )
            if body and self._query:
                if self._query not in body.lower():
                    content.pack_start(
                        self._empty_state(
                            GLYPH["search"], f'No report line matches "{self._query}"'
                        ),
                        False,
                        False,
                        0,
                    )
                else:
                    content.pack_start(
                        self._match_label(body, "muted"), False, False, 0
                    )
            elif body:
                content.pack_start(_label(body, "muted"), False, False, 0)
            out.append(card)

        card, content = self._card("SOURCES")
        for source in hp["sources"]:
            if not self._matches(source):
                continue
            content.pack_start(_label(str(source), "muted"), False, False, 0)
        content.pack_start(
            _label(f"knowledge snapshot {hp['updated']}", "disclaimer", ltr=True),
            False,
            False,
            0,
        )
        content.pack_start(_label(hp["disclaimer"], "disclaimer"), False, False, 0)
        out.append(card)
        return out

    def _mark_reviewed(self, *_ignored) -> None:
        review.mark_reviewed()
        self._toast("review marked as done")
        self.refresh()

    def _export_pdf(self, *_ignored) -> None:
        try:
            data = review.report(
                [medicine for medicine in load_medicines().medicines if medicine.active],
                actions.snapshot()[2],
            )
            path = review.export_pdf(data)
        except Exception as error:  # pragma: no cover - defensive
            self._say(f"export failed: {error}", error=True)
            return
        self._toast(f"written {path.name}")

    # ------------------------------------------------------------------
    # Card
    # ------------------------------------------------------------------
    def _card_section(self, hp: dict) -> list[Gtk.Widget]:
        card_data = hp["emergency"]
        profile = hp["profile"]
        out: list[Gtk.Widget] = []

        card, content = self._card("ALLERGIES")
        content.pack_start(
            self._text_row(
                "Comma separated",
                ", ".join(card_data["allergies"]),
                lambda text: emergency.set_field("allergies", text),
            ),
            False,
            False,
            0,
        )
        out.append(card)

        card, content = self._card("CHRONIC CONDITIONS")
        content.pack_start(
            self._text_row(
                "Comma separated",
                ", ".join(card_data["conditions"]),
                lambda text: emergency.set_field("conditions", text),
            ),
            False,
            False,
            0,
        )
        out.append(card)

        card, content = self._card(
            "MEDICAL STATUS",
            right=self._chip(
                card_data["bloodType"] or "blood type unknown",
                "chip-due" if card_data["bloodType"] else "chip-idle",
            ),
        )
        grid = Gtk.Grid(column_spacing=GAP_MD, row_spacing=GAP_SM)
        fields = [
            ("NAME", "name", card_data["name"]),
            ("BIRTH DATE", "birth_date", card_data["birthDate"]),
            ("BLOOD TYPE", "blood_type", card_data["bloodType"]),
        ]
        self._profile_entries: dict[str, Gtk.Entry] = {}
        for index, (label_text, key, value) in enumerate(fields):
            entry = Gtk.Entry()
            entry.set_text(str(value or ""))
            entry.set_placeholder_text(label_text.title())
            self._profile_entries[key] = entry
            grid.attach(_label(label_text, "section"), 0, index, 1, 1)
            entry.set_hexpand(True)
            grid.attach(entry, 1, index, 1, 1)
        statuses = ("none", "pregnant", "breastfeeding", "trying", "postpartum")
        combo = Gtk.ComboBoxText()
        for option in statuses:
            combo.append_text(option)
        combo.set_active(max(0, statuses.index(str(profile.get("status", "none")))))
        self._profile_status = combo
        grid.attach(_label("STATUS", "section"), 0, len(fields), 1, 1)
        combo.set_hexpand(True)
        grid.attach(combo, 1, len(fields), 1, 1)
        content.pack_start(grid, False, False, 0)
        content.pack_start(
            _button(
                f"{GLYPH['check']} Save status",
                lambda *_: self._save_profile(),
                "btn-primary",
            ),
            False,
            False,
            0,
        )
        out.append(card)

        card, content = self._card(
            "CURRENT MEDICATIONS",
            right=self._count_chip(len(card_data["medicines"]), "active"),
        )
        for row in card_data["medicines"]:
            if not self._matches(row["name"], row["dose"], row["times"], row["note"]):
                continue
            detail = self._detail()
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            head.pack_start(
                pill_icon(row["name"], 22),
                False,
                False,
                0,
            )
            head.pack_start(self._match_label(row["name"], ellipsize=True), True, True, 0)
            if row["emergency"]:
                head.pack_end(
                    self._glyph_chip(GLYPH["emergency"], "emergency", "chip-danger"),
                    False,
                    False,
                    0,
                )
            detail.pack_start(head, False, False, 0)
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            if row["dose"]:
                line.pack_start(self._match_label(row["dose"], ltr=True), False, False, 0)
            if row["times"]:
                line.pack_start(self._match_label(row["times"], "muted", ltr=True), False, False, 0)
            detail.pack_start(line, False, False, 0)
            if row["note"]:
                detail.pack_start(
                    self._match_label(row["note"], "muted"), False, False, 0
                )
            content.pack_start(detail, False, False, 0)
        if not card_data["medicines"]:
            content.pack_start(
                self._empty_state(GLYPH["clipboard"], "No active medicine on the card."),
                False,
                False,
                0,
            )
        out.append(card)

        card, content = self._card("CONTACTS")
        contacts = [
            (
                "EMERGENCY CONTACT",
                "emergency_contact",
                card_data.get("emergencyContact") or {},
                card_data.get("emergencyPhone", ""),
            ),
            (
                "DOCTOR",
                "doctor",
                card_data.get("doctor") or {},
                card_data.get("doctorPhone", ""),
            ),
            (
                "PHARMACY",
                "pharmacy",
                profile.get("pharmacy") or {},
                str((profile.get("pharmacy") or {}).get("phone", "")),
            ),
        ]
        grid = Gtk.Grid(column_spacing=GAP_MD, row_spacing=GAP_SM)
        self._contact_entries: dict[str, tuple[Gtk.Entry, Gtk.Entry]] = {}
        for index, (label_text, key, data, phone) in enumerate(contacts):
            name_entry = Gtk.Entry()
            name_entry.set_text(str(data.get("name", "")))
            name_entry.set_placeholder_text("Name")
            # Narrow request: the grid stretches them to fill the card anyway,
            # and a default sixteen-character entry would set the window width.
            name_entry.set_width_chars(8)
            name_entry.set_max_width_chars(24)
            phone_entry = Gtk.Entry()
            phone_entry.set_text(str(phone or data.get("phone", "")))
            phone_entry.set_placeholder_text("+20 …")
            phone_entry.set_width_chars(8)
            phone_entry.set_max_width_chars(24)
            phone_entry.set_direction(Gtk.TextDirection.LTR)
            self._contact_entries[key] = (name_entry, phone_entry)
            grid.attach(_label(label_text, "section"), 0, index, 1, 1)
            pair = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
            name_entry.set_hexpand(True)
            phone_entry.set_hexpand(True)
            pair.pack_start(name_entry, True, True, 0)
            pair.pack_start(phone_entry, True, True, 0)
            grid.attach(pair, 1, index, 1, 1)
        content.pack_start(grid, False, False, 0)
        content.pack_start(
            _button(
                f"{GLYPH['check']} Save contacts",
                lambda *_: self._save_contacts(),
                "btn-primary",
            ),
            False,
            False,
            0,
        )
        if card_data.get("updatedDate"):
            content.pack_start(
                _label(f"card updated {card_data['updatedDate']}", "disclaimer", ltr=True),
                False,
                False,
                0,
            )
        out.append(card)

        card, content = self._card("DISCLAIMER", "card")
        content.pack_start(_label(card_data["disclaimer"], "disclaimer"), False, False, 0)
        content.pack_start(
            _label("Local data only — nothing leaves this machine.", "disclaimer"),
            False,
            False,
            0,
        )
        out.append(card)
        return out

    def _text_row(self, placeholder: str, value: str, save) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GAP_SM)
        entry = Gtk.Entry()
        entry.set_text(value)
        entry.set_placeholder_text(placeholder)
        entry.set_hexpand(True)
        box.pack_start(entry, True, True, 0)
        button = _button(
            GLYPH["check"] + " Save",
            lambda *_: self._save_field(entry, save),
            "btn-primary",
        )
        box.pack_end(button, False, False, 0)
        return box

    def _save_field(self, entry: Gtk.Entry, save) -> None:
        try:
            save(entry.get_text().strip())
        except Exception as error:
            self._say(str(error), error=True)
            return
        self._toast("saved")
        self.refresh()

    def _save_profile(self) -> None:
        updates = {
            key: entry.get_text().strip()
            for key, entry in self._profile_entries.items()
        }
        updates["status"] = self._profile_status.get_active_text() or "none"
        try:
            emergency.save(updates)
        except Exception as error:
            self._say(str(error), error=True)
            return
        self._toast("medical status saved")
        self.refresh()

    def _save_contacts(self) -> None:
        try:
            for key, (name_entry, phone_entry) in self._contact_entries.items():
                emergency.set_field(
                    key,
                    f"{name_entry.get_text().strip()} | {phone_entry.get_text().strip()}",
                )
        except Exception as error:
            self._say(str(error), error=True)
            return
        self._toast("contacts saved")
        self.refresh()

    # ------------------------------------------------------------------
    # charts
    # ------------------------------------------------------------------
    def _chart(
        self,
        values,
        labels=None,
        *,
        threshold: float | None = None,
        values2=None,
        caption: str = "",
        height: int = 118,
    ) -> Gtk.Widget:
        area = Gtk.DrawingArea()
        area.set_size_request(-1, height)
        _add_class(area, "chart")
        area.connect(
            "draw",
            self._draw_chart,
            list(values),
            list(labels or []),
            threshold,
            list(values2) if values2 else None,
            caption,
        )
        return area

    def _draw_chart(
        self, area, context, values, labels, threshold, values2, caption
    ) -> bool:
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        if width < 60 or height < 40:
            return False

        present = [value for value in values if value is not None]
        if not present:
            context.set_font_size(9)
            _paint(context, MUTE)
            text = "no data yet"
            extents = context.text_extents(text)
            context.move_to((width - extents.width) / 2.0, height / 2.0)
            context.show_text(text)
            return False

        x0, x1 = 8.0, float(width - 8)
        y0, y1 = 14.0, float(height - 16)
        span_x = max(1.0, x1 - x0)
        span_y = max(1.0, y1 - y0)

        pool = list(present)
        if values2:
            pool.extend(value for value in values2 if value is not None)
        if threshold is not None:
            pool.append(float(threshold))
        lo, hi = min(pool), max(pool)
        if hi - lo < 1e-9:
            lo, hi = lo - 1.0, hi + 1.0
        else:
            pad = (hi - lo) * 0.15
            lo, hi = lo - pad, hi + pad

        count = len(values)

        def x_of(index: int) -> float:
            if count <= 1:
                return (x0 + x1) / 2.0
            return x0 + span_x * index / float(count - 1)

        def y_of(value: float) -> float:
            return y1 - (value - lo) / (hi - lo) * span_y

        _paint(context, CHART_GRID)
        context.set_line_width(1.0)
        for step in range(3):
            y_value = y0 + span_y * step / 2.0
            context.move_to(x0, y_value)
            context.line_to(x1, y_value)
        context.stroke()

        if threshold is not None:
            y_value = y_of(float(threshold))
            _paint(context, FG0, 0.75)
            context.set_dash([4.0, 4.0])
            context.move_to(x0, y_value)
            context.line_to(x1, y_value)
            context.stroke()
            context.set_dash([])
            context.set_font_size(9)
            text = f"{round(float(threshold))}% target"
            extents = context.text_extents(text)
            context.move_to(x1 - extents.width, max(y0, y_value - 4))
            context.show_text(text)

        def segments(series):
            out, current = [], []
            for index, value in enumerate(series):
                if value is None:
                    if len(current) > 1:
                        out.append(current)
                    current = []
                    continue
                current.append((x_of(index), y_of(float(value))))
            if len(current) > 1:
                out.append(current)
            return out

        for segment in segments(values):
            context.new_path()
            context.move_to(segment[0][0], y1)
            for x_value, y_value in segment:
                context.line_to(x_value, y_value)
            context.line_to(segment[-1][0], y1)
            context.close_path()
            _paint(context, CHART_FILL)
            context.fill()

            context.new_path()
            context.move_to(segment[0][0], segment[0][1])
            for x_value, y_value in segment[1:]:
                context.line_to(x_value, y_value)
            _paint(context, CHART_LINE)
            context.set_line_width(1.6)
            context.stroke()

        if values2:
            for segment in segments(values2):
                context.new_path()
                context.move_to(segment[0][0], segment[0][1])
                for x_value, y_value in segment[1:]:
                    context.line_to(x_value, y_value)
                _paint(context, MUTE)
                context.set_line_width(1.3)
                context.set_dash([3.0, 3.0])
                context.stroke()
                context.set_dash([])

        if count <= 14:
            for index, value in enumerate(values):
                if value is None:
                    continue
                context.new_path()
                context.arc(x_of(index), y_of(float(value)), 2.4, 0, 6.283185307179586)
                _paint(context, FG0)
                context.fill()

        context.set_font_size(9)
        _paint(context, MUTE)
        if labels:
            context.move_to(x0, height - 4)
            context.show_text(str(labels[0]))
            last = str(labels[-1])
            extents = context.text_extents(last)
            context.move_to(x1 - extents.width, height - 4)
            context.show_text(last)
        if caption:
            context.move_to(x0, y0 - 4)
            context.show_text(caption)
        return False

    # ------------------------------------------------------------------
    # actions + forms
    # ------------------------------------------------------------------
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

    def _edit_medicine(self, name: str | None, *_ignored, emergency_medicine: bool = False) -> None:
        document, _, _ = actions.snapshot()
        existing = document.by_name(name) if name else None
        form = MedicineForm(self, existing, emergency=emergency_medicine)
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
        if name in self._row_names:
            self._cursor = -1
        self._toast(message)
        self.refresh()


class EmergencyWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window | None = None) -> None:
        super().__init__(title="MedKit — EMERGENCY")
        self.set_default_size(480, 380)
        if parent is not None:
            self.set_transient_for(parent)
        self._parent_win = parent

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_MD)
        shell.set_border_width(16)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        head.pack_start(_label("EMERGENCY MEDICINES", "section"), True, True, 0)
        head.pack_end(
            _button(f"{GLYPH['add']} Add medicine", self._add_medicine, "btn-add"),
            False,
            False,
            0,
        )
        shell.pack_start(head, False, False, 0)
        self._rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_MD)
        shell.pack_start(self._rows, True, True, 0)
        shell.pack_end(
            _button(f"{GLYPH['close']} Close", lambda *_: self.close(), "btn-ghost"),
            False,
            False,
            0,
        )
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
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP_XS)
        _add_class(card, "card card-danger")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        head.pack_start(pill_icon(medicine.name, 26), False, False, 0)
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        name_box.pack_start(_label(medicine.name), False, False, 0)
        detail = medicine.dose or "—"
        name_box.pack_start(_label(detail, "muted", ltr=True), False, False, 0)
        if medicine.times:
            for clock in medicine.times:
                name_box.pack_start(_label(clock, "chip chip-time"), False, False, 0)
        head.pack_start(name_box, True, True, 0)
        name = medicine.name
        head.pack_end(
            _button(GLYPH["delete"], lambda *_: self._delete(name), "btn-del"), False, False, 0
        )
        head.pack_end(
            _button(GLYPH["edit"], lambda *_: self._edit(name), "btn-edit"), False, False, 0
        )
        if medicine.is_out():
            state, chip_css = "OUT OF STOCK", "chip-out"
        elif medicine.is_low():
            state, chip_css = "LOW", "chip-due"
        else:
            state, chip_css = "ok", "chip-taken"
        head.pack_end(_label(state, f"chip {chip_css}"), False, False, 0)
        stock = "not counted" if medicine.stock is None else str(medicine.stock)
        head.pack_end(_label(f"{stock} pills", "chip chip-stock"), False, False, 0)
        course = f"for {medicine.days} days" if medicine.days else "ongoing"
        head.pack_end(_label(course, "chip chip-time"), False, False, 0)
        card.pack_start(head, False, False, 0)
        if medicine.notes:
            card.pack_start(
                _label(f"Note: {medicine.notes}", "muted"), False, False, 0
            )
        card.pack_start(
            _label(f"Contacts: {medicine.emergency_contacts or '—'}", "muted", ltr=True),
            False,
            False,
            0,
        )
        return card


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

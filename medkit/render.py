from __future__ import annotations

from pathlib import Path

import cairo

from . import paths

SIZE = 64
ICON_VERSION = 2

BG2 = (0.086, 0.094, 0.110)
FG0 = (0.949, 0.957, 0.969)

PALETTE: dict[str, tuple[float, float, float]] = {
    "neutral": (0.35, 0.38, 0.41),
    "green": (0.76, 0.79, 0.83),
    "amber": (0.95, 0.96, 0.97),
    "red": (0.55, 0.57, 0.61),
}
BADGE_COLOR = (0.90, 0.91, 0.93)


def icon_name(color: str, badge: int = 0) -> str:
    return f"medkit-{_safe_color(color)}{_suffix(badge)}-v{ICON_VERSION}"


def icon_file(color: str, badge: int = 0) -> Path:
    color = _safe_color(color)
    badge = max(0, min(99, badge))
    path = paths.icon_dir() / f"{icon_name(color, badge)}.png"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    _render(path, color, badge)
    return path


def _safe_color(color: str) -> str:
    return color if color in PALETTE else "neutral"


def _suffix(badge: int) -> str:
    return f"-{max(0, min(99, badge))}" if badge else ""


def _pill_path(context: cairo.Context, half_w: float, half_h: float, drop: float = 0.0) -> None:
    context.new_sub_path()
    context.arc(half_w - half_h, drop, half_h, -1.5708, 1.5708)
    context.arc(-(half_w - half_h), drop, half_h, 1.5708, 4.7124)
    context.close_path()


def _badge(context: cairo.Context, badge: int) -> None:
    cx, cy, radius = SIZE - 13, SIZE - 13, 12
    context.set_source_rgb(*BG2)
    context.arc(cx, cy, radius, 0, 6.2832)
    context.fill()
    context.set_line_width(2)
    context.set_source_rgb(*FG0)
    context.arc(cx, cy, radius, 0, 6.2832)
    context.stroke()
    text = str(badge)
    context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    context.set_font_size(13)
    extents = context.text_extents(text)
    context.set_source_rgb(*FG0)
    context.move_to(
        cx - extents.width / 2 - extents.x_bearing,
        cy - extents.height / 2 - extents.y_bearing,
    )
    context.show_text(text)


def _render(path: Path, color: str, badge: int) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    context = cairo.Context(surface)
    context.set_source_rgba(0, 0, 0, 0)
    context.paint()

    half_w, half_h = SIZE * 0.42, SIZE * 0.21
    context.save()
    context.translate(SIZE / 2, SIZE / 2)
    context.rotate(-0.7854)
    context.set_source_rgb(*FG0)
    _pill_path(context, half_w, half_h)
    if color == "green":
        context.fill()
    else:
        context.set_line_width(2)
        context.stroke()
    context.restore()

    if badge:
        _badge(context, badge)

    surface.write_to_png(str(path))

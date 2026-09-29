from __future__ import annotations

from pathlib import Path

import cairo

from . import paths

SIZE = 64
PALETTE: dict[str, tuple[float, float, float]] = {
    "neutral": (0.36, 0.39, 0.45),
    "green": (0.09, 0.64, 0.29),
    "amber": (0.96, 0.62, 0.05),
    "red": (0.86, 0.15, 0.15),
}
BADGE_COLOR = (0.86, 0.13, 0.13)


def icon_name(color: str, badge: int = 0) -> str:
    return f"medkit-{_safe_color(color)}{_suffix(badge)}"


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
    context.set_source_rgb(*BADGE_COLOR)
    context.arc(cx, cy, radius, 0, 6.2832)
    context.fill()
    context.set_line_width(2)
    context.set_source_rgb(1.0, 1.0, 1.0)
    context.arc(cx, cy, radius, 0, 6.2832)
    context.stroke()
    text = str(badge)
    context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    context.set_font_size(13)
    extents = context.text_extents(text)
    context.set_source_rgb(1.0, 1.0, 1.0)
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

    context.set_source_rgba(0.02, 0.03, 0.05, 0.35)
    _pill_path(context, half_w, half_h, SIZE * 0.06)
    context.fill()

    context.set_source_rgb(*PALETTE[color])
    _pill_path(context, half_w, half_h)
    context.fill()

    context.save()
    _pill_path(context, half_w, half_h)
    context.clip()
    context.set_source_rgb(0.97, 0.98, 1.0)
    context.rectangle(0, -half_h, half_w, half_h * 2)
    context.fill()
    context.restore()

    context.set_source_rgba(0.04, 0.06, 0.10, 0.22)
    context.set_line_width(1.5)
    context.move_to(0, -half_h + 5)
    context.line_to(0, half_h - 5)
    context.stroke()

    context.save()
    context.translate(-half_w * 0.44, -half_h * 0.40)
    context.scale(1.0, 0.38)
    context.set_source_rgba(1.0, 1.0, 1.0, 0.55)
    context.arc(0, 0, half_h * 0.55, 0, 6.2832)
    context.fill()
    context.restore()

    context.set_source_rgba(0.03, 0.05, 0.08, 0.55)
    context.set_line_width(2)
    _pill_path(context, half_w, half_h)
    context.stroke()
    context.restore()

    if badge:
        _badge(context, badge)

    surface.write_to_png(str(path))

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import paths

SIZE = 96
FRAMES = 16
FRAME_MS = 110
ART_VERSION = 2

COLORS = (
    "#38bdf8",
    "#a78bfa",
    "#f472b6",
    "#facc15",
    "#34d399",
    "#fb923c",
    "#f87171",
    "#22d3ee",
    "#4ade80",
    "#e879f9",
    "#fbbf24",
    "#60a5fa",
)

# Every medicine gets its own *shape* as well as its own colour, so a row of
# cards never reads as one pill repeated: a capsule, a scored tablet, a
# caplet, a softgel, a syrup bottle, an inhaler, a patch, a dropper.
SHAPES = (
    "capsule",
    "tablet",
    "caplet",
    "softgel",
    "bottle",
    "inhaler",
    "patch",
    "drops",
)


def color_for(name: str) -> str:
    return style_for(name)[0]


def shape_for(name: str) -> str:
    return style_for(name)[1]


def style_for(name: str) -> tuple[str, str]:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    color = COLORS[int(digest[0:2], 16) % len(COLORS)]
    shape = SHAPES[int(digest[4:6], 16) % len(SHAPES)]
    return color, shape


def rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def shade(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    if amount >= 0:
        return tuple(int(channel + (255 - channel) * amount) for channel in color)
    return tuple(int(channel * (1 + amount)) for channel in color)


def pill_gif(name: str, size: int = SIZE) -> Path:
    directory = paths.icon_dir() / "pills"
    directory.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
    path = directory / f"{slug}-v{ART_VERSION}-{size}.gif"
    if path.exists() and path.stat().st_size > 0:
        return path
    color, shape = style_for(name)
    frames = [
        _frame(math.sin(2 * math.pi * index / FRAMES) * 34, rgb(color), size, shape)
        for index in range(FRAMES)
    ]
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        transparency=255,
        disposal=2,
        optimize=False,
    )
    return path


def pill_png(name: str, size: int = SIZE) -> Path:
    """A still of the same medicine's pill — what a notification shows."""
    directory = paths.icon_dir() / "pills"
    directory.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
    path = directory / f"{slug}-v{ART_VERSION}-{size}.png"
    if path.exists() and path.stat().st_size > 0:
        return path
    color, shape = style_for(name)
    _frame(-18, rgb(color), size, shape).save(path, optimize=True)
    return path


def _frame(angle: float, color: tuple[int, int, int], size: int, shape: str) -> Image.Image:
    scale = 2
    span = size * scale
    pill = _shape(shape, color, span, scale)
    rotated = pill.rotate(angle, resample=Image.BICUBIC, center=(span / 2, span / 2))

    shadow = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    shade_layer = Image.new("RGBA", (span, span), (8, 10, 16, 255))
    shade_layer.putalpha(rotated.getchannel("A").filter(ImageFilter.GaussianBlur(3)))
    shadow.paste(shade_layer, (0, 6 * scale // 2), shade_layer)

    canvas = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(rotated)
    return canvas.resize((size, size), Image.LANCZOS)


def _shape(shape: str, color: tuple[int, int, int], span: int, scale: int) -> Image.Image:
    layer = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    builders = {
        "capsule": _capsule,
        "tablet": _tablet,
        "caplet": _caplet,
        "softgel": _softgel,
        "bottle": _bottle,
        "inhaler": _inhaler,
        "patch": _patch,
        "drops": _drops,
    }
    builders.get(shape, _capsule)(draw, color, span, scale)
    return layer


def _clamp(box, span: int) -> tuple[int, int, int, int]:
    """Keep an inner detail box inside the canvas and non-inverted.

    Icon sizes as small as 24px leave only ~48px of working space, so a fixed
    pixel inset can easily invert a box. Clamping lets the detail disappear
    at tiny sizes rather than crashing the render.
    """
    x0, y0, x1, y1 = (int(value) for value in box)
    x0 = min(max(x0, 0), span - 1)
    x1 = min(max(x1, 0), span - 1)
    y0 = min(max(y0, 0), span - 1)
    y1 = min(max(y1, 0), span - 1)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return x0, y0, x1, y1


def _outline(draw: ImageDraw.ImageDraw, box, radius: int, color, scale: int) -> None:
    draw.rounded_rectangle(box, radius=radius, outline=(16, 20, 30, 110), width=2 * scale)


def _glint(draw: ImageDraw.ImageDraw, box, span: int) -> None:
    x0, y0, x1, y1 = _clamp(box, span)
    if x1 - x0 >= 2 and y1 - y0 >= 2:
        draw.ellipse((x0, y0, x1, y1), fill=(255, 255, 255, 95))


def _fill(draw: ImageDraw.ImageDraw, box, span: int, fill) -> None:
    x0, y0, x1, y1 = _clamp(box, span)
    if x1 > x0 and y1 > y0:
        draw.rectangle((x0, y0, x1, y1), fill=fill)


def _capsule(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    width = int(span * 0.88)
    height = int(span * 0.44)
    left = (span - width) // 2
    top = (span - height) // 2
    right = left + width
    bottom = top + height
    radius = height // 2

    draw.rounded_rectangle((left, top, right, bottom), radius=radius, fill=color + (255,))
    seam = span // 2
    draw.rectangle((seam, top, right - radius, bottom), fill=(255, 255, 255, 255))
    draw.rounded_rectangle(
        (right - 2 * radius, top, right, bottom), radius=radius, fill=(255, 255, 255, 255)
    )
    _outline(draw, (left, top, right, bottom), radius, color, scale)
    draw.line((seam, top + 2, seam, bottom - 2), fill=(16, 20, 30, 70), width=scale)
    _glint(draw, (left + radius // 2, top + height // 4, seam - 4 * scale, top + height // 2 + 4), span)


def _tablet(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    pad = int(span * 0.11)
    box = (pad, pad, span - pad, span - pad)
    draw.ellipse(box, fill=color + (255,))
    ring = _clamp((pad + 5 * scale, pad + 5 * scale, span - pad - 5 * scale, span - pad - 5 * scale), span)
    if ring[2] > ring[0] and ring[3] > ring[1]:
        draw.ellipse(ring, outline=shade(color, -0.25) + (140,), width=max(1, scale))
    draw.line(
        (span // 2, pad + 8 * scale, span // 2, span - pad - 8 * scale),
        fill=shade(color, -0.45) + (200,),
        width=2 * scale,
    )
    draw.ellipse(box, outline=(16, 20, 30, 110), width=2 * scale)
    _glint(draw, (pad + 10 * scale, pad + 10 * scale, span // 2 - 6 * scale, pad + 34 * scale), span)


def _caplet(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    width = int(span * 0.86)
    height = int(span * 0.50)
    left = (span - width) // 2
    top = (span - height) // 2
    right = left + width
    bottom = top + height
    radius = height // 2

    draw.rounded_rectangle((left, top, right, bottom), radius=radius, fill=color + (255,))
    draw.line(
        (span // 2, top + 6 * scale, span // 2, bottom - 6 * scale),
        fill=shade(color, -0.45) + (200,),
        width=2 * scale,
    )
    _outline(draw, (left, top, right, bottom), radius, color, scale)
    _glint(draw, (left + 12 * scale, top + 8 * scale, span // 2 - 12 * scale, top + height // 2), span)


def _softgel(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    width = int(span * 0.84)
    height = int(span * 0.56)
    left = (span - width) // 2
    top = (span - height) // 2
    right = left + width
    bottom = top + height

    draw.ellipse((left, top, right, bottom), fill=color + (255,))
    ring = _clamp((left + 6 * scale, top + 6 * scale, right - 6 * scale, bottom - 6 * scale), span)
    if ring[2] > ring[0] and ring[3] > ring[1]:
        draw.ellipse(ring, outline=shade(color, 0.35) + (160,), width=max(1, scale))
    draw.ellipse((left, top, right, bottom), outline=(16, 20, 30, 110), width=2 * scale)
    _glint(draw, (left + 14 * scale, top + 8 * scale, left + 48 * scale, top + height // 2), span)


def _bottle(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    body_w = int(span * 0.50)
    body_h = int(span * 0.58)
    body_left = (span - body_w) // 2
    body_top = int(span * 0.34)
    body_right = body_left + body_w
    body_bottom = body_top + body_h
    radius = int(body_w * 0.16)

    cap_w = int(span * 0.30)
    cap_h = int(span * 0.14)
    cap_left = (span - cap_w) // 2
    cap_top = int(span * 0.10)

    neck_w = int(span * 0.20)
    neck_left = (span - neck_w) // 2
    neck_top = cap_top + cap_h - 2 * scale

    draw.rounded_rectangle(
        (neck_left, neck_top, neck_left + neck_w, body_top + 4 * scale),
        radius=4 * scale,
        fill=shade(color, -0.2) + (255,),
    )
    draw.rectangle(
        (body_left + radius, body_top, body_right - radius, body_bottom),
        fill=color + (255,),
    )
    draw.rounded_rectangle(
        (body_left, body_top, body_right, body_bottom), radius=radius, fill=color + (255,)
    )
    _fill(draw, (body_left + 6 * scale, body_top + int(body_h * 0.30),
                 body_right - 6 * scale, body_top + int(body_h * 0.72)),
          span, (255, 255, 255, 130))
    draw.rounded_rectangle(
        (cap_left, cap_top, cap_left + cap_w, cap_top + cap_h),
        radius=4 * scale,
        fill=shade(color, -0.4) + (255,),
        outline=(16, 20, 30, 110),
        width=2 * scale,
    )
    _outline(draw, (body_left, body_top, body_right, body_bottom), radius, color, scale)
    _glint(draw, (body_left + 8 * scale, body_top + 8 * scale,
                  body_left + 24 * scale, body_top + int(body_h * 0.32)), span)


def _inhaler(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    body_w = int(span * 0.40)
    body_h = int(span * 0.72)
    body_left = (span - body_w) // 2
    body_top = int(span * 0.10)
    body_right = body_left + body_w
    body_bottom = body_top + body_h
    radius = int(body_w * 0.24)

    mouth_w = int(span * 0.34)
    mouth_h = int(span * 0.16)
    mouth_left = body_right - int(span * 0.06)
    mouth_top = body_bottom - mouth_h - 6 * scale

    draw.rounded_rectangle(
        (body_left, body_top, body_right, body_bottom),
        radius=radius,
        fill=color + (255,),
    )
    draw.rounded_rectangle(
        (mouth_left, mouth_top, mouth_left + mouth_w, mouth_top + mouth_h),
        radius=int(mouth_h * 0.35),
        fill=shade(color, -0.35) + (255,),
    )
    _fill(draw, (body_left + 6 * scale, body_top + int(body_h * 0.18),
                 body_right - 6 * scale, body_top + int(body_h * 0.46)),
          span, (16, 20, 30, 150))
    _fill(draw, (body_left + 10 * scale, body_top + int(body_h * 0.22),
                 body_right - 10 * scale, body_top + int(body_h * 0.32)),
          span, (255, 255, 255, 120))
    _outline(draw, (body_left, body_top, body_right, body_bottom), radius, color, scale)
    _glint(draw, (body_left + 6 * scale, body_top + 8 * scale,
                  body_left + 18 * scale, body_top + int(body_h * 0.20)), span)


def _patch(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    side = int(span * 0.74)
    left = (span - side) // 2
    top = (span - side) // 2
    right = left + side
    bottom = top + side
    radius = int(side * 0.22)

    draw.rounded_rectangle((left, top, right, bottom), radius=radius, fill=color + (255,))
    inner = max(4, (side - 22 * scale) // 2)
    ring = _clamp((left + inner, top + inner, right - inner, bottom - inner), span)
    if ring[2] > ring[0] and ring[3] > ring[1]:
        draw.rounded_rectangle(
            ring,
            radius=max(2, min(radius - 10 * scale, (ring[2] - ring[0]) // 2)),
            outline=shade(color, 0.45) + (200,),
            width=max(1, scale),
        )
    pad = max(3, int(side * 0.26))
    step = max(6, 10 * scale)
    for offset in range(0, max(0, side - 2 * pad), step):
        _fill(draw, (left + pad, top + pad + offset, left + pad + scale,
                     top + pad + offset + 5 * scale), span, shade(color, -0.35) + (160,))
        _fill(draw, (left + pad + offset, top + pad, left + pad + offset + 5 * scale,
                     top + pad + scale), span, shade(color, -0.35) + (160,))
    _outline(draw, (left, top, right, bottom), radius, color, scale)


def _drops(draw: ImageDraw.ImageDraw, color, span: int, scale: int) -> None:
    # A dropper: teardrop bulb on top, tapered body below.
    tip = (span // 2, int(span * 0.12))
    body_top = int(span * 0.44)
    body_w = int(span * 0.52)
    body_left = (span - body_w) // 2
    body_right = body_left + body_w
    body_bottom = int(span * 0.90)
    radius = int(body_w * 0.30)

    draw.polygon(
        [tip, (body_left + 6 * scale, body_top), (body_right - 6 * scale, body_top)],
        fill=shade(color, -0.15) + (255,),
    )
    draw.rectangle(
        (body_left + radius, body_top, body_right - radius, body_bottom - radius),
        fill=color + (255,),
    )
    draw.rounded_rectangle(
        (body_left, body_bottom - 2 * radius, body_right, body_bottom),
        radius=radius,
        fill=color + (255,),
    )
    draw.ellipse((body_left, body_bottom - 2 * radius, body_right, body_bottom),
                 fill=color + (255,))
    _fill(draw, (body_left + 6 * scale, body_top + 8 * scale,
                 body_right - 6 * scale, body_bottom - 10 * scale),
          span, (255, 255, 255, 90))
    draw.ellipse((body_left, body_top, body_right, body_bottom),
                 outline=(16, 20, 30, 110), width=2 * scale)
    _glint(draw, (body_left + 8 * scale, body_top + 12 * scale,
                  body_left + 26 * scale, body_top + 40 * scale), span)

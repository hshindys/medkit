from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import paths

SIZE = 96
FRAMES = 16
FRAME_MS = 110
COLORS = (
    "#38bdf8",
    "#a78bfa",
    "#f472b6",
    "#facc15",
    "#34d399",
    "#fb923c",
    "#f87171",
    "#22d3ee",
)


def color_for(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return COLORS[int(digest[:2], 16) % len(COLORS)]


def rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def pill_gif(name: str, size: int = SIZE) -> Path:
    directory = paths.icon_dir() / "pills"
    directory.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
    path = directory / f"{slug}-{size}.gif"
    if path.exists() and path.stat().st_size > 0:
        return path
    color = rgb(color_for(name))
    frames = [
        _frame(math.sin(2 * math.pi * index / FRAMES) * 34, color, size)
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


def _frame(angle: float, color: tuple[int, int, int], size: int) -> Image.Image:
    scale = 2
    span = size * scale
    pill = _capsule(color, span, scale)
    rotated = pill.rotate(angle, resample=Image.BICUBIC, center=(span / 2, span / 2))

    shadow = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    shade = Image.new("RGBA", (span, span), (8, 10, 16, 255))
    shade.putalpha(rotated.getchannel("A").filter(ImageFilter.GaussianBlur(3)))
    shadow.paste(shade, (0, 6 * scale // 2), shade)

    canvas = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(rotated)
    return _transparent(canvas.resize((size, size), Image.LANCZOS))


def _capsule(color: tuple[int, int, int], span: int, scale: int) -> Image.Image:
    layer = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
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
    draw.rounded_rectangle(
        (left, top, right, bottom), radius=radius, outline=(16, 20, 30, 110), width=2 * scale
    )
    draw.line((seam, top + 2, seam, bottom - 2), fill=(16, 20, 30, 70), width=scale)
    draw.ellipse(
        (left + radius // 2, top + height // 4, seam - 4 * scale, top + height // 2 + 4),
        fill=(255, 255, 255, 95),
    )
    return layer


def _transparent(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    palette = image.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
    palette.paste(255, mask=alpha.point(lambda value: 255 if value < 140 else 0))
    return palette

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import paths

SIZE = 96
FRAMES = 16
FRAME_MS = 110
ART_VERSION = 4

# One artwork is drawn four times larger than it is shown and resampled once,
# so the outline below really is a single crisp pixel on a 24px row instead of
# a soft cubic smear. Nothing here relies on post-hoc colour chasing.
SUPERSAMPLE = 4
OUTLINE = SUPERSAMPLE  # 1px at the target size, 4px in the supersampled canvas
NEUTRAL_TOLERANCE = 8

# Motion: a slow float plus a small tilt, both driven by the same sine so the
# loop point is seamless, and never enough rotation to tumble the pill.
FLOAT_PX = 6.0
TILT_DEG = 4.0

# One narrow specular band sweeps the silhouette once per loop.
SWEEP_WIDTH = 0.18
SWEEP_PEAK = 108

# The artwork palette. Twelve cool greys and nothing else — the glyph is
# greyscale by construction, never painted in colour and neutralised after.
COLORS = (
    "#f2f4f7",
    "#e6e8ec",
    "#d5d8dd",
    "#c3c8d0",
    "#b0b5bd",
    "#9aa0a8",
    "#8b919b",
    "#767c85",
    "#6a7078",
    "#5a6068",
    "#4d535a",
    "#43484f",
)

# Every medicine gets its own *shape* as well as its own tone, so a row of
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

_STALE_VERSION = re.compile(r"-v(\d+)-")
_prune_done = False


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


# --- cache hygiene -------------------------------------------------------

def _icon_dir(create: bool = True) -> Path:
    directory = paths.icon_dir() / "pills"
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def _purge(directory: Path) -> int:
    """Drop every icon written for an artwork version older than this one."""
    removed = 0
    if not directory.is_dir():
        return 0
    for path in sorted(directory.iterdir()):
        match = _STALE_VERSION.search(path.name)
        if match is None or int(match.group(1)) >= ART_VERSION:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def purge_stale() -> int:
    """Public self-heal: remove every `-v<N>-` icon below `ART_VERSION`.

    Called from `--tick` and `--plugin-panel`, so a running install cleans its
    own icon shelf the next time it is asked anything — no manual `find`.
    """
    return _purge(_icon_dir(create=False))


def _prune_once(directory: Path) -> None:
    global _prune_done
    if _prune_done:
        return
    _prune_done = True
    _purge(directory)


# --- the tonal model -----------------------------------------------------

@lru_cache(maxsize=64)
def _tones(name: str) -> tuple[tuple[int, int, int], ...]:
    """Light body, mid-tone edge, dark outline — all from the twelve greys.

    The hash picks where on the ramp the medicine sits, but the body always
    stays in the bright half so a 24px glyph still separates from the card.
    """
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    base = int(digest[0:2], 16) % 6
    light = rgb(COLORS[max(0, base - 2)])
    body = rgb(COLORS[base])
    edge = rgb(COLORS[min(len(COLORS) - 1, base + 3)])
    deep = rgb(COLORS[min(len(COLORS) - 1, base + 6)])
    glint = rgb(COLORS[0])
    return light, body, edge, deep, glint


@lru_cache(maxsize=512)
def _gradient_strip(
    span: int,
    top: tuple[int, int, int],
    mid: tuple[int, int, int],
    bottom: tuple[int, int, int],
    y0: int,
    y1: int,
) -> Image.Image:
    """A one-pixel-wide vertical three-stop ramp over the shape's own box."""
    rows = []
    height = max(1, y1 - y0)
    for y in range(span):
        t = (y - y0) / float(height)
        if t <= 0.0:
            rows.append(top)
        elif t >= 1.0:
            rows.append(bottom)
        else:
            if t < 0.5:
                u, first, second = t * 2.0, top, mid
            else:
                u, first, second = (t - 0.5) * 2.0, mid, bottom
            rows.append(
                tuple(int(first[i] + (second[i] - first[i]) * u) for i in range(3))
            )
    strip = Image.new("RGB", (1, span))
    strip.putdata(rows)
    return strip


def _fresh(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# --- the eight silhouettes ----------------------------------------------

# Each builder runs twice: once to lay down the silhouette (mask mode, where it
# fills white into an L image) and once to add the interior detail (detail
# mode, painted onto the toned body). Both passes return the shape's box so the
# gradient can be fitted to the artwork rather than to the whole canvas.
def _capsule(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    width = int(span * 0.88)
    height = int(span * 0.44)
    left = (span - width) // 2
    top = (span - height) // 2
    box = (left, top, left + width, top + height)
    if mask_mode:
        d.rounded_rectangle(box, radius=height // 2, fill=255)
        return box
    seam = span // 2
    d.line((seam, top + OUTLINE, seam, top + height - OUTLINE), fill=t[2], width=OUTLINE)
    return box


def _tablet(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    pad = int(span * 0.10)
    box = (pad, pad, span - pad, span - pad)
    if mask_mode:
        d.ellipse(box, fill=255)
        return box
    inset = pad + (span - 2 * pad) // 5
    d.line((span // 2, inset, span // 2, span - inset), fill=t[2], width=OUTLINE)
    return box


def _caplet(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    width = int(span * 0.86)
    height = int(span * 0.50)
    left = (span - width) // 2
    top = (span - height) // 2
    box = (left, top, left + width, top + height)
    if mask_mode:
        d.ellipse(box, fill=255)
    return box


def _softgel(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    width = int(span * 0.84)
    height = int(span * 0.56)
    left = (span - width) // 2
    top = (span - height) // 2
    box = (left, top, left + width, top + height)
    if mask_mode:
        d.ellipse(box, fill=255)
        return box
    gx0 = left + int(width * 0.16)
    gy0 = top + int(height * 0.16)
    d.ellipse((gx0, gy0, gx0 + int(width * 0.36), gy0 + int(height * 0.42)), fill=t[4])
    return box


def _bottle(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    body_w = int(span * 0.52)
    body_h = int(span * 0.54)
    body_left = (span - body_w) // 2
    body_top = int(span * 0.36)
    body = (body_left, body_top, body_left + body_w, body_top + body_h)

    neck_w = int(span * 0.18)
    neck_left = (span - neck_w) // 2
    neck = (neck_left, int(span * 0.20), neck_left + neck_w, body_top + 3 * OUTLINE)

    cap_w = int(span * 0.34)
    cap_h = int(span * 0.13)
    cap_left = (span - cap_w) // 2
    cap = (cap_left, int(span * 0.11), cap_left + cap_w, int(span * 0.11) + cap_h)

    if mask_mode:
        d.rounded_rectangle(body, radius=int(body_w * 0.16), fill=255)
        d.rounded_rectangle(neck, radius=2 * OUTLINE, fill=255)
        d.rounded_rectangle(cap, radius=2 * OUTLINE, fill=255)
        return (cap[0], cap[1], body[2], body[3])

    label_top = body_top + int(body_h * 0.42)
    label = (
        body_left + 3 * OUTLINE,
        label_top,
        body_left + body_w - 3 * OUTLINE,
        label_top + int(body_h * 0.26),
    )
    d.rounded_rectangle(body, radius=int(body_w * 0.16), outline=t[3], width=OUTLINE)
    d.rounded_rectangle(neck, radius=2 * OUTLINE, fill=t[2])
    d.rounded_rectangle(cap, radius=2 * OUTLINE, fill=t[2])
    d.rounded_rectangle(label, radius=2 * OUTLINE, fill=t[0])
    return (cap[0], cap[1], body[2], body[3])


def _inhaler(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    vertical_w = int(span * 0.34)
    vertical_left = int(span * 0.52)
    vertical = (
        vertical_left,
        int(span * 0.10),
        vertical_left + vertical_w,
        int(span * 0.80),
    )
    mouth_left = int(span * 0.14)
    mouth_right = vertical_left + vertical_w - 2 * OUTLINE
    mouth = (mouth_left, int(span * 0.58), mouth_right, int(span * 0.80))

    if mask_mode:
        d.rounded_rectangle(vertical, radius=int(vertical_w * 0.22), fill=255)
        d.rounded_rectangle(mouth, radius=int((mouth[3] - mouth[1]) * 0.34), fill=255)
        return (mouth[0], vertical[1], vertical[2], mouth[3])

    window = (
        vertical_left + 3 * OUTLINE,
        int(span * 0.30),
        vertical_left + vertical_w - 3 * OUTLINE,
        int(span * 0.52),
    )
    d.rounded_rectangle(window, radius=2 * OUTLINE, fill=t[2])
    d.line(
        (vertical_left + 3 * OUTLINE, int(span * 0.66),
         vertical_left + vertical_w - 3 * OUTLINE, int(span * 0.66)),
        fill=t[2],
        width=OUTLINE,
    )
    return (mouth[0], vertical[1], vertical[2], mouth[3])


def _patch(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    side = int(span * 0.72)
    left = (span - side) // 2
    top = (span - side) // 2
    box = (left, top, left + side, top + side)
    radius = int(side * 0.22)
    if mask_mode:
        d.rounded_rectangle(box, radius=radius, fill=255)
        return box

    inset = max(3 * OUTLINE, int(side * 0.16))
    inner = (left + inset, top + inset, left + side - inset, top + side - inset)
    dash = 4 * OUTLINE
    gap = 3 * OUTLINE
    for x in range(inner[0], inner[2], dash + gap):
        stop = min(x + dash, inner[2])
        d.line((x, inner[1], stop, inner[1]), fill=t[2], width=OUTLINE)
        d.line((x, inner[3], stop, inner[3]), fill=t[2], width=OUTLINE)
    for y in range(inner[1], inner[3], dash + gap):
        stop = min(y + dash, inner[3])
        d.line((inner[0], y, inner[0], stop), fill=t[2], width=OUTLINE)
        d.line((inner[2], y, inner[2], stop), fill=t[2], width=OUTLINE)
    return box


def _drops(d: ImageDraw.ImageDraw, span: int, t, mask_mode: bool):
    centre = span // 2
    tip_y = int(span * 0.12)
    bulb_cy = int(span * 0.66)
    radius = int(span * 0.24)
    bulb = (centre - radius, bulb_cy - radius, centre + radius, bulb_cy + radius)
    cone = [(centre, tip_y), (centre - radius, bulb_cy), (centre + radius, bulb_cy)]
    if mask_mode:
        d.polygon(cone, fill=255)
        d.ellipse(bulb, fill=255)
        return (bulb[0], tip_y, bulb[2], bulb[3])

    gx0 = centre - radius // 2 - OUTLINE
    gy0 = bulb_cy - radius // 2 - OUTLINE
    d.ellipse((gx0, gy0, gx0 + radius, gy0 + radius), fill=t[4])
    return (bulb[0], tip_y, bulb[2], bulb[3])


BUILDERS = {
    "capsule": _capsule,
    "tablet": _tablet,
    "caplet": _caplet,
    "softgel": _softgel,
    "bottle": _bottle,
    "inhaler": _inhaler,
    "patch": _patch,
    "drops": _drops,
}


@lru_cache(maxsize=32)
def _geometry(shape: str, span: int) -> tuple[Image.Image, Image.Image, tuple]:
    """The silhouette and its inner outline band, shared by every medicine.

    Deriving the outline from the mask (rather than stroking each path) gives
    one uniform hairline that follows any silhouette — the L of an inhaler and
    the teardrop of a dropper included.
    """
    mask = Image.new("L", (span, span), 0)
    box = BUILDERS.get(shape, _capsule)(ImageDraw.Draw(mask), span, None, True)
    band = ImageChops.subtract(
        mask, mask.filter(ImageFilter.MinFilter(2 * OUTLINE + 1))
    )
    return mask, band, box


def _body(shape: str, span: int, tones) -> Image.Image:
    mask, band, box = _geometry(shape, span)
    light, body, edge, deep, glint = tones
    strip = _gradient_strip(span, light, body, edge, box[1], box[3])
    canvas = Image.new("RGB", (span, span), body)
    canvas.paste(strip.resize((span, span), Image.BILINEAR), (0, 0), mask)
    BUILDERS.get(shape, _capsule)(ImageDraw.Draw(canvas), span, tones, False)
    canvas.paste(Image.new("RGB", (span, span), deep), (0, 0), band)
    out = canvas.convert("RGBA")
    out.putalpha(mask)
    return out


# --- motion --------------------------------------------------------------

def _pose(index: int, span: int, size: int) -> tuple[float, float]:
    """Degrees of tilt and pixels of float for one frame of the loop."""
    phase = 2.0 * math.pi * index / FRAMES
    wave = math.sin(phase)
    amplitude = max(1.0, FLOAT_PX * size / SIZE) * SUPERSAMPLE
    return wave * TILT_DEG, wave * amplitude


@lru_cache(maxsize=64)
def _sweep_strip(band: int, span: int) -> Image.Image:
    row = Image.new("L", (band, 1))
    row.putdata(
        [
            int(SWEEP_PEAK * (1.0 - abs(2.0 * index / max(1, band - 1) - 1.0)) ** 2)
            for index in range(band)
        ]
    )
    return row.resize((band, span), Image.NEAREST)


def _sweep(shape_alpha: Image.Image, index: int, tones) -> Image.Image:
    span = shape_alpha.size[0]
    width = max(2 * OUTLINE, int(span * SWEEP_WIDTH))
    shift = int(round(-width + (index / float(FRAMES)) * (span + width)))
    mask = Image.new("L", (span, span), 0)
    mask.paste(_sweep_strip(width, span), (shift, 0))
    mask = ImageChops.multiply(mask, shape_alpha)
    layer = Image.new("RGBA", (span, span), tones[4] + (255,))
    layer.putalpha(mask)
    return layer


def _frame(artwork: Image.Image, index: int, size: int, tones) -> Image.Image:
    span = artwork.size[0]
    angle, float_px = _pose(index, span, size)
    spun = artwork.rotate(
        angle,
        resample=Image.BICUBIC,
        center=(span / 2, span / 2),
        fillcolor=tones[1] + (0,),
    )
    shifted = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    shifted.paste(spun, (0, int(round(float_px))))
    shifted.alpha_composite(_sweep(shifted.getchannel("A"), index, tones))
    grown = shifted.resize((size, size), Image.LANCZOS)
    return _neutralize(grown)


def _still(shape: str, size: int, tones) -> Image.Image:
    """The quiet pose a notification shows: no float, no sweep, just the glint."""
    span = size * SUPERSAMPLE
    artwork = _body(shape, span, tones)
    return _neutralize(artwork.resize((size, size), Image.LANCZOS))


def _frames(name: str, size: int) -> list[Image.Image]:
    _, shape = style_for(name)
    tones = _tones(name)
    span = size * SUPERSAMPLE
    artwork = _body(shape, span, tones)
    return [_frame(artwork, index, size, tones) for index in range(FRAMES)]


# --- the safety net ------------------------------------------------------

def _neutralize(image: Image.Image) -> Image.Image:
    """Clamp every pixel back onto a neutral ramp.

    The artwork is already drawn from twelve cool greys, so this only has to
    squeeze the ramp's own slight blue cast (and any resampler overshoot on the
    silhouette) down to `NEUTRAL_TOLERANCE` — the guarantee that a decoded
    frame never shows more than eight levels between its channels.
    """
    tolerance = NEUTRAL_TOLERANCE
    pixels = list(image.getdata())
    out = []
    for red, green, blue, alpha in pixels:
        if not alpha:
            out.append((0, 0, 0, 0))
            continue
        spread = max(red, green, blue) - min(red, green, blue)
        if spread <= tolerance:
            out.append((red, green, blue, alpha))
            continue
        mean = (red + green + blue) // 3
        factor = tolerance / float(spread)
        out.append(
            (
                int(mean + (red - mean) * factor),
                int(mean + (green - mean) * factor),
                int(mean + (blue - mean) * factor),
                alpha,
            )
        )
    image.putdata(out)
    return image


# --- writers -------------------------------------------------------------

def _save_gif(frames: list[Image.Image], path: Path) -> None:
    """One shared palette for the whole loop, so the greys never flicker."""
    size = frames[0].size[0]
    montage = Image.new("RGB", (size * len(frames), size))
    for index, frame in enumerate(frames):
        montage.paste(frame.convert("RGB"), (index * size, 0))
    palette = montage.convert("P", palette=Image.ADAPTIVE, colors=255)

    plate: list[Image.Image] = []
    for frame in frames:
        plate_frame = frame.convert("RGB").quantize(
            palette=palette, dither=Image.Dither.NONE
        )
        values = list(plate_frame.getdata())
        alpha = list(frame.getchannel("A").getdata())
        plate_frame.putdata(
            [255 if level < 128 else value for value, level in zip(values, alpha)]
        )
        plate.append(plate_frame)

    plate[0].save(
        path,
        save_all=True,
        append_images=plate[1:],
        duration=FRAME_MS,
        loop=0,
        transparency=255,
        disposal=2,
        optimize=False,
    )


def _save_apng(frames: list[Image.Image], path: Path) -> None:
    """Full alpha, no palette — what GdkPixbuf reads for the dashboard."""
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        disposal=2,
        optimize=False,
    )


def _paths_for(name: str, size: int) -> tuple[Path, Path, Path, Path]:
    directory = _icon_dir()
    _prune_once(directory)
    slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
    stem = f"{slug}-v{ART_VERSION}-{size}"
    return directory, directory / f"{stem}.gif", directory / f"{stem}.anim.png", directory / f"{stem}.png"


def pill_gif(name: str, size: int = SIZE) -> Path:
    """The animation QML reads from a file, with its APNG sibling written too."""
    directory, gif, apng, _ = _paths_for(name, size)
    if _fresh(gif) and _fresh(apng):
        return gif
    frames = _frames(name, size)
    _save_gif(frames, gif)
    _save_apng(frames, apng)
    return gif


def pill_apng(name: str, size: int = SIZE) -> Path:
    """The same loop with real alpha, for the GTK side."""
    _, gif, apng, _ = _paths_for(name, size)
    if _fresh(apng) and _fresh(gif):
        return apng
    frames = _frames(name, size)
    _save_gif(frames, gif)
    _save_apng(frames, apng)
    return apng


def pill_png(name: str, size: int = SIZE) -> Path:
    """A still of the same medicine's pill — what a notification shows."""
    _, _, _, png = _paths_for(name, size)
    if _fresh(png):
        return png
    _, shape = style_for(name)
    _still(shape, size, _tones(name)).save(png, optimize=True)
    return png

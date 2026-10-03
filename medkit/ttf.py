from __future__ import annotations

"""Just enough TrueType to embed a font in a PDF, in the standard library.

MedKit's PDF writer builds its files by hand so the app keeps shipping zero
third-party libraries. Arabic medicine names broke that promise: the built-in
Helvetica has no Arabic glyphs, so every name printed as "?". The fix is to
embed a real TrueType font, which means reading four tables out of the .ttf:

* ``head``  — unitsPerEm, needed to scale advance widths
* ``hhea``/``hmtx`` — per-glyph advance widths
* ``cmap``  — character code to glyph id (formats 4 and 12)

Only the two cmap formats a modern system font actually uses are implemented,
and only the BMP subset of format 12. That is everything DejaVu Sans and Noto
need for Arabic plus Latin.
"""

import struct
from pathlib import Path

# Candidate system fonts, best first. DejaVu covers Latin and the Arabic
# presentation forms in one file, so a single face serves the whole card.
_REGULAR_CANDIDATES = (
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_BOLD_CANDIDATES = (
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


class FontError(RuntimeError):
    """Raised when no usable TrueType font can be found."""


class TrueTypeFont:
    """A parsed .ttf: glyph ids, advance widths and the raw bytes to embed."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self.tables = self._read_table_directory()
        self.units_per_em = self._read_units_per_em()
        self._cmap = self._read_cmap()
        self._widths = self._read_widths()

    # ---- parsing ------------------------------------------------------
    def _read_table_directory(self) -> dict[str, tuple[int, int]]:
        if len(self.data) < 12:
            raise FontError(f"{self.path} is too short to be a font")
        tag = self.data[:4]
        if tag == b"ttcf":
            raise FontError(f"{self.path} is a font collection, not a single face")
        if tag not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
            raise FontError(f"{self.path} is not a recognised sfnt font")
        count = struct.unpack(">H", self.data[4:6])[0]
        tables: dict[str, tuple[int, int]] = {}
        for index in range(count):
            base = 12 + index * 16
            name = self.data[base:base + 4].decode("latin-1")
            offset, length = struct.unpack(">II", self.data[base + 8:base + 16])
            tables[name] = (offset, length)
        return tables

    def _table(self, name: str) -> tuple[int, int]:
        try:
            return self.tables[name]
        except KeyError as error:
            raise FontError(f"{self.path} has no {name!r} table") from error

    def _read_units_per_em(self) -> int:
        offset, _ = self._table("head")
        return struct.unpack(">H", self.data[offset + 18:offset + 20])[0] or 1000

    def _read_cmap(self) -> dict[int, int]:
        offset, _ = self._table("cmap")
        count = struct.unpack(">H", self.data[offset + 2:offset + 4])[0]
        best: dict[int, int] | None = None
        best_score = -1
        for index in range(count):
            record = offset + 4 + index * 8
            platform, encoding, sub = struct.unpack(">HHI", self.data[record:record + 8])
            base = offset + sub
            fmt = struct.unpack(">H", self.data[base:base + 2])[0]
            # Prefer a full Unicode subtable: (3,10) or (0,4) are format 12.
            score = {(3, 10): 4, (0, 4): 3, (3, 1): 2, (0, 3): 1}.get((platform, encoding), 0)
            if fmt == 12 and score >= 0:
                table = self._parse_cmap12(base)
            elif fmt == 4 and score >= 0:
                table = self._parse_cmap4(base)
            else:
                continue
            if score > best_score:
                best, best_score = table, score
        if best is None:
            raise FontError(f"{self.path} has no usable cmap subtable")
        return best

    def _parse_cmap4(self, base: int) -> dict[int, int]:
        seg_x2 = struct.unpack(">H", self.data[base + 6:base + 8])[0]
        segments = seg_x2 // 2
        ends_at = base + 14
        starts_at = ends_at + seg_x2 + 2
        deltas_at = starts_at + seg_x2
        ranges_at = deltas_at + seg_x2
        glyphs_at = ranges_at + seg_x2

        ends = [struct.unpack(">H", self.data[ends_at + i * 2:ends_at + i * 2 + 2])[0]
                for i in range(segments)]
        starts = [struct.unpack(">H", self.data[starts_at + i * 2:starts_at + i * 2 + 2])[0]
                  for i in range(segments)]
        deltas = [struct.unpack(">h", self.data[deltas_at + i * 2:deltas_at + i * 2 + 2])[0]
                  for i in range(segments)]
        ranges = [struct.unpack(">H", self.data[ranges_at + i * 2:ranges_at + i * 2 + 2])[0]
                  for i in range(segments)]

        table: dict[int, int] = {}
        for i in range(segments):
            for code in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if ranges[i] == 0:
                    glyph = (code + deltas[i]) & 0xFFFF
                else:
                    index = glyphs_at + i * 2 + ranges[i] + (code - starts[i]) * 2
                    if index + 2 > len(self.data):
                        continue
                    glyph = struct.unpack(">H", self.data[index:index + 2])[0]
                    if glyph:
                        glyph = (glyph + deltas[i]) & 0xFFFF
                if glyph:
                    table[code] = glyph
        return table

    def _parse_cmap12(self, base: int) -> dict[int, int]:
        groups = struct.unpack(">I", self.data[base + 12:base + 16])[0]
        table: dict[int, int] = {}
        for index in range(groups):
            record = base + 16 + index * 12
            start, end, start_glyph = struct.unpack(">III", self.data[record:record + 12])
            # Only the BMP matters for a medicine card.
            for code in range(start, min(end, 0xFFFF) + 1):
                table[code] = start_glyph + (code - start)
        return table

    def _read_widths(self) -> dict[int, int]:
        head, _ = self._table("head")
        index_to_loc = struct.unpack(">h", self.data[head + 50:head + 52])[0]
        hhea, _ = self._table("hhea")
        num_h_metrics = struct.unpack(">H", self.data[hhea + 34:hhea + 36])[0]
        hmtx, _ = self._table("hmtx")
        maxp, _ = self._table("maxp")
        num_glyphs = struct.unpack(">H", self.data[maxp + 4:maxp + 6])[0]
        del index_to_loc  # only needed by a real subsetter

        widths: dict[int, int] = {}
        last = 0
        for glyph in range(num_glyphs):
            if glyph < num_h_metrics:
                at = hmtx + glyph * 4
                last = struct.unpack(">H", self.data[at:at + 2])[0]
            widths[glyph] = last
        return widths

    # ---- lookups ------------------------------------------------------
    def glyph(self, char: str) -> int:
        """Glyph id for one character, 0 (.notdef) when the font lacks it."""
        return self._cmap.get(ord(char), 0)

    def advance(self, glyph: int, size: float) -> float:
        """Advance width in points at the given font size."""
        return self._widths.get(glyph, 0) * size / self.units_per_em

    def text_width(self, text: str, size: float) -> float:
        return sum(self.advance(self.glyph(char), size) for char in text)

    def covers(self, text: str) -> bool:
        return all(not char.strip() or self.glyph(char) for char in text)

    # ---- PDF metrics --------------------------------------------------
    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """head.xMin/yMin/xMax/yMax, in font units."""
        offset, _ = self._table("head")
        return struct.unpack(">hhhh", self.data[offset + 36:offset + 44])

    @property
    def ascent(self) -> int:
        offset, _ = self._table("hhea")
        return struct.unpack(">h", self.data[offset + 4:offset + 6])[0]

    @property
    def descent(self) -> int:
        offset, _ = self._table("hhea")
        return struct.unpack(">h", self.data[offset + 6:offset + 8])[0]

    @property
    def cap_height(self) -> int:
        """OS/2.sCapHeight when the table is new enough, else the ascender."""
        if "OS/2" not in self.tables:
            return self.ascent
        offset, length = self._table("OS/2")
        if length >= 90 and struct.unpack(">H", self.data[offset:offset + 2])[0] >= 2:
            return struct.unpack(">h", self.data[offset + 88:offset + 90])[0]
        return self.ascent

    def glyph_width(self, glyph: int) -> int:
        """Advance width in 1000ths of a text space — PDF ``/W`` units."""
        return round(self._widths.get(glyph, 0) * 1000 / self.units_per_em)


def _first_existing(paths: tuple[str, ...]) -> str:
    for path in paths:
        if Path(path).exists():
            return path
    raise FontError("no TrueType font found in: " + ", ".join(paths))


_CACHE: dict[str, TrueTypeFont] = {}


def regular_font() -> TrueTypeFont:
    return _load("regular", _REGULAR_CANDIDATES)


def bold_font() -> TrueTypeFont:
    return _load("bold", _BOLD_CANDIDATES)


def _load(kind: str, candidates: tuple[str, ...]) -> TrueTypeFont:
    if kind not in _CACHE:
        _CACHE[kind] = TrueTypeFont(_first_existing(candidates))
    return _CACHE[kind]

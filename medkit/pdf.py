from __future__ import annotations

"""A very small PDF writer.

Reports have to leave this machine (a doctor's appointment does not care
about your bar), and MedKit ships no third-party libraries — so this builds
the handful of PDF objects a text report needs by hand: pages, two standard
fonts, and text/line/rectangle operators. Ghostscript and reportlab are not
required, and neither is a network connection.
"""

from pathlib import Path

from . import arabic, ttf

# A4 in PostScript points.
PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 54

FONT_REGULAR = "F1"
FONT_BOLD = "F2"
# Embedded faces, used for any string Arabic shaping turns into presentation
# forms. Helvetica is still the base-14 font for everything else, so a Latin
# report stays a two-kilobyte file.
EMBED_REGULAR = "F3"
EMBED_BOLD = "F4"

_COLORS = {
    "black": (0, 0, 0),
    "grey": (0.4, 0.4, 0.4),
    "light": (0.85, 0.85, 0.85),
    "red": (0.86, 0.17, 0.17),
    "amber": (0.96, 0.62, 0.04),
    "green": (0.13, 0.77, 0.37),
    "blue": (0.22, 0.74, 0.97),
}


def _escape(text: str) -> str:
    out = []
    for char in str(text):
        if char in ("\\", "(", ")"):
            out.append("\\" + char)
            continue
        try:
            # Text is drawn in WinAnsi (cp1252) but the stream is written as
            # latin-1, so hand back the byte as a latin-1 character: "•"
            # becomes chr(0x95) instead of surviving as U+2022 and turning
            # into a "?" on the way out of save().
            out.append(char.encode("cp1252").decode("latin-1"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            out.append("?")
    return "".join(out)


class PDF:
    """Accumulates pages, then serialises them with a correct xref table."""

    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self._ops: list[str] = []
        self._y = PAGE_HEIGHT - MARGIN
        self._used_faces: set[str] = set()
        self._used_glyphs: dict[str, set[int]] = {}
        self.new_page()

    # ---- drawing ------------------------------------------------------
    def new_page(self) -> None:
        self._ops = []
        self.pages.append(self._ops)
        self._y = PAGE_HEIGHT - MARGIN

    @property
    def y(self) -> float:
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        self._y = value

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 10,
        bold: bool = False,
        color: str = "black",
    ) -> None:
        r, g, b = _COLORS.get(color, _COLORS["black"])
        value = str(value)
        if arabic.has_arabic(value) and self._draw_embedded(
            x, y, value, size, bold, (r, g, b)
        ):
            return
        font = FONT_BOLD if bold else FONT_REGULAR
        self._ops.append(
            f"BT /{font} {size:g} Tf {r:g} {g:g} {b:g} rg "
            f"{x:g} {y:g} Td ({_escape(value)}) Tj ET"
        )

    def _draw_embedded(
        self,
        x: float,
        y: float,
        value: str,
        size: float,
        bold: bool,
        rgb: tuple[float, float, float],
    ) -> bool:
        """Lay Arabic out for an embedded face; False keeps the base-14 path."""
        face = "bold" if bold else "regular"
        try:
            font = ttf.bold_font() if bold else ttf.regular_font()
        except ttf.FontError:
            return False
        visual = arabic.visual(value)
        glyphs = [font.glyph(char) for char in visual]
        if not glyphs or not all(glyphs):
            return False
        self._used_faces.add(face)
        self._used_glyphs.setdefault(face, set()).update(glyphs)
        r, g, b = rgb
        code = EMBED_BOLD if bold else EMBED_REGULAR
        payload = "".join(f"{glyph:04X}" for glyph in glyphs)
        self._ops.append(
            f"BT /{code} {size:g} Tf {r:g} {g:g} {b:g} rg "
            f"{x:g} {y:g} Td <{payload}> Tj ET"
        )
        return True

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "light", width: float = 0.8) -> None:
        r, g, b = _COLORS.get(color, _COLORS["light"])
        self._ops.append(
            f"{r:g} {g:g} {b:g} RG {width:g} w {x1:g} {y1:g} m {x2:g} {y2:g} l S"
        )

    def rect(self, x: float, y: float, width: float, height: float, color: str = "light") -> None:
        r, g, b = _COLORS.get(color, _COLORS["light"])
        self._ops.append(f"{r:g} {g:g} {b:g} rg {x:g} {y:g} {width:g} {height:g} re f")

    # ---- flow helpers -------------------------------------------------
    def ensure(self, height: float) -> float:
        """Page-break when the cursor would run off the sheet."""
        if self.y - height < MARGIN:
            self.new_page()
            self.y = PAGE_HEIGHT - MARGIN
        return self.y

    def heading(self, value: str, size: float = 16) -> None:
        self.ensure(size + 14)
        self.y -= size + 8
        self.text(MARGIN, self.y, value, size=size, bold=True)
        self.y -= 6
        self.line(MARGIN, self.y, PAGE_WIDTH - MARGIN, self.y, color="light")

    def subheading(self, value: str) -> None:
        self.ensure(24)
        self.y -= 18
        self.text(MARGIN, self.y, value, size=12, bold=True)
        self.y -= 4

    def para(self, value: str, size: float = 10, color: str = "black", indent: float = 0) -> None:
        max_chars = int((PAGE_WIDTH - 2 * MARGIN - indent) / (size * 0.5))
        words = str(value).split()
        line = ""
        lines: list[str] = []
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > max_chars and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        for entry in lines or [""]:
            self.ensure(size + 4)
            self.y -= size + 3
            self.text(MARGIN + indent, self.y, entry, size=size, color=color)

    def bullet(self, value: str, size: float = 10, color: str = "black") -> None:
        self.para(f"•  {value}", size=size, color=color, indent=6)

    def gap(self, height: float = 8) -> None:
        self.y -= height

    # ---- serialisation ------------------------------------------------
    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        objects: list[bytes] = []

        def add(body: str) -> int:
            objects.append(body.encode("latin-1", "replace"))
            return len(objects)

        def add_raw(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        font_regular = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            "/Encoding /WinAnsiEncoding >>"
        )
        font_bold = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            "/Encoding /WinAnsiEncoding >>"
        )

        embedded: dict[str, int] = {}
        for face in sorted(self._used_faces):
            font = ttf.bold_font() if face == "bold" else ttf.regular_font()
            embedded[face] = self._embed_font(objects, add_raw, face, font)
        face_resources = "".join(
            f"/{EMBED_BOLD if face == 'bold' else EMBED_REGULAR} {reference} 0 R "
            for face, reference in embedded.items()
        )

        page_ids: list[int] = []
        content_ids: list[int] = []
        for ops in self.pages:
            stream = "\n".join(ops).encode("latin-1", "replace")
            body = (
                f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                + stream
                + b"\nendstream"
            )
            objects.append(body)
            content_ids.append(len(objects))

        for content_id in content_ids:
            body = (
                "<< /Type /Page /Parent 0 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /{FONT_REGULAR} {font_regular} 0 R "
                f"/{FONT_BOLD} {font_bold} 0 R {face_resources}>> >> "
                f"/Contents {content_id} 0 R >>"
            )
            objects.append(body.encode("latin-1"))
            page_ids.append(len(objects))

        pages_object_id = add(
            "<< /Type /Pages /Kids ["
            + " ".join(f"{pid} 0 R" for pid in page_ids)
            + f"] /Count {len(page_ids)} >>"
        )
        # Point the parents at the real Pages object now that it exists.
        for pid in page_ids:
            index = pid - 1
            objects[index] = objects[index].replace(b"/Parent 0 0 R", f"/Parent {pages_object_id} 0 R".encode("latin-1"))

        catalog_id = add(f"<< /Type /Catalog /Pages {pages_object_id} 0 R >>")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode("latin-1")
            out += body
            out += b"\nendobj\n"

        xref_at = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
        out += b"0000000000 65535 f \n"
        for offset in offsets[1:]:
            out += f"{offset:010d} 00000 n \n".encode("latin-1")
        out += (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("latin-1")

        target.write_bytes(bytes(out))
        return target

    def _embed_font(self, objects: list[bytes], add_raw, face: str, font: ttf.TrueTypeFont) -> int:
        """FontFile2 + descriptor + CIDFont + Type0, returning the Type0 id."""
        name = "DejaVuSans-Bold" if face == "bold" else "DejaVuSans"
        data = font.data
        file_id = add_raw(
            f"<< /Length {len(data)} /Length1 {len(data)} >>\nstream\n".encode("latin-1")
            + data
            + b"\nendstream"
        )

        upem = font.units_per_em

        def to_text_space(units: int) -> int:
            return round(units * 1000 / upem)

        x_min, y_min, x_max, y_max = font.bbox
        descriptor_id = add_raw(
            (
                f"<< /Type /FontDescriptor /FontName /{name} /Flags 32 "
                f"/FontBBox [{to_text_space(x_min)} {to_text_space(y_min)} "
                f"{to_text_space(x_max)} {to_text_space(y_max)}] "
                f"/ItalicAngle 0 /Ascent {to_text_space(font.ascent)} "
                f"/Descent {to_text_space(font.descent)} "
                f"/CapHeight {to_text_space(font.cap_height)} /StemV 80 "
                f"/FontFile2 {file_id} 0 R >>"
            ).encode("latin-1")
        )

        used = sorted(self._used_glyphs.get(face, set()) | {0})
        widths = " ".join(
            f"{glyph} [{font.glyph_width(glyph)}]" for glyph in used
        )
        descendant_id = add_raw(
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{name} "
                f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                f"/Supplement 0 >> /FontDescriptor {descriptor_id} 0 R "
                f"/DW 600 /W [{widths}] /CIDToGIDMap /Identity >>"
            ).encode("latin-1")
        )
        return add_raw(
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /{name} "
                f"/Encoding /Identity-H /DescendantFonts [{descendant_id} 0 R] >>"
            ).encode("latin-1")
        )


def write_text_pdf(path: str | Path, title: str, lines: list[str]) -> Path:
    """Turn plain report lines into a paginated PDF."""
    doc = PDF()
    doc.heading(title, size=17)
    for raw in lines:
        line = str(raw)
        if not line.strip():
            doc.gap(6)
            continue
        if line.startswith("=="):
            continue
        if line.startswith("##"):
            doc.subheading(line.lstrip("# ").strip())
        elif line.startswith("- ") or line.startswith("  - "):
            doc.bullet(line.lstrip(" -"))
        else:
            doc.para(line)
    doc.gap(14)
    doc.para("This is not medical advice.", size=8, color="grey")
    return doc.save(path)

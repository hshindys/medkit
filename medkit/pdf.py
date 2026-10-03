from __future__ import annotations

"""A very small PDF writer.

Reports have to leave this machine (a doctor's appointment does not care
about your bar), and MedKit ships no third-party libraries — so this builds
the handful of PDF objects a text report needs by hand: pages, two standard
fonts, and text/line/rectangle operators. Ghostscript and reportlab are not
required, and neither is a network connection.
"""

from pathlib import Path

# A4 in PostScript points.
PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 54

FONT_REGULAR = "F1"
FONT_BOLD = "F2"

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
            char.encode("cp1252")
            out.append(char)
        except UnicodeEncodeError:
            out.append("?")
    return "".join(out)


class PDF:
    """Accumulates pages, then serialises them with a correct xref table."""

    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self._ops: list[str] = []
        self._y = PAGE_HEIGHT - MARGIN
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
        font = FONT_BOLD if bold else FONT_REGULAR
        self._ops.append(
            f"BT /{font} {size:g} Tf {r:g} {g:g} {b:g} rg "
            f"{x:g} {y:g} Td ({_escape(value)}) Tj ET"
        )

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

        font_regular = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            "/Encoding /WinAnsiEncoding >>"
        )
        font_bold = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            "/Encoding /WinAnsiEncoding >>"
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
                f"/{FONT_BOLD} {font_bold} 0 R >> >> "
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

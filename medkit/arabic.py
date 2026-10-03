from __future__ import annotations

"""Arabic shaping and bidi, in the standard library only.

The emergency card and the therapy review carry Arabic medicine names, and a
PDF that prints them as "?" is worse than useless at a hospital desk. The
report writer embeds a font (see pdf.py); this module turns logical Arabic
text into the visual, contextually-shaped form that font expects.

Two jobs, both done by hand so MedKit keeps shipping zero third-party
libraries:

1. **Shaping** — pick the isolated / final / initial / medial presentation
   form (Arabic Presentation Forms-B, U+FE70..U+FEFF) for each letter
   according to its neighbours, and collapse lam-alef into its ligature.
2. **Bidi** — a right-to-left base paragraph with left-to-right runs (doses,
   clock times, numbers) laid back out in visual order. Full UAX#9 is far
   more than a medicine card needs; the run-reversal below is exact for
   Arabic with embedded Latin/digit runs, which is the whole of this text.
"""

# base letter -> (isolated, final, initial, medial); None = the form does not
# exist for that letter (right-joining and non-joining letters have no
# initial/medial form).
_FORMS: dict[int, tuple[int | None, int | None, int | None, int | None]] = {
    0x0621: (0xFE80, 0xFE80, None, None),      # hamza
    0x0622: (0xFE81, 0xFE82, None, None),      # alef madda
    0x0623: (0xFE83, 0xFE84, None, None),      # alef hamza above
    0x0624: (0xFE85, 0xFE86, None, None),      # waw hamza
    0x0625: (0xFE87, 0xFE88, None, None),      # alef hamza below
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C),  # yeh hamza
    0x0627: (0xFE8D, 0xFE8E, None, None),      # alef
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92),  # beh
    0x0629: (0xFE93, 0xFE94, None, None),      # teh marbuta
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98),  # teh
    0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C),  # theh
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0),  # jeem
    0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4),  # hah
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8),  # khah
    0x062F: (0xFEA9, 0xFEAA, None, None),      # dal
    0x0630: (0xFEAB, 0xFEAC, None, None),      # thal
    0x0631: (0xFEAD, 0xFEAE, None, None),      # reh
    0x0632: (0xFEAF, 0xFEB0, None, None),      # zain
    0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4),  # seen
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8),  # sheen
    0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC),  # sad
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0),  # dad
    0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4),  # tah
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8),  # zah
    0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC),  # ain
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0),  # ghain
    0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4),  # feh
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8),  # qaf
    0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC),  # kaf
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0),  # lam
    0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4),  # meem
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8),  # noon
    0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC),  # heh
    0x0648: (0xFEED, 0xFEEE, None, None),      # waw
    0x0649: (0xFEEF, 0xFEF0, None, None),      # alef maksura
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),  # yeh
    0x0671: (0xFB50, 0xFB51, None, None),      # alef wasla
    0x0679: (0xFB66, 0xFB67, 0xFB68, 0xFB69),
    0x067A: (0xFB5E, 0xFB5F, 0xFB60, 0xFB61),
    0x067B: (0xFB52, 0xFB53, 0xFB54, 0xFB55),
    0x067E: (0xFB56, 0xFB57, 0xFB58, 0xFB59),
    0x0680: (0xFB5A, 0xFB5B, 0xFB5C, 0xFB5D),
    0x0683: (0xFB76, 0xFB77, 0xFB78, 0xFB79),
    0x0684: (0xFB72, 0xFB73, 0xFB74, 0xFB75),
    0x0686: (0xFB7A, 0xFB7B, 0xFB7C, 0xFB7D),
    0x0687: (0xFB7E, 0xFB7F, 0xFB80, 0xFB81),
    0x0688: (0xFB88, 0xFB89, None, None),
    0x068C: (0xFB84, 0xFB85, None, None),
    0x068D: (0xFB82, 0xFB83, None, None),
    0x068E: (0xFB86, 0xFB87, None, None),
    0x0691: (0xFB8C, 0xFB8D, None, None),
    0x0698: (0xFB8A, 0xFB8B, None, None),
    0x06A4: (0xFB6A, 0xFB6B, 0xFB6C, 0xFB6D),
    0x06A6: (0xFB6E, 0xFB6F, 0xFB70, 0xFB71),
    0x06A9: (0xFB8E, 0xFB8F, 0xFB90, 0xFB91),
    0x06AD: (0xFBD3, 0xFBD4, 0xFBD5, 0xFBD6),
    0x06AF: (0xFB92, 0xFB93, 0xFB94, 0xFB95),
    0x06BA: (0xFB9E, 0xFB9F, None, None),
    0x06BB: (0xFBA0, 0xFBA1, 0xFBA2, 0xFBA3),
    0x06BE: (0xFBAA, 0xFBAB, 0xFBAC, 0xFBAD),
    0x06C0: (0xFBA4, 0xFBA5, None, None),
    0x06C1: (0xFBA6, 0xFBA7, 0xFBA8, 0xFBA9),
    0x06C5: (0xFBE0, 0xFBE1, None, None),
    0x06C6: (0xFBD9, 0xFBDA, None, None),
    0x06C7: (0xFBD7, 0xFBD8, None, None),
    0x06C8: (0xFBDB, 0xFBDC, None, None),
    0x06C9: (0xFBE2, 0xFBE3, None, None),
    0x06CB: (0xFBDE, 0xFBDF, None, None),
    0x06CC: (0xFBFC, 0xFBFD, 0xFBFE, 0xFBFF),
    0x06D0: (0xFBE4, 0xFBE5, 0xFBE6, 0xFBE7),
    0x06D2: (0xFBAE, 0xFBAF, None, None),
    0x06D3: (0xFBB0, 0xFBB1, None, None),
}

# lam + alef -> the two ligature forms (isolated, final)
_LAM_ALEF: dict[int, tuple[int, int]] = {
    0x0622: (0xFEF5, 0xFEF6),
    0x0623: (0xFEF7, 0xFEF8),
    0x0625: (0xFEF9, 0xFEFA),
    0x0627: (0xFEFB, 0xFEFC),
}

# Letters that never join to the following letter, so they can never take an
# initial or medial form even where one is listed above.
_RIGHT_JOINING = {
    0x0622, 0x0623, 0x0624, 0x0625, 0x0627, 0x0629, 0x062F, 0x0630, 0x0631,
    0x0632, 0x0648, 0x0649, 0x0671, 0x0688, 0x068C, 0x068D, 0x068E, 0x0691,
    0x0698, 0x06BA, 0x06C0, 0x06C5, 0x06C6, 0x06C7, 0x06C8, 0x06C9, 0x06CB,
    0x06D2, 0x06D3,
}

# Combining marks (harakat, shadda, sukun, tatweel): transparent for joining —
# they sit between two letters without breaking the join.
_TRANSPARENT = set(range(0x064B, 0x0660)) | {0x0640, 0x0670, 0x06D6, 0x06D7, 0x06D8,
                                             0x06D9, 0x06DA, 0x06DB, 0x06DC, 0x06DF,
                                             0x06E0, 0x06E1, 0x06E2, 0x06E3, 0x06E4,
                                             0x06E7, 0x06E8, 0x06EA, 0x06EB, 0x06EC,
                                             0x06ED}

_RTL_RANGES = (
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB50, 0xFDFF),   # Presentation Forms-A
    (0xFE70, 0xFEFF),   # Presentation Forms-B
)


def is_arabic(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _RTL_RANGES)


def _joining_type(char: str) -> str:
    """'D' dual-joining, 'R' right-joining, 'T' transparent, '' otherwise."""
    code = ord(char)
    if code in _TRANSPARENT:
        return "T"
    if code not in _FORMS:
        return ""
    if code in _RIGHT_JOINING:
        return "R"
    isolated, final, initial, medial = _FORMS[code]
    return "D" if initial is not None else "R"


def shape(text: str) -> str:
    """Replace each Arabic letter with its contextually correct form."""
    chars = list(text)
    out: list[str] = []
    index = 0
    total = len(chars)
    while index < total:
        char = chars[index]
        code = ord(char)

        # lam + alef collapses into one ligature glyph
        if code == 0x0644 and index + 1 < total and ord(chars[index + 1]) in _LAM_ALEF:
            ligatures = _LAM_ALEF[ord(chars[index + 1])]
            previous = _previous_joining(chars, index - 1)
            # "final" when the lam itself joins to the letter before it
            out.append(chr(ligatures[1] if previous == "D" else ligatures[0]))
            index += 2
            continue

        if code not in _FORMS:
            out.append(char)
            index += 1
            continue

        previous = _previous_joining(chars, index - 1)
        following = _next_joining(chars, index + 1)
        isolated, final, initial, medial = _FORMS[code]

        # A letter joins the one before it when that letter is dual-joining,
        # and joins the one after it when the next letter accepts a connection
        # from the right (dual- or right-joining).
        joins_previous = previous == "D"
        joins_next = following in ("D", "R")

        if joins_previous and joins_next and medial is not None:
            out.append(chr(medial))
        elif joins_previous and final is not None:
            out.append(chr(final))
        elif joins_next and initial is not None:
            out.append(chr(initial))
        elif isolated is not None:
            out.append(chr(isolated))
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _previous_joining(chars: list[str], index: int) -> str:
    """The joining type of the nearest non-transparent char to the left."""
    while index >= 0:
        kind = _joining_type(chars[index])
        if kind == "T":
            index -= 1
            continue
        return kind
    return ""


def _next_joining(chars: list[str], index: int) -> str:
    while index < len(chars):
        kind = _joining_type(chars[index])
        if kind == "T":
            index += 1
            continue
        return kind
    return ""


_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")


def _is_neutral(char: str) -> bool:
    """Whitespace and punctuation that carries no direction of its own."""
    return char.isspace() or char in "،؛؟٪.,:;!?()[]{}<>/\\|-–—_\"'`+*=%#@&"


# Separators a dose line leans on: 09:00, 12-03, 5.5 mg.
_NUMBER_PUNCT = set(".,:/-+")


def _directions(text: str) -> list[bool | None]:
    """Per character: RTL, LTR, or neutral — with numbers kept whole."""
    directions: list[bool | None] = [
        None if _is_neutral(char) else is_arabic(char) for char in text
    ]
    # UAX#9 W4: a common separator between two European digits is part of the
    # number, so "09:00" reverses as one run instead of printing "00:09".
    for index, char in enumerate(text):
        if directions[index] is not None or char not in _NUMBER_PUNCT:
            continue
        before = text[index - 1] if index else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if before.isdigit() and after.isdigit():
            directions[index] = False
    return directions


def bidi(text: str) -> str:
    """Lay a mixed paragraph out in visual order.

    The base direction comes from the first strong character, exactly as
    UAX#9's P2/P3 do: a medicine line opens with its Arabic name and so reads
    right-to-left, while a field label like "Name : حاتم" opens in Latin and
    stays left-to-right. Arabic runs are reversed in place either way; only an
    RTL base reverses the run order itself. So "كونكور 5 ملغ" comes back as the
    visual "ملغ 5 كونكور".

    A neutral (space or punctuation) is its own run: it belongs to neither
    neighbour, so reversing the run order lands it back between the two runs it
    separated and the words never collide.
    """
    if not any(is_arabic(char) for char in text):
        return text

    directions = _directions(text)
    # P2/P3: the base comes from the first strong *letter* — a bullet or a
    # bracket at the head of the line must not pick the direction for it.
    base_rtl = next(
        (
            is_arabic(char)
            for char, direction in zip(text, directions)
            if direction is not None and char.isalpha()
        ),
        False,
    )
    runs: list[tuple[bool | None, str]] = []  # (is_rtl, text); None = neutral
    for char, direction in zip(text, directions):
        if runs and runs[-1][0] == direction:
            runs[-1] = (direction, runs[-1][1] + char)
        else:
            runs.append((direction, char))

    laid: list[str] = [chunk[::-1] if rtl else chunk for rtl, chunk in runs]
    if base_rtl:
        laid.reverse()
    # A bracket that lands on the other side of its pair reads mirrored in RTL
    # (UAX#9 rule L4).
    return "".join(laid).translate(_MIRROR)


def visual(text: str) -> str:
    """Shape then lay out: what the PDF writer draws for an Arabic string."""
    return bidi(shape(text))


def has_arabic(text: str) -> bool:
    return any(is_arabic(char) for char in text)

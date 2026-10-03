from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from functools import lru_cache

from . import paths

# Severity is ordered so a caller can sort or threshold findings without
# re-deciding what "worse" means in every module.
SEVERITIES = ("mild", "moderate", "severe")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}

SEVERITY_COLORS = {
    "mild": "#8b919b",
    "moderate": "#9aa0a8",
    "severe": "#f2f4f7",
}

# Dose and form words that carry no identity: "Concor 5 mg" and "Concor" are
# the same medicine, and "Metformin XR tablets" is still metformin. Standalone
# numbers go too ("Brufen 400" -> "brufen"); digits glued to letters survive,
# so "vitamin b12" is not cut down to "vitamin b".
_NOISE = re.compile(
    r"\b(\d+(\.\d+)?\s*(mg|mcg|µg|ug|g|ml|iu|units?|mmol|%)?"
    r"|xr|sr|mr|cr|er|od|bd|tds|stat|prn|no\.?"
    r"|tabs?|tablets?|capsules?|caps|pill|pills|solution|suspension|syrup"
    r"|inhaler|spray|drops|gel|cream|ointment|patch|for|the|and|of)\b",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Fold a medicine name down to the words that identify the molecule."""
    cleaned = _NOISE.sub(" ", str(text or ""))
    cleaned = _NON_WORD.sub(" ", cleaned.lower())
    return _SPACES.sub(" ", cleaned).strip()


@dataclass(frozen=True)
class Resolved:
    """One medicine as the knowledge base understands it."""

    name: str
    generic: str
    classes: tuple[str, ...] = ()
    matched: bool = False

    @property
    def concepts(self) -> frozenset[str]:
        return frozenset((self.generic,) if self.generic else ()) | frozenset(self.classes)

    def has(self, concept: str) -> bool:
        return concept in self.concepts


@dataclass
class Knowledge:
    raw: dict
    members_to_class: dict[str, str] = field(default_factory=dict)
    synonyms: dict[str, str] = field(default_factory=dict)
    generics: set[str] = field(default_factory=set)

    # ---- lookup -------------------------------------------------------
    def class_label(self, class_id: str) -> str:
        entry = self.raw.get("classes", {}).get(class_id) or {}
        return str(entry.get("label", class_id))

    def resolve(self, name: str, generic_hint: str = "") -> Resolved:
        hint = normalize(generic_hint)
        base = normalize(name)

        generic = ""
        if hint and (hint in self.synonyms or hint in self.generics or hint in self.members_to_class):
            generic = self.synonyms.get(hint, hint)

        if not generic and base in self.synonyms:
            generic = self.synonyms[base]
        elif not generic and base in self.members_to_class:
            generic = base

        # Whole-word scan: "Concor 5 mg" -> "concor" -> bisoprolol, and a
        # name that already carries the molecule ("Bisoprolol fumarate")
        # matches without needing a brand entry.
        if not generic:
            for member in sorted(self.members_to_class, key=len, reverse=True):
                if re.search(rf"\b{re.escape(member)}\b", base):
                    generic = self.synonyms.get(member, member)
                    break

        if not generic and hint:
            for member in sorted(self.members_to_class, key=len, reverse=True):
                if re.search(rf"\b{re.escape(member)}\b", hint):
                    generic = self.synonyms.get(member, member)
                    break

        classes: list[str] = []
        if generic:
            direct = self.members_to_class.get(generic)
            if direct:
                classes.append(direct)
            for member, class_id in self.members_to_class.items():
                if member == generic or member in generic.split() or generic in member.split():
                    if class_id not in classes:
                        classes.append(class_id)
            # A molecule can legitimately sit in more than one class
            # (aspirin is both an antiplatelet and, at high dose, an NSAID).
            for member, class_id in self.members_to_class.items():
                if re.search(rf"\b{re.escape(member)}\b", generic) and class_id not in classes:
                    classes.append(class_id)

        return Resolved(
            name=name,
            generic=generic,
            classes=tuple(sorted(classes)),
            matched=bool(generic or classes),
        )

    def resolve_all(self, medicines) -> list[Resolved]:
        out = []
        for medicine in medicines:
            name = getattr(medicine, "name", "")
            hint = getattr(medicine, "generic", "")
            out.append(self.resolve(name, hint))
        return out

    # ---- knowledge queries --------------------------------------------
    @property
    def disclaimer(self) -> str:
        return str(
            self.raw.get(
                "disclaimer",
                "This is not medical advice.",
            )
        )

    @property
    def sources(self) -> list[str]:
        value = self.raw.get("sources", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def updated(self) -> str:
        return str(self.raw.get("updated", ""))

    @property
    def version(self) -> int:
        return int(self.raw.get("version", 1))


def _build(raw: dict) -> Knowledge:
    members: dict[str, str] = {}
    for class_id, entry in raw.get("classes", {}).items():
        if not isinstance(entry, dict):
            continue
        for member in entry.get("members", []):
            key = str(member).strip().lower()
            if key:
                members[key] = class_id
    synonyms = {
        str(key).strip().lower(): str(value).strip().lower()
        for key, value in (raw.get("synonyms") or {}).items()
    }
    generics = set(members) | set(synonyms.values())
    return Knowledge(raw=raw, members_to_class=members, synonyms=synonyms, generics=generics)


_lock = threading.Lock()


@lru_cache(maxsize=1)
def load() -> Knowledge:
    path = paths.knowledge_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return _build(raw)


def reload() -> Knowledge:
    """Drop the cached snapshot (used by tests that swap the data file)."""
    with _lock:
        load.cache_clear()
    return load()


def as_dict(resolved: Resolved, knowledge: Knowledge | None = None) -> dict:
    book = knowledge or load()
    return {
        "name": resolved.name,
        "generic": resolved.generic,
        "classes": list(resolved.classes),
        "classLabels": [book.class_label(cid) for cid in resolved.classes],
        "matched": resolved.matched,
    }

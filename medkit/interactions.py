from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .knowledge import SEVERITIES, SEVERITY_RANK, Knowledge, Resolved, load

# The blood-pressure medicines an NSAID quietly works against. Kept as one
# list because "NSAID + BP tablet" is the single warning this checker must
# never miss — it is common, and the NSAID is usually bought over the counter.
BP_CLASSES = (
    "ace_inhibitor",
    "arb",
    "beta_blocker",
    "ccb_dihydropyridine",
    "ccb_non_dhp",
    "thiazide",
    "loop_diuretic",
    "k_sparing",
)

NSAID_CLASSES = ("nsaid", "cox2")

# NSAIDs hurt these hardest: they blunt the drug, injure the kidney and (with
# a potassium-sparing diuretic) push potassium up.
_HARDEST_BP = ("ace_inhibitor", "arb", "loop_diuretic", "k_sparing")


@dataclass(frozen=True)
class Finding:
    """One interaction between two of the medicines on the list."""

    a: str
    b: str
    severity: str
    effect: str
    advice: str
    a_generic: str = ""
    b_generic: str = ""
    kind: str = "drug"
    rule: str = ""

    @property
    def pair(self) -> tuple[str, str]:
        return tuple(sorted((self.a, self.b)))

    @property
    def severity_label(self) -> str:
        return self.severity.title()

    @property
    def is_nsaid_bp(self) -> bool:
        return self.kind == "nsaid-bp"

    def to_dict(self) -> dict:
        return {
            "a": self.a,
            "b": self.b,
            "aGeneric": self.a_generic,
            "bGeneric": self.b_generic,
            "severity": self.severity,
            "severityLabel": self.severity_label,
            "effect": self.effect,
            "advice": self.advice,
            "kind": self.kind,
            "rule": self.rule,
            "nsaidBp": self.is_nsaid_bp,
        }


def _as_list(value) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _active(medicines: Sequence, book: Knowledge) -> list[tuple[object, Resolved]]:
    out = []
    for medicine in medicines:
        if not getattr(medicine, "active", True):
            continue
        resolved = book.resolve(medicine.name, getattr(medicine, "generic", ""))
        if resolved.matched:
            out.append((medicine, resolved))
    return out


def check(
    medicines: Sequence,
    knowledge: Knowledge | None = None,
) -> list[Finding]:
    """Compare every active medicine with every other one.

    One card per pair, carrying that pair's worst severity: the same two
    tablets matching three overlapping rules should read as one warning, not
    three near-identical ones.
    """
    book = knowledge or load()
    active = _active(medicines, book)

    findings: list[Finding] = []
    seen: set[tuple] = set()

    for rule in book.raw.get("interactions", []):
        if not isinstance(rule, dict):
            continue
        severity = str(rule.get("severity", "moderate")).lower()
        if severity not in SEVERITIES:
            severity = "moderate"
        for concept_a in _as_list(rule.get("a", "")):
            concepts_b = _as_list(rule.get("b", ""))
            nsaid_bp = (concept_a in NSAID_CLASSES and any(c in BP_CLASSES for c in concepts_b)) or (
                concept_a in BP_CLASSES and any(c in NSAID_CLASSES for c in concepts_b)
            )
            for medicine_a, item_a in active:
                if concept_a not in item_a.concepts:
                    continue
                for medicine_b, item_b in active:
                    if medicine_a is medicine_b:
                        continue
                    if not any(c in item_b.concepts for c in concepts_b):
                        continue
                    key = (tuple(sorted((medicine_a.name, medicine_b.name))), concept_a, tuple(concepts_b))
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        Finding(
                            a=medicine_a.name,
                            b=medicine_b.name,
                            severity=severity,
                            effect=str(rule.get("effect", "")),
                            advice=str(rule.get("advice", "")),
                            a_generic=item_a.generic,
                            b_generic=item_b.generic,
                            kind="nsaid-bp" if nsaid_bp else "drug",
                            rule=f"{concept_a}+{'/'.join(concepts_b)}",
                        )
                    )

    findings.extend(_triple_whammy(book, active))
    return _collapse(findings)


def _collapse(findings: list[Finding]) -> list[Finding]:
    """Keep the worst finding per unordered pair of medicines."""
    best: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        current = best.get(finding.pair)
        if current is None or SEVERITY_RANK[finding.severity] > SEVERITY_RANK[current.severity]:
            best[finding.pair] = finding
        elif (
            SEVERITY_RANK[finding.severity] == SEVERITY_RANK[current.severity]
            and len(finding.rule) < len(current.rule)
        ):
            best[finding.pair] = finding
    out = list(best.values())
    out.sort(key=lambda item: (-SEVERITY_RANK[item.severity], item.a, item.b))
    return out


def _triple_whammy(book: Knowledge, active) -> list[Finding]:
    """NSAID + ACE inhibitor/ARB + diuretic — the classic kidney hazard."""
    spec = book.raw.get("triple_whammy") or {}
    if not spec:
        return []
    groups = spec.get("requires") or []
    if len(groups) != 3:
        return []
    present: list[tuple[str, Resolved]] = []
    for group in groups:
        concepts = _as_list(group)
        hit = next(
            ((m.name, r) for m, r in active if any(c in r.concepts for c in concepts)),
            None,
        )
        if hit is None:
            return []
        present.append(hit)
    names = sorted({name for name, _ in present})
    if len(names) < 3:
        # One medicine covering two groups is not a triple.
        return []
    first = next(r.generic for n, r in present if n == names[0])
    return [
        Finding(
            a=names[0],
            b=", ".join(names[1:]),
            severity=str(spec.get("severity", "severe")),
            effect=str(spec.get("effect", "")),
            advice=str(spec.get("advice", "")),
            a_generic=first,
            kind="nsaid-bp",
            rule="triple-whammy",
        )
    ]


def nsaid_with_bp(medicines: Sequence, knowledge: Knowledge | None = None) -> list[Finding]:
    """The specific warning the panel headlines: NSAIDs against BP tablets."""
    return [finding for finding in check(medicines, knowledge) if finding.is_nsaid_bp]


def summarize(findings: Iterable[Finding]) -> dict:
    counts = {name: 0 for name in SEVERITIES}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    worst = "mild"
    for name in SEVERITIES:
        if counts.get(name):
            worst = name
    return {"total": sum(counts.values()), "bySeverity": counts, "worst": worst}

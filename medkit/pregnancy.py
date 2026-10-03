from __future__ import annotations

from typing import Sequence

from .knowledge import Knowledge, load

# Order used when ranking how bad a flag is.
RISK_ORDER = ("usually acceptable", "caution", "avoid", "contraindicated")
RISK_RANK = {risk: index for index, risk in enumerate(RISK_ORDER)}

RISK_COLORS = {
    "usually acceptable": "#c3c8d0",
    "caution": "#9aa0a8",
    "avoid": "#9aa0a8",
    "contraindicated": "#f2f4f7",
}

STATUS_LABELS = {
    "none": "not pregnant / not breastfeeding",
    "pregnant": "pregnant",
    "breastfeeding": "breastfeeding",
    "trying": "trying to conceive",
    "postpartum": "postpartum",
}

# `trying` and `postpartum` are treated like pregnancy for the purposes of
# "do not take this while you could be carrying", because the warning window
# starts before a positive test.
PREGNANCY_WINDOW = ("pregnant", "trying", "postpartum")


def _as_list(value) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _applies(rule: dict, status: str) -> bool:
    when = str(rule.get("when", "pregnant")).lower()
    if when == "both":
        return status in PREGNANCY_WINDOW or status == "breastfeeding"
    if when == "breastfeeding":
        return status == "breastfeeding"
    return status in PREGNANCY_WINDOW


def check(
    medicines: Sequence,
    profile: dict | None = None,
    knowledge: Knowledge | None = None,
) -> dict:
    """Flag medicines that are unsafe (or need a conversation) right now."""
    book = knowledge or load()
    status = str((profile or {}).get("status", "none") or "none").lower()
    findings: list[dict] = []

    if status != "none":
        for medicine in medicines:
            if not getattr(medicine, "active", True):
                continue
            resolved = book.resolve(medicine.name, getattr(medicine, "generic", ""))
            for rule in book.raw.get("pregnancy", []):
                if not isinstance(rule, dict) or not _applies(rule, status):
                    continue
                drugs = _as_list(rule.get("drugs", []))
                if not any(drug in resolved.concepts for drug in drugs):
                    continue
                risk = str(rule.get("risk", "caution")).lower()
                if risk not in RISK_RANK:
                    risk = "caution"
                findings.append(
                    {
                        "name": medicine.name,
                        "generic": resolved.generic,
                        "risk": risk,
                        "riskLabel": risk.title(),
                        "riskColor": RISK_COLORS[risk],
                        "note": str(rule.get("note", "")),
                        "alternative": str(rule.get("alternative", "")),
                        "when": str(rule.get("when", "pregnant")),
                    }
                )

    # One card per medicine, carrying the worst risk that applies to it.
    worst: dict[str, dict] = {}
    for finding in findings:
        current = worst.get(finding["name"])
        if current is None or RISK_RANK[finding["risk"]] > RISK_RANK[current["risk"]]:
            worst[finding["name"]] = finding
    findings = list(worst.values())
    findings.sort(key=lambda item: -RISK_RANK[item["risk"]])

    flagged = [f for f in findings if RISK_RANK[f["risk"]] >= RISK_RANK["avoid"]]
    return {
        "status": status,
        "statusLabel": STATUS_LABELS.get(status, status),
        "active": status != "none",
        "findings": findings,
        "flagged": flagged,
        "count": len(findings),
        "countFlagged": len(flagged),
        "worst": findings[0]["risk"] if findings else "",
        "consult": (
            "Ask your doctor or pharmacist before taking anything new — "
            "including anything bought over the counter."
        ),
        "disclaimer": book.disclaimer,
    }


def safer_alternatives(finding: dict) -> str:
    return str(finding.get("alternative") or "Ask your doctor for a safer alternative.")

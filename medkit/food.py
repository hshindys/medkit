from __future__ import annotations

from typing import Sequence

from .knowledge import Knowledge, Resolved, load

# Anything at or above this is worth putting in front of the user rather than
# burying it in a per-medicine note.
ALERT_RANK = {"mild": 0, "moderate": 1, "severe": 2}


def label_for(rule: dict) -> str:
    """"avoid grapefruit" or "take with food" — the relation decides.

    A handful of entries are meal-timing advice ("always take with a meal")
    rather than an avoidance, and calling those "avoid food" would be actively
    dangerous for a sulfonylurea.
    """
    foods = _as_list(rule.get("with", []))
    joined = "/".join(foods)
    if str(rule.get("rule", "avoid")) == "with":
        return f"take with {joined}"
    return f"avoid {joined}"


def _as_list(value) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _timing(book: Knowledge, resolved: Resolved) -> str:
    timing = book.raw.get("meal_timing") or {}
    by_drug = timing.get("by_drug") or {}
    by_class = timing.get("by_class") or {}
    if resolved.generic and resolved.generic in by_drug:
        return str(by_drug[resolved.generic])
    for class_id in resolved.classes:
        if class_id in by_class:
            return str(by_class[class_id])
    return ""


def _matching_rules(book: Knowledge, resolved: Resolved) -> list[dict]:
    out = []
    for rule in book.raw.get("food", []):
        if not isinstance(rule, dict):
            continue
        drugs = _as_list(rule.get("drugs", []))
        if any(drug in resolved.concepts for drug in drugs):
            out.append(rule)
    return out


def tips_for(medicine, book: Knowledge | None = None) -> dict:
    """Everything the knowledge base says about eating around one medicine."""
    knowledge = book or load()
    resolved = knowledge.resolve(medicine.name, getattr(medicine, "generic", ""))
    rules = _matching_rules(knowledge, resolved)
    rules.sort(key=lambda rule: -ALERT_RANK.get(str(rule.get("severity", "mild")), 0))
    return {
        "name": medicine.name,
        "generic": resolved.generic,
        "matched": resolved.matched,
        "timing": _timing(knowledge, resolved),
        "rules": [
            {
                "relation": str(rule.get("rule", "avoid")),
                "foods": _as_list(rule.get("with", [])),
                "label": label_for(rule),
                "severity": str(rule.get("severity", "mild")),
                "severityLabel": str(rule.get("severity", "mild")).title(),
                "tip": str(rule.get("tip", "")),
                "timing": str(rule.get("timing", "")),
            }
            for rule in rules
        ],
    }


def check(medicines: Sequence, knowledge: Knowledge | None = None) -> list[dict]:
    """Per-medicine food advice, worst severity first across the whole list."""
    book = knowledge or load()
    rows = [tips_for(medicine, book) for medicine in medicines if getattr(medicine, "active", True)]
    rows.sort(
        key=lambda row: -max(
            (ALERT_RANK.get(rule["severity"], 0) for rule in row["rules"]),
            default=0,
        )
    )
    return rows


def alerts(medicines: Sequence, knowledge: Knowledge | None = None) -> list[dict]:
    """The food combinations worth a notification: moderate and severe only.

    Meal-timing advice ("take with food") only interrupts when skipping the
    meal is genuinely dangerous — that is the severe entries such as
    sulfonylureas and insulin.
    """
    out: list[dict] = []
    for row in check(medicines, knowledge):
        for rule in row["rules"]:
            rank = ALERT_RANK.get(rule["severity"], 0)
            if rank < ALERT_RANK["moderate"]:
                continue
            if rule["relation"] == "with" and rank < ALERT_RANK["severe"]:
                continue
            out.append({"medicine": row["name"], "generic": row["generic"], **rule})
    out.sort(key=lambda item: -ALERT_RANK.get(item["severity"], 0))
    return out


def summarize(medicines: Sequence, knowledge: Knowledge | None = None) -> dict:
    book = knowledge or load()
    rows = check(medicines, book)
    return {
        "medicines": rows,
        "alerts": alerts(medicines, book),
        "disclaimer": book.disclaimer,
        "sources": book.sources,
        "updated": book.updated,
    }

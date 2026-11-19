"""Transforme les réponses en signaux, et les signaux en curseurs.

Un signal situe le jeune entre 0 et 100 sur un curseur. Le curseur est leur moyenne pondérée :
le poids dépend de la solidité de la source, pour qu'un test validé compte plus qu'une question
de quiz inspirée de ce test.
"""
from __future__ import annotations

from dataclasses import dataclass

from .catalog import Catalog, likert_parts

TIER_WEIGHTS = {
    "validated": 1.0, "performance": 1.0, "translated": 0.75, "adapted": 0.5, "custom": 0.5, "talent": 0.25
}
MAX_TEXT_FACT = 120


class InvalidAnswer(ValueError):
    pass


@dataclass
class ScoredAnswer:
    value: object
    label: str
    signals: list[dict]
    fact: tuple[str, str, str] | None = None  # clé, intitulé, valeur


def signal(trait: str, value: float, weight: float, tier: str) -> dict:
    return {"trait": trait, "value": round(float(value), 2), "weight": float(weight), "tier": tier}


def item_scale(instrument: dict, item: dict) -> dict:
    return item.get("scale") or instrument["scale"]


def _score_likert(instrument: dict, item: dict, value) -> ScoredAnswer:
    scale = item_scale(instrument, item)
    low, high = scale["min"], scale["max"]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidAnswer("Réponse hors de l'échelle.")
    position = (value - low) / (high - low) * 100
    signals = [
        signal(
            part["trait"],
            position if part.get("keyed", "+") == "+" else 100 - position,
            part.get("weight", 1),
            part.get("tier", instrument["tier"]),
        )
        for part in likert_parts(item)
    ]
    labels = scale.get("labels") or []
    label = labels[value - low] if len(labels) == high - low + 1 else str(value)
    return ScoredAnswer(value, label, signals)


def _score_choice(instrument: dict, item: dict, value) -> ScoredAnswer:
    if isinstance(value, dict):
        if not item.get("allow_text"):
            raise InvalidAnswer("Réponse libre non prévue.")
        return _score_text(value)
    options = {option["id"]: option for option in item["options"]}
    maximum = item.get("max_choices", 1)
    chosen = value if isinstance(value, list) else [value]
    if (
        not chosen
        or len(chosen) > maximum
        or len(set(map(str, chosen))) != len(chosen)
        or any(not isinstance(c, str) or c not in options for c in chosen)
    ):
        raise InvalidAnswer("Choix inconnu.")
    signals = [
        signal(s["trait"], s["value"], s.get("weight", 1), s.get("tier", instrument["tier"]))
        for option_id in chosen
        for s in options[option_id].get("signals", [])
    ]
    return ScoredAnswer(value, ", ".join(options[c]["label"] for c in chosen), signals)


def _score_text(value) -> ScoredAnswer:
    text = value.get("text") if isinstance(value, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise InvalidAnswer("Réponse vide.")
    text = " ".join(text.split())
    if len(text) > MAX_TEXT_FACT:
        raise InvalidAnswer("Réponse trop longue.")
    return ScoredAnswer({"text": text}, text, [])


def score_answer(instrument: dict, item: dict, value) -> ScoredAnswer:
    kind = item["type"]
    if kind == "likert":
        scored = _score_likert(instrument, item, value)
    elif kind == "choice":
        scored = _score_choice(instrument, item, value)
    else:
        scored = _score_text(value)
    if "fact" in item:
        scored.fact = (item["fact"], item["fact_label"], scored.label[:160])
    return scored


def scale_scores(instrument: dict, answers: list) -> dict:
    """Score brut par échelle pour la psychologue (somme des items Likert, clés inversées comprises)."""
    items = {item["id"]: item for item in instrument.get("items", [])}
    scales: dict[str, dict] = {}
    for answer in answers:
        item = items.get(answer.item_id)
        if item is None or answer.skipped or item["type"] != "likert":
            continue
        scale = item_scale(instrument, item)
        low, high = scale["min"], scale["max"]
        for part in likert_parts(item):
            keyed = answer.value if part.get("keyed", "+") == "+" else low + high - answer.value
            entry = scales.setdefault(part["trait"], {"n": 0, "raw_sum": 0, "raw_min": 0, "raw_max": 0})
            entry["n"] += 1
            entry["raw_sum"] += keyed
            entry["raw_min"] += low
            entry["raw_max"] += high
    for entry in scales.values():
        span = entry["raw_max"] - entry["raw_min"]
        entry["percent"] = round((entry["raw_sum"] - entry["raw_min"]) / span * 100, 1) if span else 0
    return scales


def _weighted(rows: list[dict]) -> tuple[float | None, float]:
    total = sum(row["weight"] * TIER_WEIGHTS.get(row["tier"], 0.5) for row in rows)
    if total <= 0:
        return None, 0.0
    value = sum(row["value"] * row["weight"] * TIER_WEIGHTS.get(row["tier"], 0.5) for row in rows)
    return round(value / total, 1), total


def confidence(total_weight: float) -> str:
    if total_weight <= 0:
        return "none"
    if total_weight < 2:
        return "low"
    return "medium" if total_weight < 5 else "high"


def aggregate(catalog: Catalog, signals: list[dict]) -> dict[str, dict]:
    """Calcule tous les curseurs : valeur, volume de données et détail par niveau de preuve."""
    by_trait: dict[str, list[dict]] = {trait_id: [] for trait_id in catalog.traits}
    for row in signals:
        if row["trait"] in by_trait:
            by_trait[row["trait"]].append(row)

    cursors = {}
    for trait_id, rows in by_trait.items():
        value, total = _weighted(rows)
        by_tier = {}
        for tier in sorted({row["tier"] for row in rows}):
            subset = [row for row in rows if row["tier"] == tier]
            by_tier[tier] = {"value": _weighted(subset)[0], "n": len(subset)}
        cursors[trait_id] = {
            "trait": trait_id,
            "value": value,
            "n": len(rows),
            "confidence": confidence(total),
            "by_tier": by_tier,
        }
    return cursors

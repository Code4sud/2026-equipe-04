"""Remplit des parties fictives pour la démonstration, à partir du contenu réellement chargé."""
from __future__ import annotations

import random
import uuid

from ..errors import ApiError
from ..extensions import db
from ..models import User
from .catalog import likert_parts
from .performance import SCORERS
from .scoring import item_scale
from . import service as game


def _likert_value(instrument: dict, item: dict, bias: dict, rng: random.Random) -> int:
    scale = item_scale(instrument, item)
    low, high = scale["min"], scale["max"]
    targets = []
    for part in likert_parts(item):
        target = bias.get(part["trait"], 50)
        targets.append(target if part.get("keyed", "+") == "+" else 100 - target)
    position = sum(targets) / len(targets) if targets else 50
    position = max(0, min(100, position + rng.uniform(-14, 14)))
    return round(low + position / 100 * (high - low))


def _option_value(item: dict, bias: dict, facts: dict, rng: random.Random):
    options = item["options"]
    wanted = facts.get(item.get("fact"))
    match = next((o for o in options if o["label"] == wanted), None)
    if match:
        return match["id"]
    if wanted and item.get("allow_text"):
        return {"text": wanted}

    def distance(option: dict) -> float:
        signals = [s for s in option.get("signals", []) if s["trait"] in bias]
        if not signals:
            return 45 + rng.random() * 10
        return sum(abs(s["value"] - bias[s["trait"]]) for s in signals) / len(signals) + rng.random() * 8

    return min(options, key=distance)["id"]


def _answer(instrument: dict, item: dict, persona: dict, rng: random.Random):
    bias, facts = persona.get("bias", {}), persona.get("facts", {})
    if item["type"] == "likert":
        return _likert_value(instrument, item, bias, rng)
    if item["type"] == "choice":
        return _option_value(item, bias, facts, rng)
    return {"text": facts.get(item["fact"], "Découvrir de nouveaux trucs")}


def seed_youth_game(user: User, persona: dict) -> None:
    """Joue tous les jeux disponibles pour un jeune fictif, de façon reproductible."""
    rng = random.Random(f"{user.email}:game")
    game.set_consent(user, persona.get("share", True))
    for instrument in game.catalog().ordered_instruments():
        try:
            payload, _ = game.start_run(user, instrument["id"])
        except ApiError as error:
            if error.code == "locked":  # Prérequis absent du contenu chargé (quiz d'arrivée).
                continue
            raise
        run_uuid = uuid.UUID(payload["run"]["id"])
        body = {}
        if instrument["kind"] == "performance":
            scorer = SCORERS[instrument["performance"]["scorer"]]
            body = {"trials": scorer.demo(instrument, rng, persona.get("skill", 0.85))}
        else:
            for item in instrument["items"]:
                value = _answer(instrument, item, persona, rng)
                game.save_answer(
                    user,
                    run_uuid,
                    item["id"],
                    {"value": value, "response_ms": rng.randint(1800, 9000)},
                )
        game.complete_run(user, run_uuid, body)
    db.session.commit()

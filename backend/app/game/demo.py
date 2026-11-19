"""Remplit des parties fictives pour la démonstration, à partir du contenu réellement chargé."""
from __future__ import annotations

import random
import uuid

from sqlalchemy import select

from ..extensions import db
from ..models import GameRun, GameRunStatus, User
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


def _play(user: User, instrument: dict, persona: dict) -> None:
    # Un tirage propre à chaque jeu : le résultat ne dépend pas des jeux déjà joués avant.
    rng = random.Random(f"{user.email}:game:{instrument['id']}")
    payload, _ = game.start_run(user, instrument["id"])
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


def seed_youth_game(user: User, persona: dict) -> None:
    """Joue, pour un jeune fictif, chaque jeu qu'il n'a pas encore commencé, prérequis d'abord.

    Relancer la commande ne rejoue rien : elle ajoute seulement les jeux livrés depuis, ou ceux
    qu'un lancement interrompu n'a pas atteints. Les réponses sont reproductibles.
    """
    rows = db.session.execute(
        select(GameRun.instrument_id, GameRun.status).where(GameRun.youth_id == user.id)
    ).all()
    started = {instrument_id for instrument_id, _ in rows}
    completed = {instrument_id for instrument_id, status in rows if status == GameRunStatus.COMPLETED}
    pending = [i for i in game.catalog().ordered_instruments() if i["id"] not in started]
    # Un jeu peut venir avant son prérequis dans l'ordre du catalogue : on repasse tant qu'un jeu
    # se débloque. Un jeu dont le prérequis manque au contenu (quiz pas encore livré) reste de côté.
    progressed = True
    while pending and progressed:
        progressed = False
        for instrument in list(pending):
            if any(required not in completed for required in instrument.get("requires", [])):
                continue
            _play(user, instrument, persona)
            completed.add(instrument["id"])
            pending.remove(instrument)
            progressed = True
    db.session.commit()

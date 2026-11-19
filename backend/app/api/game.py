"""Quiz, mini-jeux et fiche perso côté jeune ; curseurs et réponses côté psychologue.

Le jeune accepte à l'inscription la transmission de ses données à sa psychologue :
les résultats de jeux lui sont donc toujours visibles, modifications du jeune comprises.
"""
from __future__ import annotations

import uuid

from flask import g, jsonify, request

from ..game import service as game
from ..models import Role
from ..security import require_roles
from . import api
from .backoffice import STAFF_ROLES, _youth_or_404
from .helpers import json_body


def _optional_body() -> dict:
    return json_body() if request.get_data() else {}


@api.get("/me/game")
@require_roles(Role.YOUTH)
def my_game():
    return jsonify(game.game_status(g.user))


@api.post("/me/game/instruments/<instrument_id>/runs")
@require_roles(Role.YOUTH)
def start_game_run(instrument_id: str):
    payload, created = game.start_run(g.user, instrument_id)
    return jsonify(payload), 201 if created else 200


@api.put("/me/game/runs/<uuid:run_id>/answers/<item_id>")
@require_roles(Role.YOUTH)
def save_game_answer(run_id: uuid.UUID, item_id: str):
    return jsonify(game.save_answer(g.user, run_id, item_id, json_body()))


@api.post("/me/game/runs/<uuid:run_id>/pause")
@require_roles(Role.YOUTH)
def pause_game_run(run_id: uuid.UUID):
    return jsonify(game.pause_run(g.user, run_id))


@api.post("/me/game/runs/<uuid:run_id>/complete")
@require_roles(Role.YOUTH)
def complete_game_run(run_id: uuid.UUID):
    return jsonify(game.complete_run(g.user, run_id, _optional_body()))


@api.get("/me/game/sheet")
@require_roles(Role.YOUTH)
def my_character_sheet():
    return jsonify(game.character_sheet(g.user))


@api.patch("/me/game/facts/<key>")
@require_roles(Role.YOUTH)
def update_my_fact(key: str):
    return jsonify(game.update_fact(g.user, key, json_body()))


@api.put("/me/game/traits/<trait_id>/feedback")
@require_roles(Role.YOUTH)
def update_my_trait_feedback(trait_id: str):
    return jsonify(game.set_trait_feedback(g.user, trait_id, json_body().get("verdict")))


@api.get("/backoffice/game/catalog")
@require_roles(*STAFF_ROLES)
def game_catalog():
    return jsonify(game.psy_catalog())


@api.get("/backoffice/youths/<uuid:youth_id>/game")
@require_roles(*STAFF_ROLES)
def youth_game(youth_id: uuid.UUID):
    user, _profile = _youth_or_404(youth_id)
    return jsonify(game.psy_overview(user))


@api.get("/backoffice/youths/<uuid:youth_id>/game/runs/<uuid:run_id>")
@require_roles(*STAFF_ROLES)
def youth_game_run(youth_id: uuid.UUID, run_id: uuid.UUID):
    user, _profile = _youth_or_404(youth_id)
    return jsonify(game.psy_run_detail(user, run_id))


@api.get("/backoffice/youths/<uuid:youth_id>/game/traits/<trait_id>")
@require_roles(*STAFF_ROLES)
def youth_game_trait(youth_id: uuid.UUID, trait_id: str):
    user, _profile = _youth_or_404(youth_id)
    return jsonify(game.psy_trait_detail(user, trait_id))

"""Talents et jeu : seuls les talents repérés par Néo comptent pour les curseurs, l'XP et les badges.

Un talent que le jeune ajoute lui-même sur sa carte reçoit la catégorie par défaut
« savoir_faire » : le compter ferait monter « Intérêt manuel et technique » quel que soit le
talent et donnerait de l'XP à chaque nom tapé.
"""
from __future__ import annotations

import uuid

from test_game import cursor, finish_onboarding, fixture_catalog, youth_id  # noqa: F401

from app.extensions import db
from app.models import Conversation, Skill, SkillStatus


def add_talent(client, youth, name: str) -> dict:
    response = client.post("/api/me/skills", json={"name": name, "description": "Souvent"}, headers=youth)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["skill"]


def sheet(client, youth) -> dict:
    return client.get("/api/me/game/sheet", headers=youth).get_json()


def overview(client, youth, psychologist) -> dict:
    return client.get(f"/api/backoffice/youths/{youth_id(client, youth)}/game", headers=psychologist).get_json()


def test_talents_the_youth_adds_move_no_cursor_xp_or_badge(client, youth, psychologist):
    for name in ("Chanter dans une chorale", "Dessiner des mangas", "Monter des vidéos"):
        add_talent(client, youth, name)
    data = sheet(client, youth)
    assert data["progress"]["xp"] == 0
    assert not any(badge["earned"] for badge in data["progress"]["badges"])
    assert data["identity"]["archetype"] is None
    # Ils restent sur sa fiche, avec leur origine.
    assert {t["origin"] for t in data["talents"]["validated"]} == {"youth"}
    assert len(data["talents"]["validated"]) == 3
    psy = overview(client, youth, psychologist)
    assert cursor(psy, "riasec_r")["value"] is None


def test_a_talent_neo_found_still_counts(app, client, youth, psychologist):
    target = uuid.UUID(youth_id(client, youth))
    with app.app_context():
        conversation = Conversation(youth_id=target, transcript_key="k")
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Skill(
                youth_id=target,
                conversation_id=conversation.id,
                source_message_id="m1",
                name="Créer des affiches",
                name_key="creer des affiches",
                category="creativite",
                source_quote="je fais les affiches du club",
                status=SkillStatus.VALIDATED,
            )
        )
        db.session.commit()
    add_talent(client, youth, "Chanter dans une chorale")
    data = sheet(client, youth)
    assert data["progress"]["xp"] == 25
    assert {t["origin"] for t in data["talents"]["validated"]} == {"ai", "youth"}
    psy = overview(client, youth, psychologist)
    assert cursor(psy, "riasec_a")["value"] is not None
    assert cursor(psy, "riasec_r")["value"] is None


def test_the_youth_list_counts_games_as_activity_and_game_changes_to_discuss(client, youth, psychologist):
    def row():
        rows = client.get("/api/backoffice/youths", headers=psychologist).get_json()["youths"]
        return next(r for r in rows if r["id"] == youth_id(client, youth))

    assert row()["last_activity_at"] is None and row()["game_changes"] == 0
    finish_onboarding(client, youth)
    assert row()["last_activity_at"] is not None
    verdict = client.put("/api/me/game/traits/extraversion/feedback", json={"verdict": "disagree"}, headers=youth)
    assert verdict.status_code == 200
    client.patch("/api/me/game/facts/couleur_preferee", json={"value": "Vert"}, headers=youth)
    client.patch("/api/me/game/facts/couleur_preferee", json={"hidden": True}, headers=youth)
    # Un curseur jugé et un détail modifié deux fois : deux sujets à discuter.
    assert row()["game_changes"] == 2

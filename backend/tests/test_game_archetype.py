"""Archétype : habillage ludique tiré du curseur de caractère le plus marqué (service.archetype_for).

Il remplace le clan. Le jeune voit l'archétype et sa qualité en clair ; la psychologue voit en plus
le curseur, le pôle et la valeur qui l'ont désigné.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from test_game import answer, complete, cursor, finish_onboarding, fixture_catalog, start, youth_id  # noqa: F401

from app.extensions import db
from app.game import service as game
from app.game.catalog import ARCHETYPE_POLES, BALANCED_POLE, Catalog, ContentError
from app.game.service import BALANCED_LABEL, BALANCED_MARGIN
from app.models import Conversation, Skill, SkillStatus

GAME_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "game"
YOUTH_FIELDS = {"id", "name", "motto", "description", "emoji", "quality"}
PSY_FIELDS = YOUTH_FIELDS | {"trait", "pole", "value", "trait_label", "pole_label"}


def archetype_id(app, **values) -> str | None:
    """Archétype de curseurs fictifs : les curseurs absents n'ont pas de valeur."""
    with app.app_context():
        cursors = {trait_id: {"value": values.get(trait_id)} for trait_id in game.catalog().traits}
        found = game.archetype_for(cursors)
    return found["id"] if found else None


def overview(client, psychologist, youth) -> dict:
    response = client.get(f"/api/backoffice/youths/{youth_id(client, youth)}/game", headers=psychologist)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


# --- Calcul ---


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # Le curseur le plus éloigné du milieu l'emporte, d'un côté comme de l'autre.
        ({"extraversion": 70, "openness": 15}, "racine"),
        ({"agreeableness": 18, "conscientiousness": 80, "openness": 72}, "boussole"),
        ({"emotional_stability": 90, "extraversion": 15}, "roc"),
        # À égalité, l'ordre de traits/10_personality.json départage.
        ({"extraversion": 30, "agreeableness": 70}, "lanterne"),
        ({"openness": 80, "emotional_stability": 20}, "flamme"),
        # Aussi avec des dixièmes, dont les écarts ne tombent pas juste en virgule flottante :
        # 64,1 - 50 et 50 - 35,9 font tous deux 14,1.
        ({"extraversion": 64.1, "agreeableness": 35.9}, "etincelle"),
        ({"extraversion": 35.6, "agreeableness": 64.4}, "lanterne"),
        ({"conscientiousness": 64.1, "openness": 35.9}, "charpente"),
        # Jusqu'à 8 points du milieu, le curseur est « Entre les deux » : archétype équilibré.
        ({"extraversion": 58}, "cameleon"),
        ({"extraversion": 42, "openness": 55}, "cameleon"),
        ({"conscientiousness": 50}, "cameleon"),
        # Au-delà, son pôle compte, dès le dixième suivant.
        ({"extraversion": 59}, "etincelle"),
        ({"extraversion": 41}, "lanterne"),
        ({"emotional_stability": 59, "openness": 42}, "roc"),
        ({"extraversion": 58.1}, "etincelle"),
        ({"extraversion": 41.9}, "lanterne"),
    ],
)
def test_the_most_marked_personality_cursor_gives_the_archetype(app, values, expected):
    assert archetype_id(app, **values) == expected


def test_the_balanced_margin_is_the_one_of_entre_les_deux(app):
    # Un curseur affiché « Entre les deux » au jeune ne désigne jamais un pôle.
    with app.app_context():
        for value in (50 - BALANCED_MARGIN, 50 + BALANCED_MARGIN):
            assert game.youth_leaning("openness", value) == BALANCED_LABEL
            assert archetype_id(app, openness=value) == "cameleon"
        for value in (50 - BALANCED_MARGIN - 1, 50 + BALANCED_MARGIN + 1):
            assert game.youth_leaning("openness", value) != BALANCED_LABEL
            assert archetype_id(app, openness=value) != "cameleon"


def test_only_personality_values_count(app):
    # Sans valeur de caractère, pas encore d'archétype, quels que soient les intérêts ou les jeux.
    assert archetype_id(app) is None
    assert archetype_id(app, riasec_r=100, interest_digital=95, working_memory=90) is None
    assert archetype_id(app, riasec_r=100, openness=70) == "horizon"


def test_the_youth_sees_the_quality_of_the_pole_never_the_cursor(app):
    with app.app_context():
        cat = game.catalog()
        for archetype in cat.archetypes:
            view = game.youth_archetype(archetype)
            assert set(view) == YOUTH_FIELDS, archetype["id"]
        assert game.youth_archetype(cat.archetype("extraversion", "high"))["quality"] == "Sociable"
        assert game.youth_archetype(cat.archetype("extraversion", "low"))["quality"] == "Réservé·e"
        assert game.youth_archetype(cat.archetype(None, BALANCED_POLE))["quality"] == BALANCED_LABEL
        assert game.youth_archetype(None) is None


# --- Ce que voient le jeune et la psychologue ---


def test_the_psychologist_sees_how_the_archetype_was_chosen(client, youth, psychologist):
    _, result = finish_onboarding(client, youth)  # Réservé à 10, Organisé à 100.
    data = overview(client, psychologist, youth)
    charpente = Catalog().archetype("conscientiousness", "high")
    organised = cursor(data, "conscientiousness")
    assert data["archetype"] == {
        "id": "charpente",
        "name": charpente["name"],
        "motto": charpente["motto"],
        "description": charpente["description"],
        "emoji": charpente["emoji"],
        "quality": "Organisé·e",
        "trait": "conscientiousness",
        "pole": "high",
        "value": organised["value"],
        "trait_label": "Spontané ↔ Organisé",
        "pole_label": "Organisé",
    }
    # Le titre du curseur dit la même chose : « 100 % organisé ».
    assert organised["headline"] == {"percent": 100, "label": "Organisé"}
    # Le jeune voit le même archétype, sans ce qui l'a désigné.
    assert result["archetype"] == {k: v for k, v in data["archetype"].items() if k in YOUTH_FIELDS}


def test_a_balanced_profile_gets_the_balanced_archetype(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    for item_id, value in [("couleur", "jaune"), ("groupe", "b"), ("scooter", "a"), ("agenda", 3)]:
        assert answer(client, youth, run_id, item_id, value).status_code == 200
    result = complete(client, youth, run_id).get_json()
    assert (result["archetype"]["id"], result["archetype"]["quality"]) == ("cameleon", BALANCED_LABEL)
    psy = overview(client, psychologist, youth)["archetype"]
    assert set(psy) == PSY_FIELDS
    assert {k: psy[k] for k in ("trait", "pole", "value", "trait_label", "pole_label")} == {
        "trait": None, "pole": BALANCED_POLE, "value": None, "trait_label": None, "pole_label": BALANCED_LABEL,
    }


def test_no_archetype_before_any_personality_answer(client, youth, psychologist):
    assert client.get("/api/me/game/sheet", headers=youth).get_json()["identity"]["archetype"] is None
    assert overview(client, psychologist, youth)["archetype"] is None


def sheet_archetype(client, youth) -> dict | None:
    return client.get("/api/me/game/sheet", headers=youth).get_json()["identity"]["archetype"]


def test_the_sheet_keeps_the_archetype_for_the_end_of_the_arrival_quiz(app, client, youth, psychologist):
    # Un talent gardé avant le quiz et les réponses d'un quiz en pause comptent déjà pour les
    # curseurs : la psychologue voit l'archétype qu'ils donnent, mais la fiche du jeune le garde
    # secret, comme elle le promet, jusqu'à la révélation de la fin du quiz.
    with app.app_context():
        user_id = uuid.UUID(youth_id(client, youth))
        conversation = Conversation(youth_id=user_id, transcript_key="k")
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Skill(
                youth_id=user_id, conversation_id=conversation.id, source_message_id="m1",
                name="Animer un groupe", name_key="animer un groupe", category="communication",
                source_quote="j'anime le club", status=SkillStatus.VALIDATED,
            )
        )
        db.session.commit()
    assert overview(client, psychologist, youth)["archetype"]["id"] == "etincelle"
    assert sheet_archetype(client, youth) is None

    run_id = start(client, youth)["run"]["id"]
    assert answer(client, youth, run_id, "groupe", "a").status_code == 200
    assert client.post(f"/api/me/game/runs/{run_id}/pause", headers=youth).status_code == 200
    assert sheet_archetype(client, youth) is None

    start(client, youth)
    for item_id, value in [("scooter", "a"), ("couleur", "jaune")]:
        assert answer(client, youth, run_id, item_id, value).status_code == 200
    result = complete(client, youth, run_id).get_json()
    assert result["archetype"]["id"] == "etincelle" and result["previous_archetype"] is None
    assert sheet_archetype(client, youth) == result["archetype"]


def test_the_method_page_lists_every_archetype_and_its_pole(client, psychologist):
    data = client.get("/api/backoffice/game/catalog", headers=psychologist).get_json()
    rows = {row["id"]: row for row in data["archetypes"]}
    assert len(rows) == len(data["archetypes"]) == 11
    assert all(set(row) == PSY_FIELDS - {"value"} for row in rows.values())
    lanterne = rows["lanterne"]
    assert (lanterne["trait"], lanterne["pole"], lanterne["quality"]) == ("extraversion", "low", "Réservé·e")
    assert (lanterne["trait_label"], lanterne["pole_label"]) == ("Réservé ↔ Sociable", "Réservé")
    assert (rows["cameleon"]["trait"], rows["cameleon"]["pole"]) == (None, BALANCED_POLE)


def test_the_backoffice_explains_the_margin_the_server_uses():
    # Le panneau et la page Méthode citent la marge en clair : elle doit rester celle du serveur.
    # Une espace insécable (écrite \u00a0 dans le fichier) garde le nombre avec « points ».
    text = (GAME_FRONT / "backoffice" / "backoffice.fr.ts").read_text(encoding="utf-8")
    text = text.replace("\\u00a0", " ").replace("\u00a0", " ")
    assert text.count(f"plus de {BALANCED_MARGIN} points du milieu") >= 2


def test_the_front_knows_which_archetype_is_balanced():
    # Pour Le Caméléon, la fiche et la fin de partie ne disent pas que l'archétype suit un trait de
    # caractère : l'identifiant que le front reconnaît doit rester celui de archetypes.json.
    balanced = Catalog().archetype(None, BALANCED_POLE)["id"]
    text = (GAME_FRONT / "archetype" / "balanced.ts").read_text(encoding="utf-8")
    assert f"BALANCED_ARCHETYPE_ID = '{balanced}';" in text


# --- Contenu ---


def test_every_personality_pole_has_one_archetype_and_one_is_balanced():
    catalog = Catalog()
    poles = [(archetype["trait"], archetype["pole"]) for archetype in catalog.archetypes]
    expected = [(trait, pole) for trait in catalog.archetype_traits() for pole in ARCHETYPE_POLES]
    assert sorted(poles, key=str) == sorted([*expected, (None, BALANCED_POLE)], key=str)
    assert catalog.archetype_traits() == [
        "extraversion", "agreeableness", "conscientiousness", "emotional_stability", "openness"
    ]


def _remove(archetype_id: str):
    def change(archetypes: list[dict]) -> None:
        archetypes[:] = [a for a in archetypes if a["id"] != archetype_id]

    return change


def _update(archetype_id: str, **fields):
    def change(archetypes: list[dict]) -> None:
        next(a for a in archetypes if a["id"] == archetype_id).update(fields)

    return change


def _drop_field(archetype_id: str, field: str):
    def change(archetypes: list[dict]) -> None:
        next(a for a in archetypes if a["id"] == archetype_id).pop(field)

    return change


def _add(**fields):
    def change(archetypes: list[dict]) -> None:
        archetypes.append({**archetypes[-1], **fields})

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_remove("vent"), "aucun archétype pour le pôle low de conscientiousness"),
        (_remove("cameleon"), "aucun archétype pour le profil équilibré"),
        (_add(id="autre"), "même pôle que l'archétype cameleon"),
        (_update("lanterne", pole="high"), "même pôle que l'archétype etincelle"),
        (_update("etincelle", pole="middle"), "pôle invalide « middle »"),
        (_update("etincelle", trait="riasec_s"), "n'est pas un curseur bipolaire de personnalité"),
        (_update("etincelle", trait="working_memory"), "n'est pas un curseur bipolaire de personnalité"),
        (_update("etincelle", trait="nope"), "curseur inconnu « nope »"),
        (_update("etincelle", trait=None), "curseur inconnu « None »"),
        (_update("cameleon", trait="openness"), "l'archétype équilibré ne vise aucun curseur"),
        (_update("lanterne", id="etincelle"), "identifiant en double"),
        (_drop_field("roc", "emoji"), "champ manquant « emoji »"),
        (_drop_field("roc", "trait"), "champ manquant « trait »"),
        (_update("roc", motto="  "), "« motto » doit être un texte non vide"),
        (_update("roc", name=None), "« name » doit être un texte non vide"),
    ],
)
def test_the_catalog_refuses_inconsistent_archetypes(change, message):
    catalog = Catalog()
    change(catalog.archetypes)
    with pytest.raises(ContentError, match=message):
        catalog.validate()

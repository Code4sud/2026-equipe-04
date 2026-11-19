from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import register

from app.extensions import db
from app.game.catalog import Catalog, ContentError
from app.game.demo import seed_youth_game
from app.game.service import level_floor, level_for
from app.models import Conversation, Skill, SkillStatus, User

FIXTURES = Path(__file__).parent / "fixtures" / "game"


@pytest.fixture(autouse=True)
def fixture_catalog(app):
    app.extensions["game_catalog"] = Catalog(overlays=[FIXTURES])
    # Seuls les contenus de test comptent ici, quel que soit le contenu réel déjà livré.
    catalog = app.extensions["game_catalog"]
    keep = {"onboarding", "fixture_questionnaire", "fixture_span"}
    catalog.instruments = {k: v for k, v in catalog.instruments.items() if k in keep}


def start(client, headers, instrument="onboarding"):
    response = client.post(f"/api/me/game/instruments/{instrument}/runs", headers=headers)
    assert response.status_code in {200, 201}, response.get_json()
    return response.get_json()


def answer(client, headers, run_id, item_id, value=None, **extra):
    return client.put(
        f"/api/me/game/runs/{run_id}/answers/{item_id}",
        json={"value": value, **extra},
        headers=headers,
    )


def complete(client, headers, run_id, **body):
    return client.post(f"/api/me/game/runs/{run_id}/complete", json=body, headers=headers)


def finish_onboarding(client, headers):
    run_id = start(client, headers)["run"]["id"]
    for item_id, value in [
        ("couleur", "jaune"),
        ("passion", {"text": "Jeux   vidéo"}),
        ("groupe", "c"),
        ("scooter", "a"),
        ("agenda", 5),
    ]:
        assert answer(client, headers, run_id, item_id, value).status_code == 200
    response = complete(client, headers, run_id)
    assert response.status_code == 200, response.get_json()
    return run_id, response.get_json()


def youth_id(client, headers):
    return client.get("/api/auth/me", headers=headers).get_json()["user"]["id"]


def cursor(overview, trait):
    for group in overview["cursor_groups"]:
        for item in group["cursors"]:
            if item["id"] == trait:
                return item
    raise AssertionError(trait)


def test_new_youth_must_do_onboarding_and_can_pause(client, youth):
    status = client.get("/api/me/game", headers=youth).get_json()
    assert status["must_onboard"] is True

    run_id = start(client, youth)["run"]["id"]
    assert client.post(f"/api/me/game/runs/{run_id}/pause", headers=youth).status_code == 200
    assert client.get("/api/me/game", headers=youth).get_json()["must_onboard"] is False

    resumed = start(client, youth)
    assert resumed["run"]["id"] == run_id
    assert resumed["run"]["paused_at"] is None
    assert client.get("/api/me/game", headers=youth).get_json()["must_onboard"] is True


def test_status_counts_skipped_questions_as_seen_not_answered(client, youth):
    def quiz():
        instruments = client.get("/api/me/game", headers=youth).get_json()["instruments"]
        return next(item for item in instruments if item["id"] == "onboarding")

    assert (quiz()["state"], quiz()["answered"], quiz()["seen"]) == ("new", 0, 0)
    run_id = start(client, youth)["run"]["id"]
    assert (quiz()["state"], quiz()["answered"], quiz()["seen"]) == ("in_progress", 0, 0)
    skipped = client.put(f"/api/me/game/runs/{run_id}/answers/agenda", json={"skipped": True}, headers=youth)
    assert skipped.status_code == 200
    # Tout passé : rien de répondu, mais le quiz est bien commencé.
    assert (quiz()["answered"], quiz()["seen"]) == (0, 1)
    assert answer(client, youth, run_id, "groupe", "a").status_code == 200
    assert (quiz()["answered"], quiz()["seen"]) == (1, 2)


def test_public_instrument_hides_scoring_keys(client, youth):
    instrument = start(client, youth)["instrument"]
    text = str(instrument)
    assert "signals" not in text and "trait" not in text and "source_id" not in text
    assert instrument["items"][2]["options"][0] == {"id": "a", "label": "J'invite tout le monde"}


def test_answers_are_validated_saved_and_replaced(client, youth):
    run_id = start(client, youth)["run"]["id"]
    assert answer(client, youth, run_id, "groupe", "zzz").status_code == 400
    assert answer(client, youth, run_id, "agenda", 9).status_code == 400
    assert answer(client, youth, run_id, "nope", 1).status_code == 404

    first = answer(client, youth, run_id, "groupe", "a").get_json()
    assert first["xp_gained"] == 2 and first["run"]["answered"] == 1
    again = answer(client, youth, run_id, "groupe", "c").get_json()
    assert again["xp_gained"] == 0 and again["run"]["answered"] == 1
    assert start(client, youth)["answers"] == [{"item_id": "groupe", "value": "c", "skipped": False}]


def test_cannot_touch_someone_elses_run(client, youth):
    run_id = start(client, youth)["run"]["id"]
    other = register(client, "Noa")
    assert answer(client, other, run_id, "groupe", "a").status_code == 404
    assert complete(client, other, run_id).status_code == 404


def test_completion_needs_enough_answers_and_gives_an_archetype_and_xp(client, youth):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "groupe", "a")
    assert complete(client, youth, run_id).status_code == 409

    answer(client, youth, run_id, "scooter", "a")
    client.put(f"/api/me/game/runs/{run_id}/answers/agenda", json={"skipped": True}, headers=youth)
    answer(client, youth, run_id, "couleur", "jaune")
    result = complete(client, youth, run_id).get_json()
    # Seul curseur de caractère connu : Réservé ↔ Sociable à 90, côté sociable.
    assert (result["archetype"]["id"], result["archetype"]["quality"]) == ("etincelle", "Sociable")
    assert result["progress"]["xp"] == 150 + 3 * 2
    assert result["xp_gained"] == 150
    assert [badge["id"] for badge in result["new_badges"]] == ["premiers_pas"]
    assert result["leveled_up"] is True
    assert answer(client, youth, run_id, "groupe", "b").status_code == 409
    assert client.post("/api/me/game/instruments/onboarding/runs", headers=youth).status_code == 409


def skip(client, headers, run_id, item_id):
    return client.put(
        f"/api/me/game/runs/{run_id}/answers/{item_id}", json={"skipped": True}, headers=headers
    )


def game_entry(client, headers, instrument_id):
    instruments = client.get("/api/me/game", headers=headers).get_json()["instruments"]
    return next(item for item in instruments if item["id"] == instrument_id)


def start_game(client, headers, instrument_id="fixture_questionnaire"):
    return client.post(f"/api/me/game/instruments/{instrument_id}/runs", headers=headers)


def test_the_first_quiz_questions_unlock_the_games_even_all_skipped(client, youth):
    # Le quiz de test débloque les jeux qui l'exigent après 2 questions vues (unlocks_after).
    assert game_entry(client, youth, "onboarding")["unlocks_after"] == 2
    assert game_entry(client, youth, "fixture_questionnaire")["unlocks_after"] is None
    assert start_game(client, youth).get_json()["error"]["code"] == "locked"

    run_id = start(client, youth)["run"]["id"]
    assert skip(client, youth, run_id, "agenda").status_code == 200
    refused = start_game(client, youth)
    assert refused.status_code == 409
    assert refused.get_json()["error"] == {
        "code": "locked",
        "message": "Ce jeu se débloque après les 2 premières questions du quiz d’arrivée.",
    }
    assert game_entry(client, youth, "fixture_questionnaire")["locked"] is True
    assert game_entry(client, youth, "fixture_span")["locked"] is True

    # Passer compte comme voir : deux questions passées suffisent.
    assert skip(client, youth, run_id, "groupe").status_code == 200
    assert game_entry(client, youth, "fixture_questionnaire")["locked"] is False
    assert game_entry(client, youth, "fixture_span")["locked"] is False
    assert start_game(client, youth).status_code == 201
    assert start_game(client, youth, "fixture_span").status_code == 201
    # Le quiz n'est ni fini ni en pause : l'arrivée y renvoie toujours, comme avant.
    status = client.get("/api/me/game", headers=youth).get_json()
    assert status["must_onboard"] is True
    assert next(item for item in status["instruments"] if item["id"] == "onboarding")["locked"] is False


def test_the_finished_quiz_unlocks_the_games_below_the_threshold(app, client, youth):
    app.extensions["game_catalog"].instruments["onboarding"]["unlocks_after"] = 5
    run_id = start(client, youth)["run"]["id"]
    for item_id, value in [("couleur", "jaune"), ("groupe", "a"), ("scooter", "b")]:
        assert answer(client, youth, run_id, item_id, value).status_code == 200
    assert skip(client, youth, run_id, "agenda").status_code == 200
    refused = start_game(client, youth)
    assert refused.get_json()["error"]["message"] == (
        "Ce jeu se débloque après les 5 premières questions du quiz d’arrivée."
    )
    # 4 questions vues sur les 5 du seuil, mais le quiz est terminé : les jeux sont débloqués.
    assert complete(client, youth, run_id).status_code == 200
    assert game_entry(client, youth, "fixture_questionnaire")["locked"] is False
    assert start_game(client, youth).status_code == 201


def test_without_a_threshold_only_the_finished_quiz_unlocks_the_games(app, client, youth):
    del app.extensions["game_catalog"].instruments["onboarding"]["unlocks_after"]
    assert game_entry(client, youth, "onboarding")["unlocks_after"] is None
    run_id = start(client, youth)["run"]["id"]
    assert start(client, youth)["instrument"]["unlocks_after"] is None
    for item_id, value in [
        ("couleur", "jaune"), ("passion", {"text": "Skate"}), ("groupe", "c"), ("scooter", "a"), ("agenda", 4),
    ]:
        assert answer(client, youth, run_id, item_id, value).status_code == 200
    refused = start_game(client, youth)
    assert refused.status_code == 409
    assert refused.get_json()["error"]["message"] == "Ce jeu se débloque après le quiz d'arrivée."
    assert game_entry(client, youth, "fixture_questionnaire")["locked"] is True
    assert complete(client, youth, run_id).status_code == 200
    assert game_entry(client, youth, "fixture_questionnaire")["locked"] is False
    assert start_game(client, youth).status_code == 201


def test_a_one_question_threshold_reads_well(app, client, youth):
    app.extensions["game_catalog"].instruments["onboarding"]["unlocks_after"] = 1
    start(client, youth)
    assert start_game(client, youth).get_json()["error"]["message"] == (
        "Ce jeu se débloque après la première question du quiz d’arrivée."
    )


def test_run_payload_tells_the_player_the_threshold(client, youth):
    run_id = start(client, youth)["run"]["id"]
    assert start(client, youth)["instrument"]["unlocks_after"] == 2
    for item_id in ("agenda", "groupe"):
        skip(client, youth, run_id, item_id)
    assert start(client, youth, "fixture_span")["instrument"]["unlocks_after"] is None
    assert start(client, youth, "fixture_questionnaire")["instrument"]["unlocks_after"] is None


def test_a_first_mini_game_before_the_end_of_the_quiz_earns_its_badge(client, youth):
    # « Dans le jeu » : terminer un premier mini-jeu. Le quiz n'en est pas un (il ne le donne pas
    # seul, voir plus haut), et les mini-jeux se jouent dès ses premières questions.
    run_id = start(client, youth)["run"]["id"]
    for item_id in ("agenda", "groupe"):
        assert skip(client, youth, run_id, item_id).status_code == 200
    game_id = start(client, youth, "fixture_questionnaire")["run"]["id"]
    for item_id in ("e1", "e2", "c1"):
        assert answer(client, youth, game_id, item_id, 4).status_code == 200
    result = complete(client, youth, game_id).get_json()
    assert [badge["id"] for badge in result["new_badges"]] == ["joueur"]
    badges = client.get("/api/me/game", headers=youth).get_json()["progress"]["badges"]
    assert {badge["id"]: badge["earned"] for badge in badges}["joueur"] is True


def test_psychologist_sees_cursors_as_percentages(client, youth, psychologist):
    run_id, _ = finish_onboarding(client, youth)
    target = youth_id(client, youth)
    base = f"/api/backoffice/youths/{target}/game"

    assert client.get(base, headers=youth).status_code == 403
    assert client.get(f"{base}/runs/{run_id}", headers=youth).status_code == 403
    other = register(client, "Noa")
    other_run = start(client, other)["run"]["id"]
    assert client.get(f"{base}/runs/{other_run}", headers=psychologist).status_code == 404

    overview = client.get(base, headers=psychologist).get_json()
    assert cursor(overview, "extraversion")["headline"] == {"percent": 90, "label": "Réservé"}
    assert cursor(overview, "riasec_r")["headline"] == {
        "percent": 95, "label": "Intérêt manuel et technique"
    }


def test_questionnaire_outweighs_quiz_and_keeps_raw_scores(client, youth, psychologist):
    finish_onboarding(client, youth)
    run_id = start(client, youth, "fixture_questionnaire")["run"]["id"]
    for item_id, value in [("e1", 5), ("e2", 1), ("c1", 4)]:
        answer(client, youth, run_id, item_id, value, response_ms=1500)
    assert complete(client, youth, run_id).status_code == 200

    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    overview = client.get(base, headers=psychologist).get_json()
    extraversion = cursor(overview, "extraversion")
    # Quiz 10 (poids 0,5) et deux items validés à 100 (poids 1) : (5 + 200) / 2,5.
    assert extraversion["value"] == 82.0
    assert extraversion["by_tier"]["adapted"]["value"] == 10.0
    assert extraversion["by_tier"]["validated"]["value"] == 100.0

    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    assert detail["run"]["metrics"]["scales"]["extraversion"] == {
        "n": 2, "raw_sum": 10, "raw_min": 2, "raw_max": 10, "percent": 100.0
    }
    row = detail["answers"][1]
    assert row["prompt"] == "Je reste plutôt en retrait."
    assert row["answer_label"] == "Pas du tout"
    assert row["response_ms"] == 1500
    assert row["source"]["original"] == "Keep in the background."
    assert row["source"]["source"]["citation"].startswith("Exemple")
    assert row["signals"][0]["value"] == 100

    trail = client.get(f"{base}/traits/extraversion", headers=psychologist).get_json()
    assert len(trail["signals"]) == 3
    assert {signal["tier"] for signal in trail["signals"]} == {"adapted", "validated"}


def test_performance_score_is_recomputed_by_the_server(client, youth, psychologist):
    finish_onboarding(client, youth)
    run_id = start(client, youth, "fixture_span")["run"]["id"]
    assert complete(client, youth, run_id, trials=[]).status_code == 400
    trials = [
        {"sequence": [1, 2], "response": [1, 2], "rt_ms": 900},
        {"sequence": [1, 2, 3, 4], "response": [1, 2, 3, 4], "rt_ms": 1800},
        {"sequence": [1, 2, 3, 4, 5], "response": [1, 2, 3, 5, 4], "rt_ms": 2000, "correct": True},
    ]
    result = complete(client, youth, run_id, trials=trials).get_json()
    assert result["metrics"]["span"] == 4
    assert result["metrics"]["correct"] == 2

    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    assert [row["answer_label"] for row in detail["answers"]] == ["Exact", "Exact", "Différent"]
    assert detail["run_signals"][0]["trait"] == "working_memory"
    assert detail["run_signals"][0]["value"] == 60.0


def test_validated_talents_feed_cursors_and_xp(app, client, youth, psychologist):
    target = youth_id(client, youth)
    with app.app_context():
        import uuid

        user_id = uuid.UUID(target)
        conversation = Conversation(youth_id=user_id, transcript_key="k")
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Skill(
                youth_id=user_id,
                conversation_id=conversation.id,
                source_message_id="m1",
                name="Réparer",
                name_key="reparer",
                category="savoir_faire",
                source_quote="je répare",
                status=SkillStatus.VALIDATED,
            )
        )
        db.session.commit()
    overview = client.get(f"/api/backoffice/youths/{target}/game", headers=psychologist).get_json()
    assert cursor(overview, "riasec_r")["value"] == 85
    assert cursor(overview, "riasec_r")["confidence"] == "low"
    assert overview["progress"]["xp"] == 25
    trail = client.get(
        f"/api/backoffice/youths/{target}/game/traits/riasec_r", headers=psychologist
    ).get_json()
    assert trail["signals"][0]["prompt"] == "Réparer"
    assert trail["signals"][0]["answer"] == "je répare"


def test_sheet_shows_facts_and_psychologist_sees_every_change(client, youth, psychologist):
    run_id, _ = finish_onboarding(client, youth)
    sheet = client.get("/api/me/game/sheet", headers=youth).get_json()
    assert {fact["label"]: fact["value"] for fact in sheet["facts"]} == {
        "Couleur préférée": "Jaune", "Passion": "Jeux vidéo"
    }
    # Organisé à 100 s'écarte plus du milieu que Réservé à 10.
    assert sheet["identity"]["archetype"]["id"] == "charpente"
    groups = {group["id"]: group["traits"] for group in sheet["trait_groups"]}
    assert groups["personality"][0]["label"] == "Réservé·e"
    assert all(trait["value"] >= 50 for trait in groups["interests"])
    assert next(a for a in sheet["attributes"] if a["id"] == "adresse")["score"] == 19
    assert next(a for a in sheet["attributes"] if a["id"] == "logique")["score"] is None

    edited = client.patch(
        "/api/me/game/facts/passion", json={"value": "Le skate"}, headers=youth
    ).get_json()
    assert edited["fact"]["edited"] is True
    client.patch("/api/me/game/facts/couleur_preferee", json={"hidden": True}, headers=youth)
    client.put(
        "/api/me/game/traits/extraversion/feedback", json={"verdict": "disagree"}, headers=youth
    )

    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    overview = client.get(base, headers=psychologist).get_json()
    facts = {fact["key"]: fact for fact in overview["facts"]}
    assert facts["passion"]["original_value"] == "Jeux vidéo"
    assert facts["passion"]["value"] == "Le skate" and facts["passion"]["edited"] is True
    assert facts["couleur_preferee"]["hidden"] is True
    assert facts["couleur_preferee"]["value"] == "Jaune"
    assert cursor(overview, "extraversion")["verdict"] == "disagree"
    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    color = next(row for row in detail["answers"] if row["item_id"] == "couleur")
    assert color["hidden_by_youth"] is True and color["answer_label"] == "Jaune"


def test_replaying_does_not_erase_a_youth_edit(client, youth):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "couleur", "jaune")
    client.patch("/api/me/game/facts/couleur_preferee", json={"value": "Vert"}, headers=youth)
    answer(client, youth, run_id, "couleur", "bleu")
    facts = client.get("/api/me/game/sheet", headers=youth).get_json()["facts"]
    assert facts[0]["value"] == "Vert"
    assert facts[0]["original_value"] == "Bleu"


def test_levels_grow_progressively():
    assert [level_floor(n) for n in (1, 2, 3, 4)] == [0, 100, 225, 375]
    assert level_for(0) == 1 and level_for(99) == 1 and level_for(100) == 2 and level_for(375) == 4


def test_demo_data_covers_every_instrument(app, client, youth, psychologist):
    target = youth_id(client, youth)
    with app.app_context():
        import uuid

        user = db.session.get(User, uuid.UUID(target))
        seed_youth_game(user, {"bias": {"extraversion": 20, "riasec_r": 90}, "facts": {"passion": "Skate"}})
    overview = client.get(f"/api/backoffice/youths/{target}/game", headers=psychologist).get_json()
    assert len(overview["runs"]) == 3 and all(r["status"] == "completed" for r in overview["runs"])
    assert cursor(overview, "extraversion")["value"] < 50
    assert client.get("/api/me/game/sheet", headers=youth).get_json()["facts"]


def test_catalog_rejects_unknown_trait(tmp_path):
    folder = tmp_path / "instruments"
    folder.mkdir()
    (folder / "bad.json").write_text(
        '{"id":"bad","version":1,"kind":"quiz","tier":"custom","title":"t","tagline":"t",'
        '"icon":"i","duration_min":1,"xp":1,"items":[{"id":"q","type":"choice","prompt":"?",'
        '"options":[{"id":"a","label":"A","signals":[{"trait":"nope","value":1}]},'
        '{"id":"b","label":"B"}]}]}',
        encoding="utf-8",
    )
    with pytest.raises(ContentError):
        Catalog(overlays=[tmp_path])


def overlay_instrument(tmp_path, name: str, **changes) -> Path:
    """Copie d'un instrument de test, modifiée, dans un dossier de contenu qui l'emporte."""
    data = json.loads((FIXTURES / "instruments" / f"{name}.json").read_text(encoding="utf-8"))
    data.update(changes)
    folder = tmp_path / "instruments"
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("value", [1, 5])
def test_catalog_accepts_a_threshold_within_the_questions(tmp_path, value):
    catalog = Catalog(overlays=[FIXTURES, overlay_instrument(tmp_path, "onboarding", unlocks_after=value)])
    assert catalog.instruments["onboarding"]["unlocks_after"] == value


@pytest.mark.parametrize(
    "value",
    [0, -1, 6, 2.5, "2", True, None, [2]],
    ids=["zero", "negative", "more_than_items", "decimal", "text", "boolean", "null", "list"],
)
def test_catalog_rejects_a_threshold_outside_the_questions(tmp_path, value):
    folder = overlay_instrument(tmp_path, "onboarding", unlocks_after=value)
    with pytest.raises(ContentError, match=r"onboarding : « unlocks_after » doit être un nombre entier"):
        Catalog(overlays=[FIXTURES, folder])


def test_catalog_rejects_a_threshold_on_a_game_without_questions(tmp_path):
    folder = overlay_instrument(tmp_path, "fixture_span", unlocks_after=1)
    with pytest.raises(ContentError, match=r"fixture_span : « unlocks_after » demande"):
        Catalog(overlays=[FIXTURES, folder])

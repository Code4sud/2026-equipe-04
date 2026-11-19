from __future__ import annotations

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


def share(client, headers, value=True):
    response = client.patch(
        "/api/me/game/consent", json={"share_game_results": value}, headers=headers
    )
    assert response.status_code == 200


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
    assert status["share_game_results"] is None

    run_id = start(client, youth)["run"]["id"]
    assert client.post(f"/api/me/game/runs/{run_id}/pause", headers=youth).status_code == 200
    assert client.get("/api/me/game", headers=youth).get_json()["must_onboard"] is False

    resumed = start(client, youth)
    assert resumed["run"]["id"] == run_id
    assert resumed["run"]["paused_at"] is None
    assert client.get("/api/me/game", headers=youth).get_json()["must_onboard"] is True


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


def test_completion_needs_enough_answers_and_gives_clan_and_xp(client, youth):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "groupe", "a")
    assert complete(client, youth, run_id).status_code == 409

    answer(client, youth, run_id, "scooter", "a")
    client.put(f"/api/me/game/runs/{run_id}/answers/agenda", json={"skipped": True}, headers=youth)
    answer(client, youth, run_id, "couleur", "jaune")
    result = complete(client, youth, run_id).get_json()
    assert result["clan"]["id"] == "batisseurs"
    assert result["progress"]["xp"] == 150 + 3 * 2
    assert result["xp_gained"] == 150
    assert [badge["id"] for badge in result["new_badges"]] == ["premiers_pas"]
    assert result["leveled_up"] is True
    assert answer(client, youth, run_id, "groupe", "b").status_code == 409
    assert client.post("/api/me/game/instruments/onboarding/runs", headers=youth).status_code == 409


def test_games_unlock_after_onboarding(client, youth):
    response = client.post("/api/me/game/instruments/fixture_questionnaire/runs", headers=youth)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "locked"
    finish_onboarding(client, youth)
    start(client, youth, "fixture_questionnaire")


def test_psychologist_only_sees_results_when_shared(client, youth, psychologist):
    run_id, _ = finish_onboarding(client, youth)
    target = youth_id(client, youth)
    base = f"/api/backoffice/youths/{target}/game"

    overview = client.get(base, headers=psychologist).get_json()
    assert overview == {
        "youth": overview["youth"], "shared": False, "asked": False, "share_updated_at": None
    }
    assert client.get(f"{base}/runs/{run_id}", headers=psychologist).status_code == 403
    assert client.get(f"{base}/traits/extraversion", headers=psychologist).status_code == 403
    assert client.get(base, headers=youth).status_code == 403

    share(client, youth)
    overview = client.get(base, headers=psychologist).get_json()
    assert overview["shared"] is True
    assert cursor(overview, "extraversion")["headline"] == {"percent": 90, "label": "Réservé"}
    assert cursor(overview, "riasec_r")["headline"] == {
        "percent": 95, "label": "Intérêt manuel et technique"
    }


def test_questionnaire_outweighs_quiz_and_keeps_raw_scores(client, youth, psychologist):
    finish_onboarding(client, youth)
    share(client, youth)
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
    share(client, youth)
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
    share(client, youth)
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


def test_sheet_shows_facts_positive_view_and_lets_youth_decide(client, youth, psychologist):
    run_id, _ = finish_onboarding(client, youth)
    share(client, youth)
    sheet = client.get("/api/me/game/sheet", headers=youth).get_json()
    assert {fact["label"]: fact["value"] for fact in sheet["facts"]} == {
        "Couleur préférée": "Jaune", "Passion": "Jeux vidéo"
    }
    assert sheet["identity"]["clan"]["id"] == "batisseurs"
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
    assert [fact["key"] for fact in overview["facts"]] == ["passion"]
    assert cursor(overview, "extraversion")["verdict"] == "disagree"
    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    color = next(row for row in detail["answers"] if row["item_id"] == "couleur")
    assert color["hidden_by_youth"] is True and color["answer_label"] is None


def test_replaying_does_not_erase_a_youth_edit(client, youth):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "couleur", "jaune")
    client.patch("/api/me/game/facts/couleur_preferee", json={"value": "Vert"}, headers=youth)
    answer(client, youth, run_id, "couleur", "bleu")
    facts = client.get("/api/me/game/sheet", headers=youth).get_json()["facts"]
    assert facts[0]["value"] == "Vert"


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

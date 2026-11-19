"""Fiche d'aventurier : attributs à découvrir, badges et titres de niveau."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

from app.game.catalog import KINDS, Catalog
from app.game.discovery import instrument_traits, reveal_with

FIXTURES = Path(__file__).parent / "fixtures" / "game"
BADGE_RULES = {"completed", "completed_count", "talents", "facts", "level"}


def fixture_catalog() -> Catalog:
    catalog = Catalog(overlays=[FIXTURES])
    keep = {"onboarding", "fixture_questionnaire", "fixture_span"}
    catalog.instruments = {k: v for k, v in catalog.instruments.items() if k in keep}
    return catalog


@pytest.fixture(autouse=True)
def use_fixture_catalog(app):
    app.extensions["game_catalog"] = fixture_catalog()


def sheet_attributes(client, headers) -> dict[str, dict]:
    sheet = client.get("/api/me/game/sheet", headers=headers).get_json()
    return {attribute["id"]: attribute for attribute in sheet["attributes"]}


def play_onboarding(client, headers) -> None:
    run_id = client.post("/api/me/game/instruments/onboarding/runs", headers=headers).get_json()
    run_id = run_id["run"]["id"]
    for item_id, value in [("couleur", "jaune"), ("groupe", "c"), ("scooter", "a"), ("agenda", 5)]:
        response = client.put(
            f"/api/me/game/runs/{run_id}/answers/{item_id}", json={"value": value}, headers=headers
        )
        assert response.status_code == 200
    assert client.post(f"/api/me/game/runs/{run_id}/complete", headers=headers).status_code == 200


def test_instrument_traits_cover_choices_likert_and_performance():
    catalog = fixture_catalog()
    assert instrument_traits(catalog.instruments["fixture_span"]) == {"working_memory"}
    assert instrument_traits(catalog.instruments["fixture_questionnaire"]) == {
        "extraversion", "conscientiousness"
    }
    assert {"riasec_r", "riasec_i", "conscientiousness"} <= instrument_traits(
        catalog.instruments["onboarding"]
    )


def test_reveal_prefers_a_new_game_then_a_replay_and_skips_closed_ones():
    catalog = fixture_catalog()
    first = reveal_with(catalog, {"conscientiousness"}, set())
    assert first == {"id": "onboarding", "title": "Quiz d'arrivée (fictif)", "kind": "quiz"}
    assert reveal_with(catalog, {"conscientiousness"}, {"onboarding"})["id"] == "fixture_questionnaire"
    replay = reveal_with(catalog, {"conscientiousness"}, {"onboarding", "fixture_questionnaire"})
    assert replay["id"] == "fixture_questionnaire"
    assert reveal_with(catalog, {"riasec_s"}, {"onboarding"}) is None
    assert reveal_with(catalog, {"riasec_a", "openness"}, set()) is None


def test_sheet_says_which_game_reveals_an_unknown_attribute(client, youth):
    before = sheet_attributes(client, youth)
    assert all(attribute["score"] is None for attribute in before.values())
    assert before["logique"]["reveal_with"]["id"] == "onboarding"
    assert before["creativite"]["reveal_with"] is None

    play_onboarding(client, youth)
    after = sheet_attributes(client, youth)
    assert after["adresse"]["score"] == 19 and after["adresse"]["reveal_with"] is None
    assert after["logique"]["score"] is None
    assert after["logique"]["reveal_with"] == {
        "id": "fixture_span", "title": "Série fictive", "kind": "performance"
    }
    # Le quiz d'arrivée ne se rejoue pas : rien d'autre ne peut révéler l'empathie ici.
    assert after["empathie"]["reveal_with"] is None


def test_every_badge_can_be_earned():
    catalog = Catalog()
    for badge in catalog.sheet["badges"]:
        rule = badge["rule"]
        assert rule["type"] in BADGE_RULES, badge["id"]
        if rule["type"] == "completed_count" and "kind" in rule:
            assert rule["kind"] in KINDS, badge["id"]
        if rule["type"] != "completed":
            assert rule["count"] >= 1, badge["id"]


def test_level_titles_are_unique_and_never_an_archetype_name():
    def plain(text: str) -> str:
        text = unicodedata.normalize("NFKD", text).lower()
        return "".join(c for c in text if c.isalpha())

    def words(text: str) -> set[str]:
        return {plain(word) for word in re.split(r"[\s’'·-]+", text) if plain(word)}

    catalog = Catalog()
    titles = [plain(title) for title in catalog.sheet["level_titles"]]
    assert len(set(titles)) == len(titles)
    # Le nom sans son article : « L’Étincelle » donne « etincelle ». Mot à mot, pour que « Le Vent »
    # n'attrape pas « Aventurier·ère ».
    names = {plain(re.split(r"[\s’']+", archetype["name"])[-1]) for archetype in catalog.archetypes}
    assert len(names) == len(catalog.archetypes)
    assert not [title for title in catalog.sheet["level_titles"] if words(title) & names]

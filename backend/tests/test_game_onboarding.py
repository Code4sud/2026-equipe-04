"""Quiz d'arrivée réellement livré : structure, couverture des curseurs, sources et partie complète."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from conftest import register

from app.game.catalog import Catalog

CONTENT = Path(__file__).resolve().parents[1] / "app" / "game" / "content"
QUIZ_SOURCES = {"goldberg_big_five_markers", "ipip_neo", "holland_riasec"}
IPIP_SOURCES = {"goldberg_big_five_markers", "ipip_neo"}
BIG_FIVE = ["extraversion", "agreeableness", "conscientiousness", "emotional_stability", "openness"]
INTERESTS = ["riasec_r", "riasec_i", "riasec_a", "riasec_s", "riasec_e", "riasec_c", "interest_digital"]
REQUIRED_FACTS = {"couleur_preferee", "passion"}
DASHES = ("—", "–")


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


@pytest.fixture(scope="module")
def quiz(catalog):
    return catalog.instruments["onboarding"]


def is_scored(item: dict) -> bool:
    return item["type"] == "likert" or any(o.get("signals") for o in item.get("options", []))


def signal_values(items: list[dict]) -> dict[str, list[list[float]]]:
    """Pour chaque curseur, les valeurs proposées par chaque question qui le touche."""
    per_trait: dict[str, list[list[float]]] = defaultdict(list)
    for item in items:
        values: dict[str, list[float]] = defaultdict(list)
        for option in item.get("options", []):
            for signal in option.get("signals", []):
                values[signal["trait"]].append(signal["value"])
        for trait, found in values.items():
            per_trait[trait].append(found)
    return per_trait


def test_quiz_settings_match_the_onboarding_contract(quiz):
    assert quiz["kind"] == "quiz" and quiz["tier"] == "adapted"
    assert quiz["order"] == 0 and quiz["replayable"] is False
    assert not quiz.get("requires")
    assert 150 <= quiz["xp"] <= 250
    assert 8 <= quiz["duration_min"] <= 12
    assert 25 <= quiz["min_answers"] <= 35, "Passer une question doit rester vraiment possible."
    assert set(quiz["source_ids"]) == QUIZ_SOURCES


def test_fifty_items_in_five_chapters_of_ten(quiz):
    items = quiz["items"]
    assert len(items) == 50
    chapters = quiz["chapters"]
    assert len(chapters) == 5
    for chapter in chapters:
        assert chapter["title"] and chapter["intro"]
        assert sum(1 for item in items if item.get("chapter") == chapter["id"]) == 10, chapter["id"]
    # Les chapitres se suivent : une journée puis le week-end, sans retour en arrière.
    order = [chapter["id"] for chapter in chapters]
    positions = [order.index(item["chapter"]) for item in items]
    assert positions == sorted(positions)


def test_facts_have_stable_unique_keys_and_no_scoring(quiz):
    facts = [item for item in quiz["items"] if "fact" in item]
    keys = [item["fact"] for item in facts]
    assert 10 <= len(facts) <= 14
    assert len(keys) == len(set(keys))
    assert REQUIRED_FACTS <= set(keys)
    for item in facts:
        assert item["fact_label"]
        assert not is_scored(item), f"{item['id']} : un détail de fiche ne bouge aucun curseur"
        assert "source" not in item
    colour = next(item for item in facts if item["fact"] == "couleur_preferee")
    assert all(option.get("color", "").startswith("#") for option in colour["options"])


def test_every_scored_item_is_a_sourced_situation(quiz, catalog):
    scored = [item for item in quiz["items"] if is_scored(item)]
    assert 34 <= len(scored) <= 42
    for item in scored:
        source = item.get("source") or {}
        assert source.get("source_id") in QUIZ_SOURCES, item["id"]
        assert source["source_id"] in catalog.sources
        assert source.get("ref") and source.get("original"), item["id"]
        assert source.get("relation") == "inspired", item["id"]
        assert 3 <= len(item["options"]) <= 4, item["id"]
        assert all(option.get("signals") for option in item["options"]), item["id"]


# Facteur visé par un item IPIP (début de `ref`) et types de Holland cités (`original`).
IPIP_FACTORS = {
    "Extraversion": "extraversion",
    "Agréabilité": "agreeableness",
    "Conscienciosité": "conscientiousness",
    "Stabilité émotionnelle": "emotional_stability",
    "Intellect ou imagination": "openness",
    "Ouverture": "openness",
}
HOLLAND_TYPES = {
    "Realistic": "riasec_r", "Investigative": "riasec_i", "Artistic": "riasec_a",
    "Social": "riasec_s", "Enterprising": "riasec_e", "Conventional": "riasec_c",
}


def test_every_option_scores_what_its_source_cites(quiz):
    for item in quiz["items"]:
        source = item.get("source")
        if not source:
            continue
        for option in item["options"]:
            where = f"{item['id']}/{option['id']}"
            traits = {signal["trait"] for signal in option["signals"]}
            if source["source_id"] in IPIP_SOURCES:
                assert IPIP_FACTORS[source["ref"].split(",")[0]] in traits, where
                continue
            cited = {HOLLAND_TYPES[name] for name in source["original"].split(" / ")}
            # Seul l'indicateur maison d'intérêt numérique s'ajoute aux types cités.
            assert traits <= cited | {"interest_digital"}, where
            if len(cited) == 2:
                # Dilemme : chaque option, la mixte comprise, situe le jeune sur les deux types.
                assert cited <= traits, where


def test_holland_source_says_how_the_clan_is_chosen(catalog):
    # Le clan suit le curseur RIASEC le plus haut, talents validés compris (service.clan_for).
    assert "tous jeux et talents validés confondus" in catalog.sources["holland_riasec"]["note"]


def test_the_art_exhibition_cites_an_ipip_item_about_art(quiz):
    # Aucun des 50 marqueurs de Goldberg (1992) ne parle d'art : l'expo cite la facette O2 de l'IPIP-NEO.
    expo = next(item for item in quiz["items"] if item["id"] == "weekend_expo")
    assert "art" in expo["prompt"]
    assert (expo["source"]["source_id"], expo["source"]["original"]) == (
        "ipip_neo", "Do not enjoy going to art museums."
    )
    cited = [item["id"] for item in quiz["items"] if (item.get("source") or {}).get("source_id") == "ipip_neo"]
    assert cited == ["weekend_expo"]


# Options écrites après la version 1 : un nouveau sens prend un nouvel identifiant, pour qu'une
# partie en cours ne recompte pas l'ancienne réponse « c » sous l'option mixte.
REWRITTEN_OPTIONS = {"route_sortie": "c", "soir_telephone": "c"}


def test_rewritten_options_never_reuse_an_old_id(quiz):
    items = {item["id"]: item for item in quiz["items"]}
    for item_id, retired in REWRITTEN_OPTIONS.items():
        assert [option["id"] for option in items[item_id]["options"]] == ["a", "b", "d"], item_id
        assert retired not in {option["id"] for option in items[item_id]["options"]}


@pytest.mark.parametrize(
    ("traits", "minimum"), [(BIG_FIVE, 5), (INTERESTS, 4)], ids=["big_five", "interests"]
)
def test_every_trait_is_covered_by_enough_items(quiz, traits, minimum):
    per_trait = signal_values(quiz["items"])
    for trait in traits:
        assert len(per_trait[trait]) >= minimum, f"{trait} : {len(per_trait[trait])} questions"


def test_both_poles_are_reachable_for_every_trait(quiz):
    per_trait = signal_values(quiz["items"])
    for trait in BIG_FIVE + INTERESTS:
        values = [value for found in per_trait[trait] for value in found]
        assert min(values) < 40 and max(values) > 60, trait
    # Les grands traits se jouent question par question : chacune propose les deux côtés.
    for trait in BIG_FIVE:
        spanning = [found for found in per_trait[trait] if min(found) < 40 and max(found) > 60]
        assert len(spanning) >= 5, trait


def test_quiz_never_touches_cognitive_cursors(quiz, catalog):
    cognitive = {t for t, trait in catalog.traits.items() if trait["group"] == "cognitive"}
    assert not cognitive & set(signal_values(quiz["items"]))


def test_youth_facing_quiz_text_has_no_em_dash(catalog, quiz):
    public = catalog.public_instrument(quiz)
    texts = [public["title"], public["tagline"], public.get("intro", ""), public.get("outro", "")]
    texts += [chapter["title"] + chapter["intro"] for chapter in public["chapters"]]
    for item in public["items"]:
        texts.append(item["prompt"])
        texts += [option["label"] for option in item.get("options", [])]
    assert not [text for text in texts if any(dash in text for dash in DASHES)]


def test_quiz_sources_file_lists_the_verified_references():
    data = json.loads((CONTENT / "sources" / "quiz.json").read_text(encoding="utf-8"))
    sources = {source["id"]: source for source in data["sources"]}
    assert set(sources) == QUIZ_SOURCES
    for source in sources.values():
        for field in ("title", "citation", "url", "licence", "adaptation"):
            assert source.get(field), f"{source['id']} : {field}"
        assert source["validated"] is False
        assert source["url"].startswith("https://")
    assert "10.1037/1040-3590.4.1.26" in sources["goldberg_big_five_markers"]["citation"]
    for source_id in IPIP_SOURCES:
        assert "domaine public" in sources[source_id]["licence"], source_id
    assert sources["ipip_neo"]["citation"].startswith("Goldberg, L. R. (1999)")
    assert "Making vocational choices" in sources["holland_riasec"]["citation"]


# --- Partie complète avec le vrai contenu ---


def first_answer(item: dict):
    if item["type"] == "text":
        return {"text": "Le skate"}
    return item["options"][0]["id"]


def play(client, headers, answers: int):
    """Répond aux `answers` premières questions avec la première option, passe les suivantes."""
    started = client.post("/api/me/game/instruments/onboarding/runs", headers=headers).get_json()
    run_id = started["run"]["id"]
    items = started["instrument"]["items"]
    for position, item in enumerate(items):
        body = {"value": first_answer(item)} if position < answers else {"skipped": True}
        response = client.put(
            f"/api/me/game/runs/{run_id}/answers/{item['id']}", json=body, headers=headers
        )
        assert response.status_code == 200, response.get_json()
    return run_id, items


def test_public_quiz_hides_facts_traits_and_sources(client):
    youth = register(client)
    instrument = client.post("/api/me/game/instruments/onboarding/runs", headers=youth).get_json()["instrument"]
    text = json.dumps(instrument)
    for hidden in ("signals", "riasec", "source_id", "fact_label", "couleur_preferee", "scoring_note"):
        assert hidden not in text
    assert len(instrument["chapters"]) == 5 and instrument["min_answers"] == 30


def test_full_quiz_reveals_an_archetype_and_levels_up(client):
    youth = register(client)
    run_id, items = play(client, youth, answers=50)
    result = client.post(f"/api/me/game/runs/{run_id}/complete", headers=youth).get_json()
    assert result["archetype"]["name"] and result["archetype"]["quality"]
    assert result["previous_archetype"] is None
    assert len(result["highlights"]) == 3
    assert result["xp_gained"] == 200
    assert result["progress"]["xp"] == 200 + 2 * len(items)
    assert result["progress"]["level"] == 3 and result["leveled_up"] is True
    assert "premiers_pas" in {badge["id"] for badge in result["new_badges"]}

    sheet = client.get("/api/me/game/sheet", headers=youth).get_json()
    facts = {fact["key"]: fact["value"] for fact in sheet["facts"]}
    assert facts["couleur_preferee"] == "Rouge" and len(facts) == 12
    status = client.get("/api/me/game", headers=youth).get_json()
    assert status["must_onboard"] is False
    assert client.post("/api/me/game/instruments/onboarding/runs", headers=youth).status_code == 409


def test_skipping_is_allowed_down_to_the_minimum(client):
    youth = register(client)
    run_id, items = play(client, youth, answers=29)
    refused = client.post(f"/api/me/game/runs/{run_id}/complete", headers=youth)
    assert refused.status_code == 409
    assert refused.get_json()["error"]["code"] == "not_enough_answers"

    late = items[40]
    client.put(
        f"/api/me/game/runs/{run_id}/answers/{late['id']}",
        json={"value": first_answer(late)},
        headers=youth,
    )
    assert client.post(f"/api/me/game/runs/{run_id}/complete", headers=youth).status_code == 200

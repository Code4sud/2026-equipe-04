"""Questionnaires du hub : items fidèles aux sources, clés équilibrées, garde-fous, cotation."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
from test_game import answer, complete, finish_onboarding, start, youth_id
from test_game_content import normalize, sensitive_patterns

from app.game.catalog import Catalog

FIXTURES = Path(__file__).parent / "fixtures" / "game"
MINE = ("ton_style", "miroir", "grand_tri")
MY_SOURCES = ("ipip_mini_ipip", "mccrae_costa_1989")

# Clé publiée du Mini-IPIP (https://ipip.ori.org/MiniIPIPKey.htm), dans l'ordre de passation
# de Donnellan et al. (2006). N = Neuroticisme, I = Intellect/Imagination.
MINI_IPIP = {
    1: ("E", "+", "Am the life of the party."),
    2: ("A", "+", "Sympathize with others' feelings."),
    3: ("C", "+", "Get chores done right away."),
    4: ("N", "+", "Have frequent mood swings."),
    5: ("I", "+", "Have a vivid imagination."),
    6: ("E", "-", "Don't talk a lot."),
    7: ("A", "-", "Am not interested in other people's problems."),
    8: ("C", "-", "Often forget to put things back in their proper place."),
    9: ("N", "-", "Am relaxed most of the time."),
    10: ("I", "-", "Am not interested in abstract ideas."),
    11: ("E", "+", "Talk to a lot of different people at parties."),
    12: ("A", "+", "Feel others' emotions."),
    13: ("C", "+", "Like order."),
    14: ("N", "+", "Get upset easily."),
    15: ("I", "-", "Have difficulty understanding abstract ideas."),
    16: ("E", "-", "Keep in the background."),
    17: ("A", "-", "Am not really interested in others."),
    18: ("C", "-", "Make a mess of things."),
    19: ("N", "-", "Seldom feel blue."),
    20: ("I", "-", "Do not have a good imagination."),
}
FACTOR_TO_TRAIT = {
    "E": "extraversion",
    "A": "agreeableness",
    "C": "conscientiousness",
    "N": "emotional_stability",
    "I": "openness",
}
# Curseur RIASEC → lettre et nom anglais du type de Holland (Holland, 1997).
HOLLAND_TYPES = {
    "riasec_r": ("R", "Realistic"),
    "riasec_i": ("I", "Investigative"),
    "riasec_a": ("A", "Artistic"),
    "riasec_s": ("S", "Social"),
    "riasec_e": ("E", "Enterprising"),
    "riasec_c": ("C", "Conventional"),
}
MOOD_WORDS = re.compile(r"humeur|triste|cafard|deprim|blues|moral\b")
TYPE_CODE = re.compile(r"\b[EI][NS][FT][JP]\b")


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def items_of(catalog, instrument_id):
    return catalog.instruments[instrument_id]["items"]


def public_texts(catalog, instrument_id):
    public = catalog.public_instrument(catalog.instruments[instrument_id])
    yield from (public.get(field) or "" for field in ("title", "tagline", "intro", "outro", "source_note"))
    for chapter in public.get("chapters", []):
        yield chapter["title"]
        yield chapter.get("intro", "")
    for item in public["items"]:
        yield item["prompt"]
        yield item.get("hint", "")
        yield from (option["label"] for option in item.get("options", []))
    yield from (public.get("scale") or {}).get("labels", [])


@pytest.mark.parametrize("instrument_id", MINE)
def test_instruments_are_complete_and_unlock_after_the_quiz(catalog, instrument_id):
    instrument = catalog.instruments[instrument_id]
    assert instrument["kind"] == "questionnaire"
    assert instrument["requires"] == ["onboarding"]
    assert instrument["replayable"] is True
    assert 60 <= instrument["xp"] <= 120
    assert 1 <= instrument["duration_min"] <= 10
    for field in ("title", "tagline", "icon", "intro", "outro", "source_note", "scoring_note"):
        assert instrument.get(field), f"{instrument_id} : {field}"
    assert instrument.get("min_answers", 0) <= len(instrument["items"])


def test_mirror_uses_the_published_mini_ipip_items_minus_mood_items(catalog):
    items = items_of(catalog, "miroir")
    assert len(items) == 18
    numbers = []
    for item in items:
        source = item["source"]
        number = int(source["ref"].split()[1])
        factor, published_key, original = MINI_IPIP[number]
        numbers.append(number)
        assert source["source_id"] == "ipip_mini_ipip"
        assert source["relation"] == "translated"
        assert source["original"] == original
        assert item["trait"] == FACTOR_TO_TRAIT[factor]
        # Le Neuroticisme est noté dans le sens Stabilité émotionnelle : clé inversée.
        expected = published_key if factor != "N" else {"+": "-", "-": "+"}[published_key]
        assert item["keyed"] == expected, item["id"]
    assert sorted(numbers) == [n for n in MINI_IPIP if n not in {4, 19}]


def test_mirror_keys_stay_balanced(catalog):
    items = items_of(catalog, "miroir")
    per_trait = Counter(item["trait"] for item in items)
    assert per_trait == {
        "extraversion": 4, "agreeableness": 4, "conscientiousness": 4, "openness": 4,
        "emotional_stability": 2,
    }
    for trait in per_trait:
        keys = {item["keyed"] for item in items if item["trait"] == trait}
        assert keys == {"+", "-"}, trait
    keys = Counter(item["keyed"] for item in items)
    assert abs(keys["+"] - keys["-"]) <= 2
    assert all(a["trait"] != b["trait"] for a, b in zip(items, items[1:]))


def test_mirror_stability_items_weigh_half_so_two_answers_stay_low(catalog):
    items = items_of(catalog, "miroir")
    weights = {item["id"]: item.get("weight", 1) for item in items}
    stability = {item["id"] for item in items if item["trait"] == "emotional_stability"}
    assert stability == {"ipip09", "ipip14"}
    assert {weights[item_id] for item_id in stability} == {0.5}
    assert {weight for item_id, weight in weights.items() if item_id not in stability} == {1}


def test_mirror_source_says_why_the_published_french_adaptation_is_not_used(catalog):
    note = catalog.sources["ipip_mini_ipip"]["note"]
    assert "Laverdière" in note and "https://doi.org/10.1016/j.erap.2019.100512" in note


def test_grand_tri_has_48_activities_alternating_the_six_types(catalog):
    instrument = catalog.instruments["grand_tri"]
    items = instrument["items"]
    assert len(items) == 48
    assert all(item["type"] == "likert" and item["keyed"] == "+" for item in items)
    assert Counter(item["trait"] for item in items) == {trait: 8 for trait in HOLLAND_TYPES}
    # Les six types reviennent toujours dans le même ordre : jamais deux fois le même d'affilée.
    assert [item["trait"] for item in items] == list(HOLLAND_TYPES) * 8
    assert len({item["id"] for item in items}) == len({item["prompt"] for item in items}) == 48
    assert Counter(item["chapter"] for item in items) == {"etape1": 16, "etape2": 16, "etape3": 16}
    scale = instrument["scale"]
    assert (scale["min"], scale["max"], len(scale["labels"])) == (1, 5, 5)


def test_grand_tri_activities_are_only_inspired_by_holland_types(catalog):
    instrument = catalog.instruments["grand_tri"]
    assert instrument["tier"] == "adapted"
    assert instrument["source_ids"] == ["holland_riasec"]
    for item in instrument["items"]:
        letter, name = HOLLAND_TYPES[item["trait"]]
        assert item["source"] == {
            "source_id": "holland_riasec", "ref": f"Type {letter}", "original": name, "relation": "inspired"
        }, item["id"]
    holland = catalog.sources["holland_riasec"]
    assert holland["validated"] is False
    assert "Grand Tri" in holland["licence"] and "Grand Tri" in holland["adaptation"]


def test_no_content_cites_the_riasec_markers_any_more(catalog):
    assert "iip_riasec_markers" not in catalog.sources
    for instrument in catalog.instruments.values():
        assert "iip_riasec_markers" not in instrument.get("source_ids", []), instrument["id"]
        for item in instrument.get("items", []):
            assert (item.get("source") or {}).get("source_id") != "iip_riasec_markers", item["id"]


def test_ton_style_is_a_balanced_custom_game_on_four_cursors(catalog):
    instrument = catalog.instruments["ton_style"]
    assert instrument["tier"] == "custom"
    items = instrument["items"]
    assert len(items) == 20
    traits = Counter()
    high_first = 0
    for item in items:
        assert item["type"] == "choice" and len(item["options"]) == 2
        signals = [option["signals"] for option in item["options"]]
        assert all(len(s) == 1 for s in signals)
        (first,), (second,) = signals
        assert first["trait"] == second["trait"]
        assert sorted([first["value"], second["value"]]) == [25, 75]
        traits[first["trait"]] += 1
        high_first += first["value"] > 50
        assert item["source"]["relation"] == "inspired"
    assert traits == {"extraversion": 5, "openness": 5, "agreeableness": 5, "conscientiousness": 5}
    assert high_first == 10


def test_every_translated_item_keeps_its_original(catalog):
    # Traduction maison d'un test validé : jamais présentée comme le test validé lui-même.
    translated = [i for i in catalog.instruments.values() if i["tier"] == "translated"]
    assert "miroir" in {instrument["id"] for instrument in translated}
    for instrument in translated:
        for item in instrument["items"]:
            source = item["source"]
            assert source["source_id"] in instrument["source_ids"]
            assert source["ref"] and source["original"].strip(), item["id"]
            assert source["relation"] == "translated"
            assert source["original"] != item["prompt"]


@pytest.mark.parametrize("source_id", MY_SOURCES)
def test_sources_document_licence_and_adaptation(catalog, source_id):
    source = catalog.sources[source_id]
    for field in ("title", "authors", "citation", "url", "licence", "adaptation", "note"):
        assert source.get(field), f"{source_id} : {field}"
    assert source["url"].startswith("https://")
    assert str(source["year"]) in source["citation"]
    assert "doi.org/10." in source["citation"]
    # Traduction maison ou simple inspiration : jamais présenté comme la version validée.
    assert source["validated"] is False


@pytest.mark.parametrize("instrument_id", MINE)
def test_youth_texts_respect_the_guardrails(catalog, instrument_id):
    patterns = sensitive_patterns()
    for text in public_texts(catalog, instrument_id):
        assert not TYPE_CODE.search(text), text
        clean = normalize(text)
        assert not MOOD_WORDS.search(clean), text
        for topic, regex in patterns:
            assert not regex.search(clean), f"[{topic}] {text}"


# --- Parcours complet par l'API ---


@pytest.fixture
def play_catalog(app):
    app.extensions["game_catalog"] = Catalog(overlays=[FIXTURES])


def play(client, headers, instrument_id, value):
    run_id = start(client, headers, instrument_id)["run"]["id"]
    for item in client.application.extensions["game_catalog"].instruments[instrument_id]["items"]:
        chosen = value(item) if callable(value) else value
        assert answer(client, headers, run_id, item["id"], chosen).status_code == 200
    response = complete(client, headers, run_id)
    assert response.status_code == 200, response.get_json()
    return run_id, response.get_json()


def test_mirror_is_locked_until_the_quiz_then_scores_each_scale(
    play_catalog, client, youth, psychologist
):
    response = client.post("/api/me/game/instruments/miroir/runs", headers=youth)
    assert response.status_code == 409
    finish_onboarding(client, youth)

    run_id, result = play(client, youth, "miroir", 5)
    # Les points par réponse arrivent pendant la partie, la fin de partie ajoute ceux du jeu.
    assert result["xp_gained"] == 80
    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    scales = detail["run"]["metrics"]["scales"]
    # « Tout à fait moi » partout : les clés inversées ramènent les échelles équilibrées à 50 %.
    assert scales["extraversion"]["percent"] == 50.0
    assert scales["emotional_stability"] == {
        "n": 2, "raw_sum": 6, "raw_min": 2, "raw_max": 10, "percent": 50.0
    }
    assert scales["openness"]["percent"] == 25.0
    first = detail["answers"][0]
    assert first["source"]["original"] == "Am the life of the party."
    assert first["source"]["source"]["licence"].startswith("Domaine public")
    assert first["answer_label"] == "Tout à fait moi"
    assert detail["instrument"]["tier_label"] == "Test validé, traduction maison non validée"
    # Deux items seulement : leur poids propre de 0,5 garde ce curseur en confiance faible.
    stability = client.get(f"{base}/traits/emotional_stability", headers=psychologist).get_json()
    assert [(row["weight"], row["tier"]) for row in stability["signals"]] == [(0.5, "translated")] * 2
    assert stability["cursor"]["confidence"] == "low"


def test_grand_tri_scores_each_type_as_work_inspired_by_holland(
    play_catalog, client, youth, psychologist
):
    finish_onboarding(client, youth)
    run_id, _ = play(client, youth, "grand_tri", lambda item: 5 if item["trait"] == "riasec_a" else 1)
    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    detail = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    scales = detail["run"]["metrics"]["scales"]
    assert scales["riasec_a"] == {"n": 8, "raw_sum": 40, "raw_min": 8, "raw_max": 40, "percent": 100.0}
    assert scales["riasec_r"]["percent"] == 0.0
    assert detail["instrument"]["tier_label"] == "Inspiré de travaux publiés, non validé"
    first = detail["answers"][0]["source"]
    assert (first["original"], first["relation"]) == ("Realistic", "inspired")
    assert first["source"]["citation"].startswith("Holland, J. L. (1997)")
    trail = client.get(f"{base}/traits/riasec_a", headers=psychologist).get_json()
    rows = [row for row in trail["signals"] if row["instrument_id"] == "grand_tri"]
    assert len(rows) == 8
    assert all((row["value"], row["weight"], row["tier"]) == (100, 1, "adapted") for row in rows)


def test_ton_style_feeds_big_five_cursors_with_half_weight(
    play_catalog, client, youth, psychologist
):
    finish_onboarding(client, youth)
    play(client, youth, "ton_style", lambda item: next(
        option["id"] for option in item["options"] if option["signals"][0]["value"] > 50
    ))
    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    trail = client.get(f"{base}/traits/conscientiousness", headers=psychologist).get_json()
    custom = [row for row in trail["signals"] if row["tier"] == "custom"]
    assert len(custom) == 5 and all(row["value"] == 75 for row in custom)
    assert trail["cursor"]["by_tier"]["custom"]["value"] == 75
    sheet = client.get("/api/me/game/sheet", headers=youth).get_json()
    personality = next(group for group in sheet["trait_groups"] if group["id"] == "personality")
    labels = {trait["id"]: trait["label"] for trait in personality["traits"]}
    assert labels["extraversion"] == "Sociable"

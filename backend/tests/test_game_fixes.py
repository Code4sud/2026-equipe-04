"""Régressions du module de jeu : verdicts, attributs, versions du contenu, démo, mesures montrées
au jeune, entrées invalides, verrous, champs du backoffice et historique des modifications."""
from __future__ import annotations

import io
import json
import random
import re
from pathlib import Path

import pytest
from test_game import answer, complete, finish_onboarding, start, youth_id

from app.game import service as game
from app.game.catalog import Catalog
from app.game.performance import SCORERS, drop_percents
from app.game.scoring import InvalidAnswer, UnsafeText, clean_text

FIXTURES = Path(__file__).parent / "fixtures" / "game"
FRONT_RESULTS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "game" / "cognitive" / "results.ts"
COGNITIVE = ("corsi", "digit_span", "stroop", "logic")


@pytest.fixture(autouse=True)
def catalog(app):
    content = Catalog(overlays=[FIXTURES])
    keep = {"onboarding", "fixture_questionnaire", "fixture_span"}
    content.instruments = {k: v for k, v in content.instruments.items() if k in keep}
    app.extensions["game_catalog"] = content
    return content


@pytest.fixture
def real_games(app):
    """Vrais jeux cognitifs, avec le quiz d'arrivée fictif des tests."""
    content = Catalog(overlays=[FIXTURES])
    content.instruments = {
        k: v for k, v in content.instruments.items() if k in {"onboarding", *COGNITIVE}
    }
    app.extensions["game_catalog"] = content
    return content


def psy_base(client, youth) -> str:
    return f"/api/backoffice/youths/{youth_id(client, youth)}/game"


def run_rows(client, psychologist, youth, run_id) -> dict[str, dict]:
    detail = client.get(f"{psy_base(client, youth)}/runs/{run_id}", headers=psychologist).get_json()
    return {row["item_id"]: row for row in detail["answers"]}


def sheet(client, youth) -> dict:
    return client.get("/api/me/game/sheet", headers=youth).get_json()


def youth_traits(payload: dict) -> dict[str, dict]:
    return {trait["id"]: trait for group in payload["trait_groups"] for trait in group["traits"]}


def facts_of(client, youth) -> dict[str, dict]:
    return {fact["key"]: fact for fact in sheet(client, youth)["facts"]}


def raw(client, method, url, headers, text):
    """Envoie un JSON tel quel (NaN, 1e400, \\u0000...), que json.dumps ne produirait pas."""
    return client.open(url, method=method, data=text, headers={**headers, "Content-Type": "application/json"})


# --- 2. La fiche ne montre que des points forts ---


def test_attribute_score_maps_strengths_from_50_100_to_10_20():
    parts = [{"trait": "a"}, {"trait": "b", "weight": 0.5}, {"trait": "c"}]
    cursors = {"a": {"value": 100.0}, "b": {"value": 50.0}, "c": {"value": 5.0}}
    # c (5) est ignoré : (100 + 0,5 × 50) / 1,5 = 83,3, soit 10 + 33,3 / 5 = 16,7.
    assert game._attribute_score(parts, cursors) == 17
    assert game._attribute_score([{"trait": "a"}], cursors) == 20
    assert game._attribute_score([{"trait": "b"}], cursors) == 10
    assert game._attribute_score([{"trait": "c"}], cursors) is None
    assert game._attribute_score([{"trait": "a"}], {"a": {"value": None}}) is None


def test_attributes_never_show_a_low_number(client, youth):
    finish_onboarding(client, youth)  # Extraversion 10, intérêt manuel 95, organisation 100.
    attributes = {a["id"]: a for a in sheet(client, youth)["attributes"]}
    # L'audace ne repose ici que sur un pôle bas : elle reste à découvrir au lieu d'afficher 9.
    assert attributes["audace"]["score"] is None
    assert attributes["audace"]["reveal_with"]["id"] == "fixture_questionnaire"
    assert attributes["adresse"]["score"] == 19 and attributes["methode"]["score"] == 20

    run_id = start(client, youth, "fixture_span")["run"]["id"]
    failed = [{"sequence": [1, 2], "response": [2, 1]}, {"sequence": [1, 2, 3], "response": [3, 2, 1]}]
    assert complete(client, youth, run_id, trials=failed).status_code == 200
    attributes = {a["id"]: a for a in sheet(client, youth)["attributes"]}
    # Partie ratée : la mémoire de travail à 0 ne fait pas apparaître une logique à 8.
    assert attributes["logique"]["score"] is None
    assert all(a["score"] is None or 10 <= a["score"] <= 20 for a in attributes.values())


def test_unipolar_traits_never_show_a_low_value_whatever_their_group(client, youth, catalog):
    for group in catalog.trait_groups:
        group.pop("youth_view", None)
    finish_onboarding(client, youth)
    run_id = start(client, youth, "fixture_span")["run"]["id"]
    assert complete(client, youth, run_id, trials=[{"sequence": [1, 2], "response": [2, 1]}]).status_code == 200
    traits = youth_traits(sheet(client, youth))
    assert "working_memory" not in traits
    assert all(trait["value"] >= 50 for trait in traits.values() if trait["kind"] == "unipolar")
    # Un curseur bipolaire reste neutre : ses deux pôles se montrent.
    assert traits["extraversion"]["value"] == 10.0


# --- 6. Le jeune ne reçoit que ses réussites ---


def metric_paths(data: dict, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    paths = set()
    for key, value in data.items():
        paths.add((*prefix, key))
        if isinstance(value, dict):
            paths |= metric_paths(value, (*prefix, key))
    return paths


def front_metric_paths() -> set[tuple[str, ...]]:
    """Clés lues par l'écran de fin des jeux (count(metrics, 'phases', 'forward', 'span'))."""
    text = FRONT_RESULTS.read_text(encoding="utf-8")
    return {tuple(re.findall(r"'([^']+)'", args)) for args in re.findall(r"count\(metrics, ([^)]*)\)", text)}


def test_default_youth_projection_drops_every_percent():
    metrics = {"span": 5, "percent": 40.0, "phases": {"forward": {"span": 5, "percent": 40.0}}}
    assert drop_percents(metrics) == {"span": 5, "phases": {"forward": {"span": 5}}}
    assert metrics["percent"] == 40.0  # Les mesures de la psychologue restent intactes.


def test_youth_result_keeps_what_the_screen_reads_and_nothing_for_the_psychologist_only(
    client, youth, psychologist, real_games
):
    wanted = front_metric_paths()
    assert ("phases", "forward", "span") in wanted and ("best_streak",) in wanted
    finish_onboarding(client, youth)
    available: set[tuple[str, ...]] = set()
    for instrument_id in COGNITIVE:
        instrument = real_games.instruments[instrument_id]
        trials = SCORERS[instrument["performance"]["scorer"]].demo(instrument, random.Random(instrument_id), 0.8)
        run_id = start(client, youth, instrument_id)["run"]["id"]
        response = complete(client, youth, run_id, trials=trials)
        assert response.status_code == 200, response.get_json()
        metrics = response.get_json()["metrics"]
        text = json.dumps(metrics)
        for hidden in ("percent", "accuracy", "precision", "resistance", "interference", "by_kind", "total"):
            assert hidden not in text, (instrument_id, hidden)
        available |= metric_paths(metrics)
        detail = client.get(f"{psy_base(client, youth)}/runs/{run_id}", headers=psychologist).get_json()
        assert "percent" in detail["run"]["metrics"]
    assert wanted <= available


# --- 7. Entrées invalides ---


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e400", "1" + "0" * 400])
def test_response_times_that_are_not_finite_are_ignored(client, youth, psychologist, number):
    run_id = start(client, youth)["run"]["id"]
    url = f"/api/me/game/runs/{run_id}/answers/groupe"
    response = raw(client, "PUT", url, youth, f'{{"value": "a", "response_ms": {number}}}')
    assert response.status_code == 200, response.get_json()
    expected = 600_000 if number.startswith("1000") else None
    assert run_rows(client, psychologist, youth, run_id)["groupe"]["response_ms"] == expected


def test_trial_times_that_are_not_finite_are_ignored(client, youth, psychologist):
    finish_onboarding(client, youth)
    run_id = start(client, youth, "fixture_span")["run"]["id"]
    trials = ", ".join(
        f'{{"sequence": {list(range(1, n + 1))}, "response": {list(range(1, n + 1))}, "rt_ms": {rt}}}'
        for n, rt in [(2, "NaN"), (3, "1e400"), (4, "-Infinity"), (5, "1" + "0" * 400)]
    )
    response = raw(client, "POST", f"/api/me/game/runs/{run_id}/complete", youth, f'{{"trials": [{trials}]}}')
    assert response.status_code == 200, response.get_json()
    rows = run_rows(client, psychologist, youth, run_id)
    assert [row["response_ms"] for row in rows.values()] == [None, None, None, 600_000]


UNSAFE = ["\\u0000", "a\\u0007b", "\\u001b[0m", "\\u007f", "\\u009b", "\\ud800", "x\\udfff"]


@pytest.mark.parametrize("unsafe", UNSAFE)
def test_text_answers_refuse_control_characters_and_lone_surrogates(client, youth, unsafe):
    run_id = start(client, youth)["run"]["id"]
    for item_id in ("passion", "couleur"):  # Question libre, et choix qui accepte un texte.
        url = f"/api/me/game/runs/{run_id}/answers/{item_id}"
        response = raw(client, "PUT", url, youth, f'{{"value": {{"text": "Le skate{unsafe}"}}}}')
        assert response.status_code == 400, (item_id, response.get_json())
        assert response.get_json()["error"]["code"] == "invalid_answer"
    assert facts_of(client, youth) == {}


@pytest.mark.parametrize("unsafe", UNSAFE)
def test_fact_edits_refuse_control_characters_and_lone_surrogates(client, youth, unsafe):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "couleur", "jaune")
    response = raw(client, "PATCH", "/api/me/game/facts/couleur_preferee", youth, f'{{"value": "Vert{unsafe}"}}')
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_field"
    assert facts_of(client, youth)["couleur_preferee"]["value"] == "Jaune"


def test_ordinary_whitespace_is_kept_as_single_spaces(client, youth):
    run_id = start(client, youth)["run"]["id"]
    url = f"/api/me/game/runs/{run_id}/answers/passion"
    assert raw(client, "PUT", url, youth, '{"value": {"text": "  Le\\tskate\\r\\n et\\u00a0le roller "}}').status_code == 200
    assert facts_of(client, youth)["passion"]["value"] == "Le skate et le roller"
    response = client.patch("/api/me/game/facts/passion", json={"value": "Le\nroller"}, headers=youth)
    assert response.status_code == 200 and response.get_json()["fact"]["value"] == "Le roller"


def test_clean_text_is_the_single_rule():
    assert clean_text("  Le\tskate\r\n ", 120) == "Le skate"
    for unsafe in ("\x00", "\x1b[0m", "\x7f", "\x9b", "\ud800"):
        with pytest.raises(UnsafeText):
            clean_text(f"a{unsafe}b", 120)
    for empty in ("", "   ", None, 12):
        with pytest.raises(InvalidAnswer):
            clean_text(empty, 120)
    with pytest.raises(InvalidAnswer):
        clean_text("x" * 121, 120)


def test_game_requests_are_capped_at_256_kb(app, client, youth):
    run_id = start(client, youth)["run"]["id"]
    url = f"/api/me/game/runs/{run_id}/answers/groupe"
    body = json.dumps({"value": "a", "padding": "x" * (300 * 1024)})
    response = raw(client, "PUT", url, youth, body)
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "payload_too_large"
    # Sans longueur annoncée (envoi par morceaux), la lecture s'arrête aussi à la limite.
    chunked = client.put(
        url,
        input_stream=io.BytesIO(body.encode()),
        headers={**youth, "Content-Type": "application/json", "Transfer-Encoding": "chunked"},
        environ_overrides={"wsgi.input_terminated": True},
    )
    assert chunked.status_code == 413
    assert chunked.get_json()["error"]["code"] == "payload_too_large"
    # Un envoi normal passe, par morceaux ou non, et la configuration globale ne change pas.
    small = client.put(
        url,
        input_stream=io.BytesIO(b'{"value": "b"}'),
        headers={**youth, "Content-Type": "application/json", "Transfer-Encoding": "chunked"},
        environ_overrides={"wsgi.input_terminated": True},
    )
    assert small.status_code == 200, small.get_json()
    assert answer(client, youth, run_id, "groupe", "a").status_code == 200
    assert app.config.get("MAX_CONTENT_LENGTH") is None

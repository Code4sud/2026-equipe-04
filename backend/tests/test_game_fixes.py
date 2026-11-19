"""Régressions du module de jeu : verdicts, attributs, versions du contenu, démo, mesures montrées
au jeune, entrées invalides, verrous, champs du backoffice et historique des modifications."""
from __future__ import annotations

import copy
import io
import json
import random
import re
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import event, update
from test_game import answer, complete, cursor, finish_onboarding, start, youth_id

from app.errors import ApiError
from app.extensions import db
from app.game import events
from app.game import service as game
from app.game.catalog import Catalog
from app.game.performance import SCORERS, drop_percents
from app.game.scoring import InvalidAnswer, UnsafeText, clean_text, scale_scores
from app.models import (
    GameAnswer,
    GameEvent,
    GameFact,
    GameRun,
    GameRunStatus,
    TraitFeedback,
    User,
    iso,
    utcnow,
)

FIXTURES = Path(__file__).parent / "fixtures" / "game"
FRONT_RESULTS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "game" / "cognitive" / "results.ts"
COGNITIVE = ("corsi", "digit_span", "stroop", "logic")

# Un autre jeu qui pose la même question de détail, avec le même identifiant de question.
ECHO = {
    "id": "fixture_echo",
    "version": 1,
    "order": 30,
    "kind": "questionnaire",
    "tier": "custom",
    "title": "Écho fictif",
    "tagline": "Pour tester",
    "icon": "mirror",
    "duration_min": 1,
    "xp": 20,
    "min_answers": 1,
    "items": [
        {
            "id": "couleur", "type": "choice", "prompt": "Et ta couleur aujourd'hui ?",
            "fact": "couleur_preferee", "fact_label": "Couleur préférée",
            "options": [
                {"id": "vert", "label": "Vert", "signals": [{"trait": "openness", "value": 70}]},
                {"id": "bleu", "label": "Bleu", "signals": [{"trait": "openness", "value": 60}]},
            ],
        },
        {
            "id": "calme", "type": "likert", "prompt": "Je garde mon calme.",
            "trait": "emotional_stability", "keyed": "+", "scale": {"min": 1, "max": 5},
        },
    ],
}

VERSIONED = {
    "id": "fixture_versions",
    "version": 1,
    "order": 40,
    "kind": "questionnaire",
    "tier": "custom",
    "title": "Versions fictives",
    "tagline": "Pour tester",
    "icon": "mirror",
    "duration_min": 1,
    "xp": 20,
    "min_answers": 2,
    "scale": {"min": 1, "max": 5, "labels": ["Non", "Plutôt non", "Bof", "Plutôt oui", "Oui"]},
    "items": [
        {
            "id": "q1", "type": "choice", "prompt": "Un choix",
            "options": [
                {"id": "a", "label": "A", "signals": [{"trait": "extraversion", "value": 90}]},
                {"id": "b", "label": "B", "signals": [{"trait": "extraversion", "value": 10}]},
            ],
        },
        {"id": "q2", "type": "likert", "prompt": "Je parle facilement.", "trait": "extraversion", "keyed": "+"},
        {"id": "q3", "type": "likert", "prompt": "Je range.", "trait": "conscientiousness", "keyed": "+"},
        {"id": "q4", "type": "likert", "prompt": "Je finis.", "trait": "conscientiousness", "keyed": "+"},
        {
            "id": "q5", "type": "choice", "prompt": "Un autre choix",
            "options": [{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}, {"id": "z", "label": "Z"}],
        },
    ],
}


def version_two() -> dict:
    instrument = copy.deepcopy(VERSIONED)
    instrument["version"] = 2
    items = {item["id"]: item for item in instrument["items"]}
    # q1 devient une question Likert : l'ancienne réponse « a » n'a plus de sens.
    items["q1"] = {"id": "q1", "type": "likert", "prompt": "Une échelle", "trait": "extraversion", "keyed": "+"}
    # q2 change de sens : la réponse gardée est recalculée avec la nouvelle clé.
    items["q2"]["keyed"] = "-"
    # q3 passe de 1-5 à 1-7 : un 4 ne veut plus dire la même chose.
    items["q3"]["scale"] = {"min": 1, "max": 7}
    # q4 est renommée : elle ne doit pas compter deux fois.
    renamed = {**items.pop("q4"), "id": "q4b"}
    # q5 perd l'option « z ».
    items["q5"]["options"] = items["q5"]["options"][:2]
    instrument["items"] = [items["q1"], items["q2"], items["q3"], renamed, items["q5"]]
    return instrument


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


def overview(client, psychologist, youth) -> dict:
    response = client.get(psy_base(client, youth), headers=psychologist)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def run_rows(client, psychologist, youth, run_id) -> dict[str, dict]:
    detail = client.get(f"{psy_base(client, youth)}/runs/{run_id}", headers=psychologist).get_json()
    return {row["item_id"]: row for row in detail["answers"]}


def sheet(client, youth) -> dict:
    return client.get("/api/me/game/sheet", headers=youth).get_json()


def youth_traits(payload: dict) -> dict[str, dict]:
    return {trait["id"]: trait for group in payload["trait_groups"] for trait in group["traits"]}


def facts_of(client, youth) -> dict[str, dict]:
    return {fact["key"]: fact for fact in sheet(client, youth)["facts"]}


def verdict(client, youth, trait_id, value):
    return client.put(f"/api/me/game/traits/{trait_id}/feedback", json={"verdict": value}, headers=youth)


def skip(client, youth, run_id, item_id):
    response = client.put(
        f"/api/me/game/runs/{run_id}/answers/{item_id}", json={"skipped": True}, headers=youth
    )
    assert response.status_code == 200, response.get_json()
    return response


def raw(client, method, url, headers, text):
    """Envoie un JSON tel quel (NaN, 1e400, \\u0000...), que json.dumps ne produirait pas."""
    return client.open(url, method=method, data=text, headers={**headers, "Content-Type": "application/json"})


def play_questionnaire(client, youth, values: dict) -> dict:
    run_id = start(client, youth, "fixture_questionnaire")["run"]["id"]
    for item_id, value in values.items():
        assert answer(client, youth, run_id, item_id, value).status_code == 200
    response = complete(client, youth, run_id)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


@contextmanager
def written_by_another_request(statement):
    """Une autre requête écrit `statement` juste avant la première écriture de celle-ci."""
    fired: list[bool] = []

    def before_flush(_session, _context, _instances):
        if not fired:
            fired.append(True)
            with db.engine.begin() as connection:
                connection.execute(statement)

    event.listen(db.session, "before_flush", before_flush)
    try:
        yield fired
    finally:
        event.remove(db.session, "before_flush", before_flush)


def answer_row(run_id: str, item_id: str, value, label: str):
    return GameAnswer.__table__.insert().values(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
        item_id=item_id,
        position=0,
        prompt="Envoi précédent",
        value=value,
        label=label,
        skipped=False,
        signals=[],
        answered_at=utcnow(),
    )


# --- 1. Un verdict vaut pour le pôle jugé ---


def test_verdict_follows_the_pole_the_youth_judged(client, youth, psychologist):
    finish_onboarding(client, youth)  # Extraversion à 10 : « Réservé·e ».
    assert verdict(client, youth, "extraversion", "disagree").status_code == 200
    trait = youth_traits(sheet(client, youth))["extraversion"]
    assert trait["label"] == "Réservé·e" and trait["verdict"] == "disagree"
    detail = cursor(overview(client, psychologist, youth), "extraversion")["verdict_detail"]
    assert detail["verdict"] == "disagree" and detail["label_at_verdict"] == "Réservé·e"
    assert detail["value_at_verdict"] == 10.0 and detail["stale"] is False and detail["at"]

    # Le questionnaire fait basculer le curseur vers « Sociable » : l'ancien « Pas moi » ne vaut plus.
    result = play_questionnaire(client, youth, {"e1": 5, "e2": 1, "c1": 4})
    highlight = next(trait for trait in result["highlights"] if trait["id"] == "extraversion")
    assert highlight["label"] == "Sociable" and highlight["verdict"] is None
    trait = youth_traits(sheet(client, youth))["extraversion"]
    assert trait["label"] == "Sociable" and trait["verdict"] is None

    psy = cursor(overview(client, psychologist, youth), "extraversion")
    assert psy["headline"] == {"percent": 82, "label": "Sociable"}
    assert psy["verdict"] == "disagree"
    assert psy["verdict_detail"]["stale"] is True
    assert psy["verdict_detail"]["label_at_verdict"] == "Réservé·e"

    # Le jeune juge le nouveau pôle.
    assert verdict(client, youth, "extraversion", "agree").status_code == 200
    assert youth_traits(sheet(client, youth))["extraversion"]["verdict"] == "agree"
    data = overview(client, psychologist, youth)
    detail = cursor(data, "extraversion")["verdict_detail"]
    assert (detail["verdict"], detail["label_at_verdict"], detail["value_at_verdict"], detail["stale"]) == (
        "agree", "Sociable", 82.0, False
    )
    # Juger un pôle qui a changé est un nouveau verdict, pas un changement d'avis.
    latest = data["events"][0]
    assert latest["kind"] == "verdict_set"
    assert latest["before"]["verdict"] == "disagree" and latest["before"]["label"] == "Réservé·e"
    assert latest["after"] == {"verdict": "agree", "label": "Sociable", "value": 82.0}


def test_verdict_label_is_computed_by_the_server(client, youth, psychologist):
    finish_onboarding(client, youth)
    response = client.put(
        "/api/me/game/traits/extraversion/feedback",
        json={"verdict": "agree", "label": "Sociable", "label_at_verdict": "Sociable", "value_at_verdict": 99},
        headers=youth,
    )
    assert response.status_code == 200
    assert response.get_json() == {"trait_id": "extraversion", "verdict": "agree"}
    detail = cursor(overview(client, psychologist, youth), "extraversion")["verdict_detail"]
    assert detail["label_at_verdict"] == "Réservé·e" and detail["value_at_verdict"] == 10.0


def test_withdrawn_verdict_leaves_a_trace(client, youth, psychologist):
    finish_onboarding(client, youth)
    for value in ("agree", "agree", "disagree", None):
        assert verdict(client, youth, "extraversion", value).status_code == 200
    data = overview(client, psychologist, youth)
    psy = cursor(data, "extraversion")
    assert psy["verdict"] is None and psy["verdict_detail"] is None
    # Le double appui sur « C'est moi » ne laisse qu'une trace.
    assert [e["kind"] for e in data["events"]] == ["verdict_withdrawn", "verdict_changed", "verdict_set"]
    withdrawn = data["events"][0]
    assert withdrawn["subject"] == "Réservé ↔ Sociable"
    assert withdrawn["ref"] == {"type": "trait", "trait_id": "extraversion"}
    assert withdrawn["before"]["verdict"] == "disagree" and withdrawn["before"]["label"] == "Réservé·e"
    assert withdrawn["after"] == {"verdict": None, "label": "Réservé·e", "value": 10.0}
    assert youth_traits(sheet(client, youth))["extraversion"]["verdict"] is None


def test_two_quick_verdict_taps_keep_the_last_one(client, youth, psychologist):
    finish_onboarding(client, youth)
    earlier_tap = TraitFeedback.__table__.insert().values(
        youth_id=uuid.UUID(youth_id(client, youth)),
        trait_id="extraversion",
        verdict="agree",
        label_at_verdict="Réservé·e",
        value_at_verdict=10.0,
        updated_at=utcnow(),
    )
    with written_by_another_request(earlier_tap) as fired:
        response = verdict(client, youth, "extraversion", "disagree")
    assert fired and response.status_code == 200, response.get_json()
    data = overview(client, psychologist, youth)
    assert cursor(data, "extraversion")["verdict"] == "disagree"
    assert data["events"][0]["kind"] == "verdict_changed"
    assert data["events"][0]["before"]["verdict"] == "agree"


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


# --- 3. Passer une question de détail retire le détail ---


def test_skipping_an_answered_fact_question_removes_its_fact(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "couleur", "jaune")
    answer(client, youth, run_id, "passion", {"text": "Le skate"})
    client.patch("/api/me/game/facts/passion", json={"value": "Le roller"}, headers=youth)
    skip(client, youth, run_id, "couleur")
    skip(client, youth, run_id, "passion")

    facts = facts_of(client, youth)
    # La couleur venait de la réponse retirée ; la passion corrigée par le jeune reste la sienne.
    assert "couleur_preferee" not in facts and facts["passion"]["value"] == "Le roller"
    retracted = [e for e in overview(client, psychologist, youth)["events"] if e["kind"] == "answer_retracted"]
    assert [e["ref"]["item_id"] for e in retracted] == ["passion", "couleur"]
    passion, couleur = retracted
    assert couleur["subject"] == "Quiz d'arrivée (fictif) · Ta couleur préférée ?"
    assert couleur["before"] == {"label": "Jaune", "value": "jaune"}
    assert couleur["after"]["skipped"] is True
    assert couleur["after"]["fact_removed"] == {
        "key": "couleur_preferee", "label": "Couleur préférée", "value": "Jaune"
    }
    assert passion["after"]["fact_removed"] is None


def test_skipping_a_question_never_answered_changes_nothing(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    skip(client, youth, run_id, "couleur")
    assert overview(client, psychologist, youth)["events"] == []


def test_retraction_only_removes_a_fact_from_the_same_instrument_and_item(client, youth, catalog):
    catalog.instruments["fixture_echo"] = copy.deepcopy(ECHO)
    onboarding = start(client, youth)["run"]["id"]
    answer(client, youth, onboarding, "couleur", "jaune")
    echo = start(client, youth, "fixture_echo")["run"]["id"]
    answer(client, youth, echo, "couleur", "bleu")
    # Le détail vient maintenant de l'écho : passer la question du quiz ne le retire pas.
    skip(client, youth, onboarding, "couleur")
    assert facts_of(client, youth)["couleur_preferee"]["value"] == "Bleu"
    skip(client, youth, echo, "couleur")
    assert "couleur_preferee" not in facts_of(client, youth)


# --- 4. Une partie commencée sur une ancienne version du contenu ---


def test_resuming_an_old_version_reconciles_the_answers(client, youth, psychologist, catalog):
    catalog.instruments["fixture_versions"] = copy.deepcopy(VERSIONED)
    run_id = start(client, youth, "fixture_versions")["run"]["id"]
    for item_id, value in [("q1", "a"), ("q2", 5), ("q3", 4), ("q4", 3), ("q5", "z")]:
        assert answer(client, youth, run_id, item_id, value).status_code == 200

    catalog.instruments["fixture_versions"] = version_two()
    resumed = start(client, youth, "fixture_versions")
    assert resumed["run"]["id"] == run_id and resumed["run"]["instrument_version"] == 2
    assert resumed["answers"] == [{"item_id": "q2", "value": 5, "skipped": False}]

    assert answer(client, youth, run_id, "q4b", 3).status_code == 200
    assert complete(client, youth, run_id).status_code == 200
    detail = client.get(f"{psy_base(client, youth)}/runs/{run_id}", headers=psychologist).get_json()
    rows = {row["item_id"]: row for row in detail["answers"]}
    assert list(rows) == ["q1", "q2", "q3", "q4b", "q5"]
    assert [rows[i]["status"] for i in rows] == ["unanswered", "answered", "unanswered", "answered", "unanswered"]
    # q2 garde sa réponse, recalculée avec la nouvelle clé inversée.
    assert rows["q2"]["signals"][0]["value"] == 0
    scales = detail["run"]["metrics"]["scales"]
    assert scales["extraversion"]["n"] == 1 and scales["conscientiousness"]["n"] == 1
    trail = client.get(f"{psy_base(client, youth)}/traits/conscientiousness", headers=psychologist).get_json()
    assert [row["item_id"] for row in trail["signals"]] == ["q4b"]


def test_completing_after_a_content_update_does_not_crash(client, youth, psychologist, catalog):
    catalog.instruments["fixture_versions"] = copy.deepcopy(VERSIONED)
    run_id = start(client, youth, "fixture_versions")["run"]["id"]
    for item_id, value in [("q1", "a"), ("q2", 5), ("q3", 4), ("q4", 3), ("q5", "x")]:
        answer(client, youth, run_id, item_id, value)

    catalog.instruments["fixture_versions"] = version_two()
    response = complete(client, youth, run_id)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["run"]["instrument_version"] == 2
    detail = client.get(f"{psy_base(client, youth)}/runs/{run_id}", headers=psychologist).get_json()
    assert set(detail["run"]["metrics"]["scales"]) == {"extraversion"}
    answered = [row["item_id"] for row in detail["answers"] if row["status"] == "answered"]
    assert answered == ["q2", "q5"]


def test_scale_scores_skip_values_that_are_not_on_the_scale():
    instrument = {
        "scale": {"min": 1, "max": 5},
        "items": [{"id": "e1", "type": "likert", "trait": "extraversion", "keyed": "-"}],
    }
    answers = [
        SimpleNamespace(item_id="e1", skipped=False, value=value) for value in ("a", 4.5, True, None, 9, 4)
    ]
    assert scale_scores(instrument, answers) == {
        "extraversion": {"n": 1, "raw_sum": 2, "raw_min": 1, "raw_max": 5, "percent": 25.0}
    }


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


# --- 8. Modifications d'une partie sous verrou ---


def test_a_double_put_updates_the_answer_instead_of_failing(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    with written_by_another_request(answer_row(run_id, "groupe", "a", "J'invite tout le monde")) as fired:
        response = answer(client, youth, run_id, "groupe", "c")
    assert fired and response.status_code == 200, response.get_json()
    assert response.get_json()["xp_gained"] == 0  # L'autre envoi a déjà compté la réponse.
    assert start(client, youth)["answers"] == [{"item_id": "groupe", "value": "c", "skipped": False}]
    changed = overview(client, psychologist, youth)["events"][0]
    assert changed["kind"] == "answer_changed" and changed["before"]["value"] == "a"
    assert changed["after"] == {"label": "Je préfère un truc au calme", "value": "c"}


def test_a_fact_question_sent_twice_does_not_crash(client, youth):
    run_id = start(client, youth)["run"]["id"]
    with written_by_another_request(answer_row(run_id, "couleur", "bleu", "Bleu")) as fired:
        response = answer(client, youth, run_id, "couleur", "jaune")
    assert fired and response.status_code == 200, response.get_json()
    assert {key: fact["value"] for key, fact in facts_of(client, youth).items()} == {"couleur_preferee": "Jaune"}


def test_a_fact_created_meanwhile_by_another_game_is_updated(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    other_game = GameFact.__table__.insert().values(
        youth_id=uuid.UUID(youth_id(client, youth)),
        key="couleur_preferee",
        label="Couleur préférée",
        value="Vert",
        original_value="Vert",
        source_instrument_id="fixture_echo",
        source_item_id="couleur",
        edited=False,
        hidden=False,
        updated_at=utcnow(),
    )
    with written_by_another_request(other_game) as fired:
        response = answer(client, youth, run_id, "couleur", "jaune")
    assert fired and response.status_code == 200, response.get_json()
    fact = next(f for f in overview(client, psychologist, youth)["facts"] if f["key"] == "couleur_preferee")
    assert fact["value"] == "Jaune" and fact["source_instrument_id"] == "onboarding"


def test_a_run_completed_meanwhile_refuses_answers_and_is_not_scored_twice(app, client, youth):
    run_id = start(client, youth)["run"]["id"]
    for item_id, value in [("groupe", "a"), ("scooter", "a"), ("agenda", 4)]:
        answer(client, youth, run_id, item_id, value)
    with app.app_context():
        user = db.session.get(User, uuid.UUID(youth_id(client, youth)))
        stale = db.session.get(GameRun, uuid.UUID(run_id))
        assert stale.status == GameRunStatus.IN_PROGRESS  # Copie gardée par cette requête.
        # Une autre requête termine la partie pendant ce temps.
        with db.engine.begin() as connection:
            connection.execute(
                update(GameRun.__table__)
                .where(GameRun.__table__.c.id == stale.id)
                .values(status=GameRunStatus.COMPLETED, completed_at=utcnow())
            )
        for action in (
            lambda: game.save_answer(user, stale.id, "couleur", {"value": "jaune"}),
            lambda: game.pause_run(user, stale.id),
        ):
            with pytest.raises(ApiError) as caught:
                action()
            assert caught.value.code == "run_closed"
            db.session.rollback()
        result = game.complete_run(user, stale.id, {})
        assert result["run"]["status"] == "completed"
        # La partie n'est pas notée une deuxième fois par-dessus l'autre requête.
        assert db.session.get(GameRun, stale.id).metrics == {}


def test_every_run_change_takes_the_run_lock(app, client, youth, monkeypatch):
    locked: list[uuid.UUID] = []
    real_lock = game._lock_run

    def spy(run_id):
        locked.append(run_id)
        return real_lock(run_id)

    monkeypatch.setattr(game, "_lock_run", spy)
    run_id = start(client, youth)["run"]["id"]
    assert locked == []  # Nouvelle partie : rien à verrouiller.
    steps = [
        lambda: client.post(f"/api/me/game/runs/{run_id}/pause", headers=youth),
        lambda: client.post("/api/me/game/instruments/onboarding/runs", headers=youth),
        lambda: answer(client, youth, run_id, "groupe", "a"),
        lambda: answer(client, youth, run_id, "scooter", "a"),
        lambda: answer(client, youth, run_id, "agenda", 4),
        lambda: complete(client, youth, run_id),
    ]
    for count, step in enumerate(steps, start=1):
        assert step().status_code in {200, 201}
        assert len(locked) == count and str(locked[-1]) == run_id

    seen: dict = {}
    with app.app_context():
        real_get = db.session.get

        def get(entity, ident, **kwargs):
            seen.update(kwargs)
            return real_get(entity, ident, **kwargs)

        monkeypatch.setattr(db.session, "get", get)
        real_lock(uuid.UUID(run_id))
    assert seen == {"with_for_update": True, "populate_existing": True}


# --- 9. Champs demandés par le backoffice ---


def test_facts_say_where_they_come_from_and_when_the_youth_edited_them(client, youth, psychologist):
    finish_onboarding(client, youth)
    facts = {f["key"]: f for f in overview(client, psychologist, youth)["facts"]}
    color = facts["couleur_preferee"]
    assert (color["source_instrument_id"], color["source_item_id"], color["edited_at"]) == (
        "onboarding", "couleur", None
    )
    client.patch("/api/me/game/facts/couleur_preferee", json={"hidden": True}, headers=youth)
    client.patch("/api/me/game/facts/passion", json={"value": "Le skate"}, headers=youth)
    facts = {f["key"]: f for f in overview(client, psychologist, youth)["facts"]}
    assert facts["couleur_preferee"]["edited_at"] is None  # Masquer n'est pas corriger.
    assert facts["passion"]["edited_at"] and facts["passion"]["edited"] is True
    mine = facts_of(client, youth)["passion"]
    assert mine["edited_at"] == facts["passion"]["edited_at"]
    assert "source_instrument_id" not in mine and "source_item_id" not in mine


def test_hidden_flag_matches_the_instrument_and_the_item(client, youth, psychologist, catalog):
    catalog.instruments["fixture_echo"] = copy.deepcopy(ECHO)
    onboarding = start(client, youth)["run"]["id"]
    echo = start(client, youth, "fixture_echo")["run"]["id"]
    answer(client, youth, echo, "couleur", "vert")
    answer(client, youth, echo, "calme", 4)
    assert complete(client, youth, echo).status_code == 200
    # Le quiz répond ensuite à sa propre question « couleur » : le détail vient de lui.
    for item_id, value in [("couleur", "jaune"), ("groupe", "c"), ("scooter", "a"), ("agenda", 5)]:
        answer(client, youth, onboarding, item_id, value)
    assert complete(client, youth, onboarding).status_code == 200
    client.patch("/api/me/game/facts/couleur_preferee", json={"hidden": True}, headers=youth)

    assert run_rows(client, psychologist, youth, onboarding)["couleur"]["hidden_by_youth"] is True
    assert run_rows(client, psychologist, youth, echo)["couleur"]["hidden_by_youth"] is False
    trail = client.get(f"{psy_base(client, youth)}/traits/openness", headers=psychologist).get_json()
    assert [(row["instrument_id"], row["hidden_by_youth"]) for row in trail["signals"]] == [
        ("fixture_echo", False)
    ]


def test_run_detail_shows_what_was_offered(client, youth, psychologist):
    run_id, _ = finish_onboarding(client, youth)
    rows = run_rows(client, psychologist, youth, run_id)
    assert rows["couleur"]["options"] == [{"id": "jaune", "label": "Jaune"}, {"id": "bleu", "label": "Bleu"}]
    assert rows["couleur"]["scale"] is None
    assert rows["agenda"]["scale"] == {
        "min": 1, "max": 5, "labels": ["Jamais", "Rarement", "Parfois", "Souvent", "Toujours"]
    }
    assert rows["agenda"]["options"] is None
    assert rows["passion"]["options"] is None and rows["passion"]["scale"] is None
    questionnaire = start(client, youth, "fixture_questionnaire")["run"]["id"]
    scale = run_rows(client, psychologist, youth, questionnaire)["e1"]["scale"]
    assert scale["min"] == 1 and scale["max"] == 5 and scale["labels"][0] == "Pas du tout"


def test_psy_catalog_gives_weights_and_confidence_thresholds(client, psychologist):
    data = client.get("/api/backoffice/game/catalog", headers=psychologist).get_json()
    assert data["weights"] == {
        "validated": 1.0, "performance": 1.0, "adapted": 0.5, "custom": 0.5, "talent": 0.25
    }
    assert data["confidence_thresholds"] == {"medium": 2.0, "high": 5.0}
    assert all("chapters" in instrument for instrument in data["instruments"])


# --- 10. Historique des modifications, pour la psychologue seulement ---


def test_psychologist_sees_every_change_of_the_youth(client, youth, psychologist):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "couleur", "jaune")
    answer(client, youth, run_id, "couleur", "jaune")  # Même réponse renvoyée : rien à signaler.
    answer(client, youth, run_id, "groupe", "a")
    answer(client, youth, run_id, "groupe", "c")
    answer(client, youth, run_id, "passion", {"text": "Le skate"})
    for change in ({"value": "Le roller"}, {"value": "Le roller"}):
        client.patch("/api/me/game/facts/passion", json=change, headers=youth)
    for hidden in (True, True, False):
        client.patch("/api/me/game/facts/couleur_preferee", json={"hidden": hidden}, headers=youth)
    skip(client, youth, run_id, "couleur")
    for item_id, value in [("scooter", "a"), ("agenda", 5)]:
        answer(client, youth, run_id, item_id, value)
    assert complete(client, youth, run_id).status_code == 200
    for value in ("agree", "disagree", None):
        verdict(client, youth, "extraversion", value)

    found = overview(client, psychologist, youth)["events"]
    assert [e["kind"] for e in found] == [
        "verdict_withdrawn", "verdict_changed", "verdict_set", "answer_retracted",
        "fact_shown", "fact_hidden", "fact_edited", "answer_changed",
    ]
    by_kind = {e["kind"]: e for e in found}
    changed = by_kind["answer_changed"]
    assert changed["subject"] == "Quiz d'arrivée (fictif) · Une soirée s'organise. Tu fais quoi ?"
    assert changed["ref"] == {"type": "answer", "run_id": run_id, "item_id": "groupe", "instrument_id": "onboarding"}
    assert changed["before"] == {"label": "J'invite tout le monde", "value": "a"}
    assert changed["after"] == {"label": "Je préfère un truc au calme", "value": "c"}
    edited = by_kind["fact_edited"]
    assert edited["subject"] == "Passion" and edited["ref"] == {"type": "fact", "key": "passion"}
    assert (edited["before"]["value"], edited["after"]["value"]) == ("Le skate", "Le roller")
    assert by_kind["fact_hidden"]["subject"] == "Couleur préférée"
    assert (by_kind["fact_hidden"]["after"]["hidden"], by_kind["fact_shown"]["after"]["hidden"]) == (True, False)
    assert by_kind["verdict_changed"]["before"]["verdict"] == "agree"
    assert all(e["at"] and isinstance(e["id"], int) for e in found)


def test_youth_never_receives_the_history(client, youth):
    run_id = start(client, youth)["run"]["id"]
    answer(client, youth, run_id, "groupe", "a")
    payloads = [answer(client, youth, run_id, "groupe", "c").get_json()]
    answer(client, youth, run_id, "couleur", "jaune")
    payloads.append(client.patch("/api/me/game/facts/couleur_preferee", json={"value": "Vert"}, headers=youth).get_json())
    payloads.append(verdict(client, youth, "extraversion", "agree").get_json())
    payloads.append(skip(client, youth, run_id, "couleur").get_json())
    answer(client, youth, run_id, "scooter", "a")
    answer(client, youth, run_id, "agenda", 4)
    payloads.append(complete(client, youth, run_id).get_json())
    payloads += [sheet(client, youth), client.get("/api/me/game", headers=youth).get_json()]
    text = json.dumps(payloads, ensure_ascii=False)
    assert '"events"' not in text and "label_at_verdict" not in text and "verdict_detail" not in text
    for kind in events.KINDS:
        assert kind not in text


def test_history_keeps_the_200_most_recent_changes(app, client, youth, psychologist):
    target = uuid.UUID(youth_id(client, youth))
    base = utcnow()
    with app.app_context():
        db.session.add_all(
            GameEvent(
                youth_id=target,
                kind=events.FACT_HIDDEN,
                subject=events.fact_subject("couleur_preferee"),
                before={"hidden": False},
                after={"hidden": True},
                created_at=base + timedelta(seconds=index),
            )
            for index in range(205)
        )
        db.session.commit()
    found = overview(client, psychologist, youth)["events"]
    assert len(found) == 200
    assert found[0]["at"] == iso(base + timedelta(seconds=204))
    assert [e["at"] for e in found] == sorted((e["at"] for e in found), reverse=True)

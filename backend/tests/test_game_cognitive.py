"""Jeux cognitifs : correction recalculée par le serveur, clé jamais envoyée, contenu sourcé."""
from __future__ import annotations

import itertools
import json
import math
import random
import uuid
from pathlib import Path

import pytest
from conftest import register
from test_game_content import guardrail_problems, normalize

from app.extensions import db
from app.game.catalog import Catalog
from app.game.demo import seed_youth_game
from app.game.performance import SCORERS, stroop_sequence
from app.game.scoring import InvalidAnswer
from app.models import User

FIXTURES = Path(__file__).parent / "fixtures" / "game"
GAMES = {
    "corsi": "visuospatial_memory",
    "digit_span": "working_memory",
    "stroop": "attention_control",
    "logic": "reasoning",
}
YOUTH_FIELDS = ("title", "tagline", "intro", "outro", "source_note")


@pytest.fixture(scope="module")
def real():
    return Catalog()


@pytest.fixture
def games(app):
    """Contenu réel des jeux cognitifs, avec le quiz d'arrivée fictif des tests."""
    catalog = Catalog(overlays=[FIXTURES])
    catalog.instruments = {
        key: value for key, value in catalog.instruments.items() if key in {"onboarding", *GAMES}
    }
    app.extensions["game_catalog"] = catalog
    return catalog


def score(catalog: Catalog, instrument_id: str, trials: list[dict]):
    instrument = catalog.instruments[instrument_id]
    return SCORERS[instrument["performance"]["scorer"]].score(instrument, trials)


def demo(catalog: Catalog, instrument_id: str, seed: str = "demo", skill: float = 0.85) -> list[dict]:
    instrument = catalog.instruments[instrument_id]
    return SCORERS[instrument["performance"]["scorer"]].demo(instrument, random.Random(seed), skill)


def start(client, headers, instrument_id):
    response = client.post(f"/api/me/game/instruments/{instrument_id}/runs", headers=headers)
    assert response.status_code in {200, 201}, response.get_json()
    return response.get_json()


def complete(client, headers, run_id, trials):
    return client.post(
        f"/api/me/game/runs/{run_id}/complete", json={"trials": trials}, headers=headers
    )


def finish_onboarding(client, headers):
    run_id = start(client, headers, "onboarding")["run"]["id"]
    for item_id, value in [("couleur", "jaune"), ("groupe", "c"), ("scooter", "a"), ("agenda", 5)]:
        response = client.put(
            f"/api/me/game/runs/{run_id}/answers/{item_id}", json={"value": value}, headers=headers
        )
        assert response.status_code == 200
    assert client.post(f"/api/me/game/runs/{run_id}/complete", headers=headers).status_code == 200
    client.patch("/api/me/game/consent", json={"share_game_results": True}, headers=headers)


def youth_id(client, headers):
    return client.get("/api/auth/me", headers=headers).get_json()["user"]["id"]


# --- Contenu ---


def test_four_cognitive_games_are_sourced_and_honest(real):
    for instrument_id, trait in GAMES.items():
        instrument = real.instruments[instrument_id]
        assert instrument["kind"] == "performance" and instrument["tier"] == "performance"
        assert instrument["requires"] == ["onboarding"] and instrument["replayable"] is True
        assert instrument["performance"]["trait"] == trait
        assert instrument["performance"]["variant"]
        note = normalize(instrument["scoring_note"])
        assert "pas d'etalonnage" in note and "pas un diagnostic" in note, instrument_id
        assert 2 <= instrument["duration_min"] <= 4
        for source_id in instrument["source_ids"]:
            source = real.sources[source_id]
            assert source["validated"] is False
            assert source["url"].startswith("https://")
    assert real.instruments["logic"]["performance"]["puzzles"]


def test_public_payload_never_contains_the_answer_key(real):
    instrument = real.instruments["logic"]
    public = real.public_instrument(instrument)
    text = json.dumps(public, ensure_ascii=False)
    assert "answer_key" not in text
    for entry in instrument["answer_key"].values():
        assert entry["rule"] not in text
    for puzzle in public["performance"]["puzzles"]:
        assert set(puzzle) <= {"id", "kind", "prompt", "sequence", "grid", "options"}
    for instrument_id in GAMES:
        settings = real.public_instrument(real.instruments[instrument_id])["performance"]
        assert "trait" not in settings and "weight" not in settings


def test_logic_puzzles_are_consistent(real):
    instrument = real.instruments["logic"]
    settings, key = instrument["performance"], instrument["answer_key"]
    practice, puzzles = settings["practice"], settings["puzzles"]
    ids = [puzzle["id"] for puzzle in practice + puzzles]
    assert len(ids) == len(set(ids))
    assert set(key) == {puzzle["id"] for puzzle in puzzles}
    assert {puzzle["kind"] for puzzle in puzzles} == {"series", "matrix"}
    for puzzle in practice + puzzles:
        options = puzzle["options"]
        assert len(options) == 6
        assert len({option["id"] for option in options}) == 6
        contents = [json.dumps(option.get("cell") or option.get("label"), sort_keys=True) for option in options]
        assert len(set(contents)) == 6, f"{puzzle['id']} : deux choix identiques"
        answer = puzzle["answer"] if puzzle in practice else key[puzzle["id"]]["answer"]
        assert answer in {option["id"] for option in options}
        if puzzle["kind"] == "matrix":
            assert len(puzzle["grid"]) == 9 and puzzle["grid"].count(None) == 1
        else:
            assert len(puzzle["sequence"]) >= 4
    for entry in key.values():
        assert entry["level"] in {1, 2, 3} and entry["rule"]
        assert entry["source"]["relation"] == "inspired"
        assert entry["source"]["source_id"] in real.sources
    # Les bonnes réponses ne tombent pas toujours au même endroit.
    assert len({entry["answer"] for entry in key.values()}) >= 4


def test_series_answers_follow_their_rule(real):
    puzzles = {p["id"]: p for p in real.instruments["logic"]["performance"]["puzzles"]}
    key = real.instruments["logic"]["answer_key"]

    def answer(puzzle_id):
        return next(o["label"] for o in puzzles[puzzle_id]["options"] if o["id"] == key[puzzle_id]["answer"])

    assert answer("s1") == str(int(puzzles["s1"]["sequence"][-1]) + 4)
    assert ord(answer("s2")) - ord(puzzles["s2"]["sequence"][-1]) == 3
    assert answer("s3") == "42"  # 2, 6, 12, 20, 30 : n × (n + 1)
    assert answer("s4") == str(int(puzzles["s4"]["sequence"][-1]) - 2)
    assert answer("s5") == chr(ord(puzzles["s5"]["sequence"][-2]) + 2)


def test_matrix_answers_follow_their_rule(real):
    puzzles = {p["id"]: p for p in real.instruments["logic"]["performance"]["puzzles"]}
    key = real.instruments["logic"]["answer_key"]

    def answer(puzzle_id):
        return next(o["cell"] for o in puzzles[puzzle_id]["options"] if o["id"] == key[puzzle_id]["answer"])

    grid = puzzles["m4"]["grid"]
    for row in (0, 3):
        assert grid[row]["count"] + grid[row + 1]["count"] == grid[row + 2]["count"]
    assert answer("m4")["count"] == grid[6]["count"] + grid[7]["count"]

    grid = puzzles["m5"]["grid"]
    for row in (0, 3):
        assert set(grid[row]["lines"]) ^ set(grid[row + 1]["lines"]) == set(grid[row + 2]["lines"])
    assert set(answer("m5")["lines"]) == set(grid[6]["lines"]) ^ set(grid[7]["lines"])

    grid = puzzles["m3"]["grid"][:8] + [answer("m3")]
    for line in range(3):
        row = grid[line * 3 : line * 3 + 3]
        column = grid[line::3]
        for cells in (row, column):
            assert len({cell["shape"] for cell in cells}) == 3
            assert len({cell["fill"] for cell in cells}) == 3

    grid = puzzles["m2"]["grid"][:8] + [answer("m2")]
    for line in range(3):
        angles = [cell["rotate"] for cell in grid[line * 3 : line * 3 + 3]]
        assert all((b - a) % 360 == 90 for a, b in zip(angles, angles[1:]))


def test_corsi_board_and_digit_phases(real):
    corsi = real.instruments["corsi"]["performance"]
    blocks = corsi["blocks"]
    assert [block["id"] for block in blocks] == corsi["symbols"] == list(range(1, 10))
    for block in blocks:
        assert 8 <= block["x"] <= 92 and 8 <= block["y"] <= 92
    for a, b in itertools.combinations(blocks, 2):
        assert math.dist((a["x"], a["y"]), (b["x"], b["y"])) >= 25, (a, b)
    digits = real.instruments["digit_span"]["performance"]
    assert [phase["id"] for phase in digits["phases"]] == ["forward", "backward"]
    assert [phase["backwards"] for phase in digits["phases"]] == [False, True]


def _content_texts(real: Catalog):
    for instrument_id in GAMES:
        instrument = real.instruments[instrument_id]
        for field in YOUTH_FIELDS:
            yield instrument_id, instrument[field]
        settings = instrument["performance"]
        for color in settings.get("colors", []):
            yield instrument_id, color["label"]
        for puzzle in settings.get("puzzles", []) + settings.get("practice", []):
            yield f"{instrument_id}/{puzzle['id']}", puzzle["prompt"]
            yield f"{instrument_id}/{puzzle['id']}", puzzle.get("hint", "")
            for option in puzzle["options"]:
                yield f"{instrument_id}/{puzzle['id']}", option.get("label", "")


def test_youth_texts_of_the_games_respect_guardrails(real):
    # Les textes du front (cognitive.fr.ts) sont relus avec tous les *.fr.ts par test_game_content.
    problems = guardrail_problems(_content_texts(real))
    assert not problems, "\n".join(problems)


# --- Empan ---


def test_span_ignores_a_lying_correct_flag_and_scores_both_phases(real):
    result = score(
        real,
        "digit_span",
        [
            {"phase": "forward", "practice": True, "sequence": [4, 1], "response": [1, 4], "rt_ms": 900},
            {"phase": "forward", "sequence": [1, 2, 3], "response": [1, 2, 3], "rt_ms": 1500},
            {"phase": "forward", "sequence": [1, 2, 3, 4], "response": [1, 2, 3, 4], "rt_ms": 1800},
            {"phase": "forward", "sequence": [1, 2, 3, 4, 5], "response": [1, 2, 3, 4, 5], "rt_ms": 2100},
            {"phase": "forward", "sequence": [5, 2, 8, 1, 9, 3], "response": [5, 2, 8, 9, 1, 3], "correct": True},
            {"phase": "forward", "sequence": [7, 2, 8, 1, 9, 3], "response": [7, 2, 8, 1, 3, 9]},
            {"phase": "backward", "sequence": [3, 8], "response": [8, 3], "rt_ms": 1400},
            {"phase": "backward", "sequence": [3, 8, 1], "response": [1, 8, 3]},
            {"phase": "backward", "sequence": [3, 8, 1, 6], "response": [6, 1, 8, 3]},
            {"phase": "backward", "sequence": [3, 8, 1, 6, 2], "response": [3, 8, 1, 6, 2]},
            {"phase": "backward", "sequence": [4, 8, 1, 6, 2], "response": [2, 6, 1, 4, 8]},
        ],
    )
    metrics = result.metrics
    assert metrics["phases"]["forward"] == {"span": 5, "trials": 5, "correct": 3, "percent": 42.9}
    assert metrics["phases"]["backward"] == {"span": 4, "trials": 5, "correct": 3, "percent": 42.9}
    assert metrics["span"] == 5 and metrics["correct"] == 6 and metrics["practice_trials"] == 1
    assert result.signals == [
        {"trait": "working_memory", "value": 42.86, "weight": 4.0, "tier": "performance"}
    ]
    practice, lying = result.rows[0], result.rows[4]
    assert practice["prompt"] == "Entraînement · Endroit · série de 2 chiffres"
    assert practice["value"]["practice"] is True and practice["label"] == "Différent"
    assert lying["value"]["correct"] is False and lying["label"] == "Différent"
    backward = result.rows[7]
    assert backward["value"]["expected"] == [1, 8, 3] and backward["value"]["correct"] is True
    assert backward["response_ms"] is None


def test_corsi_span_and_percent(real):
    trials = [
        {"sequence": [5, 2], "response": [5, 2], "rt_ms": 1200},
        {"sequence": [5, 2, 9], "response": [5, 2, 9], "rt_ms": 1900},
        {"sequence": [1, 6, 3, 7], "response": [1, 6, 7, 3], "rt_ms": 2600},
        {"sequence": [1, 6, 3, 8], "response": [1, 6, 3, 8], "rt_ms": 2500},
        {"sequence": [1, 6, 3, 8, 4], "response": [1, 6, 3], "rt_ms": 2700},
        {"sequence": [9, 6, 3, 8, 4], "response": [9, 6, 3, 8, 2], "rt_ms": 2700},
    ]
    result = score(real, "corsi", trials)
    assert result.metrics == {"span": 4, "trials": 6, "correct": 3, "percent": 37.5}
    assert result.signals[0]["trait"] == "visuospatial_memory"
    assert result.rows[2]["prompt"] == "Série de 4 lanternes"


@pytest.mark.parametrize(
    "trials",
    [
        [],
        "abc",
        [{"sequence": [1, 10], "response": [1, 10]}],
        [{"sequence": [1, 0], "response": [1, 0]}],
        [{"sequence": [True, 2], "response": [1, 2]}],
        [{"sequence": [1, 2], "response": "12"}],
        [{"sequence": [1], "response": [1]}],
        [{"sequence": [1, 2], "response": [1, 2], "phase": "forward"}],
        [{"sequence": [1, 2], "response": [1, 2]}, {"practice": True, "sequence": [1, 2], "response": [1, 2]}],
        [{"practice": True, "sequence": [1, 2], "response": [1, 2]}] * 3 + [{"sequence": [1, 2], "response": [1, 2]}],
        [{"practice": True, "sequence": [1, 2], "response": [1, 2]}],
    ],
)
def test_corsi_rejects_invalid_trials(real, trials):
    with pytest.raises(InvalidAnswer):
        score(real, "corsi", trials)


def test_digit_span_needs_every_phase_and_known_phases(real):
    forward = {"phase": "forward", "sequence": [1, 2, 3], "response": [1, 2, 3]}
    with pytest.raises(InvalidAnswer):
        score(real, "digit_span", [forward])
    with pytest.raises(InvalidAnswer):
        score(real, "digit_span", [forward, {**forward, "phase": ["backward"]}])
    with pytest.raises(InvalidAnswer):
        score(real, "digit_span", [forward, {**forward, "phase": "sideways"}])


# --- Stroop ---


STROOP_TRIALS = [
    {"practice": True, "word": "rouge", "ink": "vert", "response": "rouge", "rt_ms": 900},
    {"practice": True, "word": "bleu", "ink": "bleu", "response": "bleu", "rt_ms": 800},
    {"word": "rouge", "ink": "rouge", "response": "rouge", "rt_ms": 600, "congruent": False},
    {"word": "vert", "ink": "vert", "response": "vert", "rt_ms": 620},
    {"word": "bleu", "ink": "bleu", "response": "bleu", "rt_ms": 640},
    {"word": "jaune", "ink": "jaune", "response": "jaune", "rt_ms": 660},
    {"word": "rouge", "ink": "bleu", "response": "bleu", "rt_ms": 700},
    {"word": "vert", "ink": "jaune", "response": "jaune", "rt_ms": 760},
    {"word": "bleu", "ink": "rouge", "response": "rouge", "rt_ms": 820},
    {"word": "jaune", "ink": "vert", "response": "jaune", "rt_ms": 500, "correct": True},
    {"word": "rouge", "ink": "vert", "response": "vert", "rt_ms": 3500},
]


def test_stroop_recomputes_congruency_and_correctness(real):
    result = score(real, "stroop", STROOP_TRIALS)
    metrics = result.metrics
    assert metrics["trials"] == 9 and metrics["correct"] == 8 and metrics["accuracy"] == 88.9
    assert metrics["congruent"] == {
        "n": 4, "correct": 4, "accuracy": 100.0, "mean_rt_ms": 630, "median_rt_ms": 630, "rt_n": 4
    }
    assert metrics["incongruent"] == {
        "n": 5, "correct": 4, "accuracy": 80.0, "mean_rt_ms": 760, "median_rt_ms": 760, "rt_n": 3
    }
    assert metrics["interference_ms"] == 130 and metrics["accuracy_gap"] == 20.0
    # précision (8/9 − 1/4) / (3/4) = 85,19 ; résistance 1 − 130/400 = 67,5 %.
    assert metrics["precision"] == 85.2 and metrics["resistance"] == 67.5
    assert metrics["percent"] == 71.3
    assert metrics["best_streak"] == 7 and metrics["fastest_rt_ms"] == 600
    assert metrics["practice_trials"] == 2
    assert result.signals[0]["trait"] == "attention_control"
    assert result.signals[0]["value"] == 71.34

    rows = result.rows
    assert rows[0]["prompt"] == "Entraînement · mot ROUGE écrit en vert · incongruent"
    assert rows[2]["value"]["congruent"] is True
    assert rows[9]["value"] == {
        "word": "jaune", "ink": "vert", "response": "jaune", "congruent": False, "correct": False
    }
    assert rows[9]["label"] == "Erreur : jaune" and rows[9]["response_ms"] == 500


def test_stroop_without_answer_and_formula_bounds(real):
    trials = [{"word": "rouge", "ink": "bleu", "response": None, "rt_ms": 5000}] + [
        {"word": word, "ink": word, "response": word, "rt_ms": 700} for word in ("rouge", "vert", "bleu")
    ]
    result = score(real, "stroop", trials)
    assert result.rows[0]["label"] == "Sans réponse" and result.rows[0]["response_ms"] is None
    # Pas de temps incongruent juste : effet incalculable, résistance neutre.
    assert result.metrics["interference_ms"] is None and result.metrics["resistance"] == 50.0
    assert 0 <= result.metrics["percent"] <= 100

    guess = [{"word": "rouge", "ink": "bleu", "response": "rouge", "rt_ms": 400}] * 8
    assert score(real, "stroop", guess).metrics["percent"] == 0


@pytest.mark.parametrize(
    "trials",
    [
        [{"word": "violet", "ink": "bleu", "response": "bleu"}],
        [{"word": "rouge", "ink": "bleu", "response": ["bleu"]}],
        [{"word": ["rouge"], "ink": "bleu", "response": "bleu"}],
        [{"word": "rouge", "ink": "bleu", "response": "bleu", "practice": True}],
        [{"word": "rouge", "ink": "bleu", "response": "bleu"}, {"word": "rouge", "ink": "bleu", "response": "bleu", "practice": True}],
        [{"word": "rouge", "ink": "bleu", "response": "bleu", "practice": True}] * 5 + [{"word": "rouge", "ink": "bleu", "response": "bleu"}],
        [{"word": "rouge", "ink": "bleu", "response": "bleu"}] * 33,
    ],
)
def test_stroop_rejects_invalid_trials(real, trials):
    with pytest.raises(InvalidAnswer):
        score(real, "stroop", trials)


def test_stroop_sequence_is_balanced_without_repeated_ink():
    colors = ["rouge", "vert", "bleu", "jaune"]
    for seed in range(20):
        pairs = stroop_sequence(colors, 32, random.Random(seed))
        assert len(pairs) == 32
        assert sum(word == ink for word, ink in pairs) == 16
        assert all(a[1] != b[1] for a, b in zip(pairs, pairs[1:]))


# --- Énigmes ---


def _logic_trials(real, answers: dict[str, str | None]) -> list[dict]:
    return [{"puzzle": puzzle_id, "response": response, "rt_ms": 9000} for puzzle_id, response in answers.items()]


def test_logic_uses_the_server_key_only(real):
    key = real.instruments["logic"]["answer_key"]
    answers = {puzzle_id: entry["answer"] for puzzle_id, entry in key.items()}
    perfect = score(real, "logic", _logic_trials(real, answers))
    assert perfect.metrics["solved"] == 10 and perfect.metrics["percent"] == 100.0
    assert perfect.metrics["best_streak"] == 10

    wrong = "a" if key["s1"]["answer"] != "a" else "b"
    trials = _logic_trials(real, {**answers, "s1": wrong, "m5": None})
    trials[0]["correct"] = True
    trials.insert(0, {"puzzle": "p1", "response": "a", "rt_ms": 4000})
    result = score(real, "logic", trials)
    assert result.metrics["solved"] == 8 and result.metrics["percent"] == 80.0
    assert result.metrics["skipped"] == 1 and result.metrics["attempted"] == 9
    assert result.metrics["by_kind"] == {
        "series": {"solved": 4, "total": 5}, "matrix": {"solved": 4, "total": 5}
    }
    assert result.metrics["practice_trials"] == 1
    assert result.signals[0] == {"trait": "reasoning", "value": 80.0, "weight": 4.0, "tier": "performance"}
    practice, lying, skipped = result.rows[0], result.rows[1], result.rows[-1]
    assert practice["value"]["practice"] is True and practice["label"] == "Non résolue"
    assert lying["value"]["correct"] is False and lying["label"] == "Non résolue"
    assert lying["prompt"] == "Suite 3, 7, 11, 15, ? · règle : +4 à chaque pas"
    assert lying["value"]["source"]["relation"] == "inspired"
    assert skipped["label"] == "Passée" and skipped["value"]["response"] is None
    assert skipped["value"]["expected_text"].startswith("traits :")


@pytest.mark.parametrize(
    "trials",
    [
        [{"puzzle": "zz", "response": "a"}],
        [{"puzzle": "s1", "response": "g"}],
        [{"puzzle": "s1", "response": 1}],
        [{"puzzle": ["s1"], "response": "a"}],
        [{"puzzle": "s1", "response": "a"}, {"puzzle": "s1", "response": "b"}],
        [{"puzzle": "p1", "response": "b"}],
    ],
)
def test_logic_rejects_invalid_trials(real, trials):
    with pytest.raises(InvalidAnswer):
        score(real, "logic", trials)


# --- Démo ---


@pytest.mark.parametrize("instrument_id", sorted(GAMES))
def test_demo_trials_are_realistic_and_score(real, instrument_id):
    values = []
    for seed in range(12):
        for skill in (0.6, 0.8, 0.9):
            result = score(real, instrument_id, demo(real, instrument_id, f"{seed}", skill))
            assert 0 <= result.signals[0]["value"] <= 100
            values.append(result.signals[0]["value"])
    assert 15 < sum(values) / len(values) < 97


# --- API ---


def test_games_are_scored_by_the_server_and_visible_to_the_psychologist(client, youth, psychologist, games):
    assert client.post("/api/me/game/instruments/corsi/runs", headers=youth).status_code == 409
    finish_onboarding(client, youth)
    base = f"/api/backoffice/youths/{youth_id(client, youth)}/game"
    for instrument_id, trait in GAMES.items():
        payload = start(client, youth, instrument_id)
        assert payload["instrument"]["performance"]["variant"]
        result = complete(client, youth, payload["run"]["id"], demo(games, instrument_id))
        assert result.status_code == 200, result.get_json()
        body = result.get_json()
        # Le jeune reçoit ses réussites, jamais le pourcentage : il reste à la psychologue.
        assert body["metrics"] and "percent" not in json.dumps(body["metrics"])
        assert body["xp_gained"] >= 80

        detail = client.get(f"{base}/runs/{payload['run']['id']}", headers=psychologist).get_json()
        assert detail["run"]["metrics"]["percent"] is not None
        assert detail["run_signals"][0]["trait"] == trait
        assert detail["instrument"]["sources"] and detail["instrument"]["scoring_note"]
        assert all(row["type"] == "trial" and row["status"] == "answered" for row in detail["answers"])
        assert all(row["value"] is not None and "correct" in row["value"] for row in detail["answers"])
        assert any(row["response_ms"] for row in detail["answers"])

    overview = client.get(base, headers=psychologist).get_json()
    cognitive = next(group for group in overview["cursor_groups"] if group["id"] == "cognitive")
    assert all(cursor["value"] is not None for cursor in cognitive["cursors"])


def test_answer_key_never_reaches_the_youth(client, youth, games):
    finish_onboarding(client, youth)
    text = json.dumps(start(client, youth, "logic")) + json.dumps(client.get("/api/me/game", headers=youth).get_json())
    assert "answer_key" not in text and "reasoning" not in text
    for entry in games.instruments["logic"]["answer_key"].values():
        assert json.dumps(entry["rule"])[1:-1] not in text


def test_invalid_trials_get_400_and_the_run_stays_open(client, youth, games):
    finish_onboarding(client, youth)
    for instrument_id, bad in [
        ("corsi", [{"sequence": [1, 12], "response": [1, 12]}]),
        ("digit_span", [{"phase": "forward", "sequence": [1, 2, 3], "response": [1, 2, 3]}]),
        ("stroop", [{"word": "violet", "ink": "bleu", "response": "bleu"}]),
        ("logic", [{"puzzle": "zz", "response": "a"}]),
    ]:
        run_id = start(client, youth, instrument_id)["run"]["id"]
        response = complete(client, youth, run_id, bad)
        assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_trials"
        assert complete(client, youth, run_id, demo(games, instrument_id)).status_code == 200


def test_demo_youth_plays_the_cognitive_games(app, client, youth, psychologist, games):
    target = youth_id(client, youth)
    with app.app_context():
        user = db.session.get(User, uuid.UUID(target))
        seed_youth_game(user, {"skill": 0.9, "bias": {}, "facts": {}})
    overview = client.get(f"/api/backoffice/youths/{target}/game", headers=psychologist).get_json()
    assert {run["instrument_id"] for run in overview["runs"]} == {"onboarding", *GAMES}
    assert all(run["status"] == "completed" for run in overview["runs"])
    cognitive = next(group for group in overview["cursor_groups"] if group["id"] == "cognitive")
    assert {cursor["id"] for cursor in cognitive["cursors"] if cursor["value"] is not None} == set(
        GAMES.values()
    )


def test_unrelated_youth_cannot_complete_someone_elses_game(client, youth, games):
    finish_onboarding(client, youth)
    run_id = start(client, youth, "stroop")["run"]["id"]
    other = register(client, "Noa")
    assert complete(client, other, run_id, demo(games, "stroop")).status_code == 404

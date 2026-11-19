"""Niveaux de preuve : libellés, poids, et niveau propre à un signal."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.game.catalog import TIER_STRENGTH, TIERS, Catalog, ContentError
from app.game.scoring import TIER_WEIGHTS, aggregate, score_answer
from app.game.service import TIER_LABELS

QUIZ = {"id": "quiz", "kind": "quiz", "tier": "adapted", "scale": {"min": 1, "max": 5}}
GAME_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "game"


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def test_every_tier_has_a_label_and_a_weight():
    assert set(TIER_LABELS) == set(TIER_WEIGHTS) == TIERS | {"talent"}
    assert TIER_LABELS["translated"] == "Test validé, traduction maison non validée"
    assert TIER_LABELS["adapted"] == "Inspiré de travaux publiés, non validé"
    # Une traduction maison compte moins que le test validé, plus qu'une simple inspiration.
    assert TIER_WEIGHTS["validated"] > TIER_WEIGHTS["translated"] == 0.75 > TIER_WEIGHTS["adapted"]


def ts_block(path: Path, start: str, end: str) -> str:
    """Texte d'un fichier TypeScript entre `start` et le premier `end` qui suit."""
    source = path.read_text(encoding="utf-8")
    return source.split(start, 1)[1].split(end, 1)[0]


def test_backoffice_shows_the_tiers_of_the_api():
    # Le front garde une copie des libellés (légende, méthode) et des poids (détail d'un curseur).
    union = ts_block(GAME_FRONT / "types.ts", "export type Tier =", ";")
    assert set(re.findall(r"'(\w+)'", union)) == set(TIER_LABELS)
    labels = ts_block(GAME_FRONT / "backoffice" / "backoffice.fr.ts", "  tiers: {", "}")
    assert dict(re.findall(r"(\w+): '([^']*)'", labels)) == TIER_LABELS
    format_ts = GAME_FRONT / "backoffice" / "format.ts"
    weights = ts_block(format_ts, "export const TIER_WEIGHTS: Record<Tier, number> = {", "}")
    assert {key: float(value) for key, value in re.findall(r"(\w+): ([\d.]+)", weights)} == TIER_WEIGHTS
    order = re.findall(r"'(\w+)'", ts_block(format_ts, "export const TIER_ORDER: Tier[] = [", "]"))
    assert sorted(order) == sorted(TIER_WEIGHTS)
    assert [TIER_WEIGHTS[tier] for tier in order] == sorted(TIER_WEIGHTS.values(), reverse=True)


def test_a_choice_signal_can_carry_its_own_tier():
    item = {
        "id": "q", "type": "choice", "prompt": "?",
        "options": [
            {"id": "a", "label": "A", "signals": [
                {"trait": "riasec_i", "value": 80},
                {"trait": "interest_digital", "value": 70, "weight": 0.5, "tier": "custom"},
            ]},
            {"id": "b", "label": "B", "signals": [{"trait": "riasec_i", "value": 20}]},
        ],
    }
    signals = score_answer(QUIZ, item, "a").signals
    assert [(s["trait"], s["weight"], s["tier"]) for s in signals] == [
        ("riasec_i", 1.0, "adapted"),
        ("interest_digital", 0.5, "custom"),
    ]


def test_a_likert_part_can_carry_its_own_tier():
    several = {
        "id": "l1", "type": "likert", "prompt": "?",
        "traits": [{"trait": "openness"}, {"trait": "interest_digital", "weight": 0.5, "tier": "custom"}],
    }
    assert [s["tier"] for s in score_answer(QUIZ, several, 5).signals] == ["adapted", "custom"]
    single = {"id": "l2", "type": "likert", "prompt": "?", "trait": "openness", "tier": "custom"}
    assert score_answer(QUIZ, single, 5).signals[0]["tier"] == "custom"


def test_a_translated_answer_weighs_three_quarters(catalog):
    rows = [
        {"trait": "openness", "value": 100.0, "weight": 1.0, "tier": "translated"},
        {"trait": "openness", "value": 0.0, "weight": 1.0, "tier": "adapted"},
    ]
    cursor = aggregate(catalog, rows)["openness"]
    # (100 × 0,75 + 0 × 0,5) / (0,75 + 0,5)
    assert cursor["value"] == 60.0
    assert cursor["by_tier"] == {"adapted": {"value": 0.0, "n": 1}, "translated": {"value": 100.0, "n": 1}}


def overlay(tmp_path, item: dict, tier: str = "custom"):
    """Contenu réel plus un instrument d'essai à une seule question."""
    folder = tmp_path / "instruments"
    folder.mkdir()
    instrument = {
        "id": "essai", "version": 1, "kind": "questionnaire", "tier": tier, "title": "t",
        "tagline": "t", "icon": "i", "duration_min": 1, "xp": 1, "scale": {"min": 1, "max": 5},
        "source_ids": [] if tier == "custom" else ["ipip_mini_ipip"],
        "items": [item],
    }
    (folder / "essai.json").write_text(json.dumps(instrument), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "item",
    [
        {"id": "q", "type": "choice", "prompt": "?", "options": [
            {"id": "a", "label": "A", "signals": [{"trait": "openness", "value": 50, "tier": "officiel"}]},
            {"id": "b", "label": "B"},
        ]},
        {"id": "q", "type": "likert", "prompt": "?", "trait": "openness", "tier": "officiel"},
        {"id": "q", "type": "likert", "prompt": "?", "traits": [{"trait": "openness", "tier": "officiel"}]},
    ],
    ids=["choice", "likert", "likert_traits"],
)
def test_catalog_rejects_an_unknown_signal_tier(tmp_path, item):
    with pytest.raises(ContentError, match="niveau de preuve inconnu"):
        Catalog(overlays=[overlay(tmp_path, item)])


def test_every_tier_has_a_strength():
    assert set(TIER_STRENGTH) == TIERS
    # Même ordre que les poids : un niveau plus solide ne pèse jamais moins.
    ranked = sorted(TIERS, key=TIER_STRENGTH.get)
    assert [TIER_WEIGHTS[tier] for tier in ranked] == sorted(TIER_WEIGHTS[tier] for tier in ranked)


@pytest.mark.parametrize(
    ("instrument_tier", "signal_tier"),
    [("validated", "translated"), ("translated", "adapted"), ("adapted", "custom"), ("custom", "custom")],
)
def test_a_signal_may_lower_the_tier_of_its_instrument(tmp_path, instrument_tier, signal_tier):
    item = {"id": "q", "type": "likert", "prompt": "?", "trait": "openness", "tier": signal_tier}
    assert "essai" in Catalog(overlays=[overlay(tmp_path, item, instrument_tier)]).instruments


@pytest.mark.parametrize(
    ("instrument_tier", "signal_tier"),
    [("custom", "adapted"), ("custom", "translated"), ("adapted", "translated"), ("adapted", "validated")],
)
def test_a_signal_may_not_raise_the_tier_of_its_instrument(tmp_path, instrument_tier, signal_tier):
    # Une question maison ne peut pas se présenter comme un test validé à la psychologue.
    item = {"id": "q", "type": "choice", "prompt": "?", "options": [
        {"id": "a", "label": "A", "signals": [{"trait": "openness", "value": 50, "tier": signal_tier}]},
        {"id": "b", "label": "B"},
    ]}
    with pytest.raises(ContentError, match="plus solide que celui de l'instrument"):
        Catalog(overlays=[overlay(tmp_path, item, instrument_tier)])


# --- Quiz d'arrivée : l'indicateur maison garde son propre niveau ---


def quiz_signals(catalog):
    quiz = catalog.instruments["onboarding"]
    return [
        signal
        for item in quiz["items"]
        for option in item.get("options", [])
        for signal in option.get("signals", [])
    ]


def test_quiz_digital_signals_are_marked_as_in_house(catalog):
    signals = quiz_signals(catalog)
    digital = [s for s in signals if s["trait"] == "interest_digital"]
    assert len(digital) >= 8
    assert all(s.get("tier") == "custom" and s.get("weight") == 0.5 for s in digital), digital
    # Les autres signaux gardent le niveau du quiz.
    assert all("tier" not in s for s in signals if s["trait"] != "interest_digital")


def test_psychologist_sees_the_in_house_label_on_quiz_digital_signals(client, youth, psychologist):
    run_id = client.post("/api/me/game/instruments/onboarding/runs", headers=youth).get_json()["run"]["id"]
    response = client.put(
        f"/api/me/game/runs/{run_id}/answers/reveil_chaine", json={"value": "a"}, headers=youth
    )
    assert response.status_code == 200, response.get_json()
    target = client.get("/api/auth/me", headers=youth).get_json()["user"]["id"]
    base = f"/api/backoffice/youths/{target}/game"

    digital = client.get(f"{base}/traits/interest_digital", headers=psychologist).get_json()
    assert [(row["tier"], row["tier_label"], row["weight"]) for row in digital["signals"]] == [
        ("custom", "Indicateur maison", 0.5)
    ]
    assert digital["cursor"]["by_tier"]["custom"]["label"] == "Indicateur maison"
    artistic = client.get(f"{base}/traits/riasec_a", headers=psychologist).get_json()
    assert [(row["tier"], row["tier_label"]) for row in artistic["signals"]] == [
        ("adapted", "Inspiré de travaux publiés, non validé")
    ]
    run = client.get(f"{base}/runs/{run_id}", headers=psychologist).get_json()
    assert run["instrument"]["tier_label"] == "Inspiré de travaux publiés, non validé"

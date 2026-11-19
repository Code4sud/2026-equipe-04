"""Niveaux de preuve : libellés, poids, et niveau propre à un signal."""
from __future__ import annotations

import json

import pytest

from app.game.catalog import TIERS, Catalog, ContentError
from app.game.scoring import TIER_WEIGHTS, aggregate, score_answer
from app.game.service import TIER_LABELS

QUIZ = {"id": "quiz", "kind": "quiz", "tier": "adapted", "scale": {"min": 1, "max": 5}}


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def test_every_tier_has_a_label_and_a_weight():
    assert set(TIER_LABELS) == set(TIER_WEIGHTS) == TIERS | {"talent"}
    assert TIER_LABELS["translated"] == "Test validé, traduction maison non validée"
    assert TIER_LABELS["adapted"] == "Inspiré de travaux publiés, non validé"
    # Une traduction maison compte moins que le test validé, plus qu'une simple inspiration.
    assert TIER_WEIGHTS["validated"] > TIER_WEIGHTS["translated"] == 0.75 > TIER_WEIGHTS["adapted"]


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


def overlay(tmp_path, item: dict):
    """Contenu réel plus un instrument d'essai à une seule question."""
    folder = tmp_path / "instruments"
    folder.mkdir()
    instrument = {
        "id": "essai", "version": 1, "kind": "questionnaire", "tier": "custom", "title": "t",
        "tagline": "t", "icon": "i", "duration_min": 1, "xp": 1, "scale": {"min": 1, "max": 5},
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


def test_catalog_accepts_a_known_signal_tier(tmp_path):
    item = {"id": "q", "type": "likert", "prompt": "?", "trait": "openness", "tier": "translated"}
    assert "essai" in Catalog(overlays=[overlay(tmp_path, item)]).instruments

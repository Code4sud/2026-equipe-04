"""Correction des jeux chronométrés.

Le navigateur envoie chaque essai, et le serveur recalcule lui-même ce qui est juste.
Pour ajouter un jeu : écrire `score` et `demo`, puis l'inscrire dans SCORERS.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from .scoring import InvalidAnswer, signal

MAX_TRIALS = 200


@dataclass
class PerformanceResult:
    metrics: dict
    signals: list[dict]
    # Une ligne par essai : item_id, prompt, value, label, response_ms.
    rows: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Scorer:
    score: Callable[[dict, list[dict]], PerformanceResult]
    demo: Callable[[dict, random.Random, float], list[dict]]


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def response_time(trial: dict) -> int | None:
    value = trial.get("rt_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, min(int(value), 600_000))


def check_trials(trials) -> list[dict]:
    if not isinstance(trials, list) or not trials or len(trials) > MAX_TRIALS:
        raise InvalidAnswer("Liste d'essais invalide.")
    if any(not isinstance(trial, dict) for trial in trials):
        raise InvalidAnswer("Essai invalide.")
    return trials


def score_span(instrument: dict, trials: list[dict]) -> PerformanceResult:
    """Empan : plus longue série restituée sans erreur (à l'endroit ou à l'envers)."""
    settings = instrument["performance"]
    backwards = settings.get("backwards", False)
    low, high = settings.get("min_span", 2), settings.get("max_span", 9)
    best = 0
    correct_count = 0
    rows = []
    for index, trial in enumerate(check_trials(trials), start=1):
        sequence, response = trial.get("sequence"), trial.get("response")
        if not isinstance(sequence, list) or not isinstance(response, list) or len(sequence) > 30:
            raise InvalidAnswer("Essai invalide.")
        expected = list(reversed(sequence)) if backwards else sequence
        correct = response == expected
        if correct:
            correct_count += 1
            best = max(best, len(sequence))
        rows.append(
            {
                "item_id": f"essai-{index:03d}",
                "prompt": f"Série de {len(sequence)} éléments",
                "value": {"sequence": sequence, "response": response, "correct": correct},
                "label": "Exact" if correct else "Différent",
                "response_ms": response_time(trial),
            }
        )
    value = clamp_percent((best - low + 1) / (high - low + 1) * 100) if best else 0.0
    metrics = {"span": best, "trials": len(rows), "correct": correct_count, "percent": round(value, 1)}
    return PerformanceResult(
        metrics,
        [signal(settings["trait"], value, settings.get("weight", 4), instrument["tier"])],
        rows,
    )


def demo_span(instrument: dict, rng: random.Random, skill: float) -> list[dict]:
    settings = instrument["performance"]
    low, high = settings.get("min_span", 2), settings.get("max_span", 9)
    trials = []
    for length in range(low, high + 1):
        sequence = [rng.randrange(9) for _ in range(length)]
        success = rng.random() < skill ** max(1, length - low)
        expected = list(reversed(sequence)) if settings.get("backwards") else list(sequence)
        response = expected if success else expected[:-1] + [(expected[-1] + 1) % 9]
        trials.append({"sequence": sequence, "response": response, "rt_ms": 700 * length})
        if not success:
            break
    return trials


SCORERS: dict[str, Scorer] = {"span": Scorer(score_span, demo_span)}

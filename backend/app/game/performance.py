"""Correction des jeux chronométrés.

Le navigateur envoie chaque essai, et le serveur recalcule lui-même ce qui est juste :
un champ `correct` venu du navigateur est toujours ignoré.
Les essais d'entraînement (`practice`) restent visibles pour la psychologue mais ne comptent pas.
Pour ajouter un jeu : écrire `score` et `demo`, puis l'inscrire dans SCORERS. Le jeune ne reçoit
que la projection `youth` des mesures (par défaut : sans aucun pourcentage) ; la psychologue
voit tout.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Callable

from .scoring import InvalidAnswer, signal

MAX_TRIALS = 200
MAX_SEQUENCE = 30
PRACTICE_LABEL = "Entraînement"


@dataclass
class PerformanceResult:
    metrics: dict
    signals: list[dict]
    # Une ligne par essai : item_id, prompt, value, label, response_ms.
    rows: list[dict] = field(default_factory=list)


def drop_percents(metrics: dict) -> dict:
    """Projection par défaut pour le jeune : les mesures sans pourcentage, global ou par phase."""
    youth = {key: value for key, value in metrics.items() if key != "percent"}
    if isinstance(metrics.get("phases"), dict):
        youth["phases"] = {
            phase_id: {k: v for k, v in entry.items() if k != "percent"}
            if isinstance(entry, dict)
            else entry
            for phase_id, entry in metrics["phases"].items()
        }
    return youth


@dataclass(frozen=True)
class Scorer:
    score: Callable[[dict, list[dict]], PerformanceResult]
    demo: Callable[[dict, random.Random, float], list[dict]]
    # Ce que le jeune reçoit en fin de partie (frontend/src/game/cognitive/results.ts).
    youth: Callable[[dict], dict] = drop_percents


def youth_metrics(instrument: dict, metrics: dict | None) -> dict:
    """Mesures montrées au jeune : ses réussites, jamais un pourcentage ni un score bas."""
    scorer = SCORERS.get(instrument.get("performance", {}).get("scorer"))
    if scorer is None or not metrics:
        return {}
    return drop_percents(scorer.youth(metrics))


def keep_only(*keys: str) -> Callable[[dict], dict]:
    return lambda metrics: {key: metrics[key] for key in keys if key in metrics}


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def finite_ms(value) -> int | None:
    """Durée en millisecondes, ou None si elle n'est pas un nombre fini (NaN, Infinity, 1e400)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return max(0, min(int(value), 600_000))


def response_time(trial: dict) -> int | None:
    return finite_ms(trial.get("rt_ms"))


def check_trials(trials) -> list[dict]:
    if not isinstance(trials, list) or not trials or len(trials) > MAX_TRIALS:
        raise InvalidAnswer("Liste d'essais invalide.")
    if any(not isinstance(trial, dict) for trial in trials):
        raise InvalidAnswer("Essai invalide.")
    return trials


def is_practice(trial: dict) -> bool:
    return trial.get("practice") is True


def prompt_of(*parts: str) -> str:
    text = " · ".join(part for part in parts if part)
    return text[:1].upper() + text[1:]


def best_streak(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


class PracticeGate:
    """L'entraînement vient avant les essais comptés, et en nombre limité.

    Sans cette règle, un navigateur pourrait cacher ses erreurs en les marquant « entraînement ».
    """

    def __init__(self, limit: int):
        self.limit = limit
        self.counts: dict[object, int] = {}
        self.started: set[object] = set()

    def check(self, group: object, practice: bool) -> None:
        if not practice:
            self.started.add(group)
            return
        if group in self.started:
            raise InvalidAnswer("Entraînement après le début de la partie.")
        self.counts[group] = self.counts.get(group, 0) + 1
        if self.counts[group] > self.limit:
            raise InvalidAnswer("Trop d'essais d'entraînement.")

    @property
    def total(self) -> int:
        return sum(self.counts.values())


# --- Empan (chiffres, blocs de Corsi) ---


def span_phases(settings: dict) -> list[dict]:
    """Une épreuve d'empan a une seule phase (réglages de premier niveau) ou plusieurs (`phases`)."""
    if settings.get("phases"):
        return settings["phases"]
    return [
        {
            "id": None,
            "backwards": settings.get("backwards", False),
            "min_span": settings.get("min_span", 2),
            "max_span": settings.get("max_span", 9),
        }
    ]


def _symbol_check(settings: dict) -> Callable[[object], bool]:
    allowed = settings.get("symbols")
    if allowed is None:
        return lambda v: (
            isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 100
        ) or (isinstance(v, str) and 0 < len(v) <= 3)
    return lambda v: isinstance(v, (int, str)) and not isinstance(v, bool) and v in allowed


def span_percent(best: int, low: int, high: int) -> float:
    """0 sans série exacte, sinon de 1 / (nombre de longueurs) × 100 à 100 pour la longueur maximale."""
    return clamp_percent((best - low + 1) / (high - low + 1) * 100) if best else 0.0


def score_span(instrument: dict, trials: list[dict]) -> PerformanceResult:
    """Empan : plus longue série restituée sans erreur, à l'endroit ou à l'envers, phase par phase.

    Pourcentage d'une phase = (empan − longueur de départ + 1) / (longueur max − départ + 1) × 100 ;
    curseur = moyenne des phases.
    """
    settings = instrument["performance"]
    phases = span_phases(settings)
    by_id = {phase["id"]: phase for phase in phases}
    valid = _symbol_check(settings)
    unit = settings.get("unit", "éléments")
    gate = PracticeGate(settings.get("practice_max", 2))
    stats = {phase["id"]: {"span": 0, "trials": 0, "correct": 0} for phase in phases}
    rows = []
    for index, trial in enumerate(check_trials(trials), start=1):
        phase_id = trial.get("phase")
        if phase_id is not None and not isinstance(phase_id, str):
            raise InvalidAnswer("Phase inconnue.")
        phase = by_id.get(phase_id)
        sequence, response = trial.get("sequence"), trial.get("response")
        if (
            phase is None
            or not isinstance(sequence, list)
            or not isinstance(response, list)
            or not sequence
            or len(sequence) > MAX_SEQUENCE
            or len(response) > MAX_SEQUENCE
            or not all(map(valid, sequence))
            or not all(map(valid, response))
        ):
            raise InvalidAnswer("Essai invalide.")
        practice = is_practice(trial)
        gate.check(phase_id, practice)
        if not practice and not phase["min_span"] <= len(sequence) <= phase["max_span"]:
            raise InvalidAnswer("Longueur de série hors des réglages.")

        expected = list(reversed(sequence)) if phase.get("backwards") else list(sequence)
        correct = response == expected
        if not practice:
            entry = stats[phase_id]
            entry["trials"] += 1
            if correct:
                entry["correct"] += 1
                entry["span"] = max(entry["span"], len(sequence))
        value = {"sequence": sequence, "response": response, "correct": correct}
        if phase.get("backwards"):
            value["expected"] = expected
        if phase_id is not None:
            value["phase"] = phase_id
        if practice:
            value["practice"] = True
        rows.append(
            {
                "item_id": f"essai-{index:03d}",
                "prompt": prompt_of(
                    PRACTICE_LABEL if practice else "",
                    phase.get("label", ""),
                    f"série de {len(sequence)} {unit}",
                ),
                "value": value,
                "label": "Exact" if correct else "Différent",
                "response_ms": response_time(trial),
            }
        )
    if any(entry["trials"] == 0 for entry in stats.values()):
        raise InvalidAnswer("Aucun essai compté pour une des phases.")

    percents = []
    for phase in phases:
        entry = stats[phase["id"]]
        percent = span_percent(entry["span"], phase["min_span"], phase["max_span"])
        entry["percent"] = round(percent, 1)
        percents.append(percent)
    value = sum(percents) / len(percents)
    metrics = {
        "span": max(entry["span"] for entry in stats.values()),
        "trials": sum(entry["trials"] for entry in stats.values()),
        "correct": sum(entry["correct"] for entry in stats.values()),
        "percent": round(value, 1),
    }
    if settings.get("phases"):
        metrics["phases"] = {phase["id"]: stats[phase["id"]] for phase in phases}
    if gate.total:
        metrics["practice_trials"] = gate.total
    return PerformanceResult(
        metrics,
        [signal(settings["trait"], value, settings.get("weight", 4), instrument["tier"])],
        rows,
    )


def _span_mistake(expected: list, pool: list, rng: random.Random) -> list:
    response = list(expected)
    if len(response) >= 2 and rng.random() < 0.6:
        position = rng.randrange(len(response) - 1)
        response[position], response[position + 1] = response[position + 1], response[position]
        if response != expected:
            return response
    position = rng.randrange(len(response))
    response[position] = rng.choice([symbol for symbol in pool if symbol != expected[position]])
    return response


def demo_span(instrument: dict, rng: random.Random, skill: float) -> list[dict]:
    """Suit la procédure adaptative du jeu : +1 après une réussite, arrêt après 2 erreurs."""
    settings = instrument["performance"]
    pool = list(settings.get("symbols") or range(9))
    trials = []
    for phase in span_phases(settings):
        low, high = phase["min_span"], phase["max_span"]
        target = low + (high - low) * 0.65 * skill + rng.uniform(-0.8, 0.8)
        extra = {"phase": phase["id"]} if phase["id"] is not None else {}

        def trial(length: int, success: bool, practice: bool = False) -> dict:
            if length <= len(pool):
                sequence = rng.sample(pool, length)
            else:
                sequence = [rng.choice(pool) for _ in range(length)]
            expected = sequence[::-1] if phase.get("backwards") else list(sequence)
            response = expected if success else _span_mistake(expected, pool, rng)
            rt = int(length * rng.uniform(550, 950) + rng.uniform(400, 1200))
            row = {**extra, "sequence": sequence, "response": response, "rt_ms": rt}
            return {**row, "practice": True} if practice else row

        if settings.get("practice_span"):
            trials.append(trial(settings["practice_span"], True, practice=True))
        length, failures = low, 0
        while True:
            success = rng.random() < 1 / (1 + math.exp(2 * (length - target)))
            trials.append(trial(length, success))
            if success:
                if length >= high:
                    break
                length, failures = length + 1, 0
            else:
                failures += 1
                if failures == 2:
                    break
    return trials


# --- Stroop ---


def stroop_sequence(
    colors: list[str], count: int, rng: random.Random, congruent_ratio: float = 0.5
) -> list[tuple[str, str]]:
    """Paires (mot, encre) équilibrées : chaque encre autant de fois, la part voulue d'essais
    congruents répartie entre les couleurs, et jamais la même encre deux fois de suite.
    Même règle que le navigateur (frontend/src/game/cognitive/stroop/sequence.ts)."""
    size = len(colors)
    inks = [colors[i % size] for i in range(count - count % size)] + rng.sample(colors, count % size)
    slots = rng.sample(range(count), count)
    by_ink = {color: [i for i in slots if inks[i] == color] for color in colors}
    target = min(count, round(count * congruent_ratio))
    congruent: set[int] = set()
    cycle = rng.sample(colors, size)
    while len(congruent) < target:
        for color in cycle:
            if by_ink[color] and len(congruent) < target:
                congruent.add(by_ink[color].pop())
    turn = {color: rng.randrange(size - 1) for color in colors}
    pool = []
    for index, ink in enumerate(inks):
        if index in congruent:
            pool.append((ink, ink))
            continue
        others = [color for color in colors if color != ink]
        pool.append((others[turn[ink] % len(others)], ink))
        turn[ink] += 1
    for _ in range(500):
        remaining, order = list(pool), []
        while remaining:
            last = order[-1][1] if order else None
            choices = [i for i, pair in enumerate(remaining) if pair[1] != last]
            if not choices:
                break
            order.append(remaining.pop(rng.choice(choices)))
        if not remaining:
            return order
    return pool


def _stroop_condition(entries: list[dict], rt_min: int, rt_max: int) -> dict:
    good = [entry for entry in entries if entry["correct"]]
    times = [e["rt"] for e in good if e["rt"] is not None and rt_min <= e["rt"] <= rt_max]
    return {
        "n": len(entries),
        "correct": len(good),
        "accuracy": round(len(good) / len(entries) * 100, 1) if entries else None,
        "mean_rt_ms": round(mean(times)) if times else None,
        "median_rt_ms": round(median(times)) if times else None,
        "rt_n": len(times),
    }


def score_stroop(instrument: dict, trials: list[dict]) -> PerformanceResult:
    """Nommer l'encre et pas le mot. Congruence et justesse sont recalculées ici.

    précision = (exactitude − hasard) / (1 − hasard), le hasard valant 1 / nombre de couleurs ;
    résistance = 1 − effet de congruence / échelle, bornée entre 0 et 1 (0,5 si incalculable) ;
    curseur = précision × (0,5 + 0,5 × résistance) × 100.
    """
    settings = instrument["performance"]
    labels = {color["id"]: color["label"] for color in settings["colors"]}
    rt_min, rt_max = settings.get("rt_min_ms", 200), settings.get("rt_max_ms", 3000)
    scale = settings.get("interference_scale_ms", 400)
    limit = settings.get("trials")
    gate = PracticeGate(settings.get("practice_trials", 4))
    rows, scored = [], []
    for index, trial in enumerate(check_trials(trials), start=1):
        word, ink, response = trial.get("word"), trial.get("ink"), trial.get("response")
        if (
            not isinstance(word, str)
            or not isinstance(ink, str)
            or word not in labels
            or ink not in labels
            or (response is not None and (not isinstance(response, str) or response not in labels))
        ):
            raise InvalidAnswer("Essai invalide.")
        practice = is_practice(trial)
        gate.check("stroop", practice)
        congruent = word == ink
        correct = response == ink
        rt = response_time(trial) if response is not None else None
        value = {"word": word, "ink": ink, "response": response, "congruent": congruent, "correct": correct}
        if practice:
            value["practice"] = True
        else:
            scored.append({"congruent": congruent, "correct": correct, "rt": rt})
        if response is None:
            label = "Sans réponse"
        else:
            label = "Juste" if correct else f"Erreur : {labels[response].lower()}"
        rows.append(
            {
                "item_id": f"essai-{index:03d}",
                "prompt": prompt_of(
                    PRACTICE_LABEL if practice else "",
                    f"mot {labels[word].upper()} écrit en {labels[ink].lower()}",
                    "congruent" if congruent else "incongruent",
                ),
                "value": value,
                "label": label,
                "response_ms": rt,
            }
        )
    if not scored:
        raise InvalidAnswer("Aucun essai compté.")
    if limit and len(scored) > limit:
        raise InvalidAnswer("Trop d'essais.")

    congruent = _stroop_condition([e for e in scored if e["congruent"]], rt_min, rt_max)
    incongruent = _stroop_condition([e for e in scored if not e["congruent"]], rt_min, rt_max)
    interference = (
        incongruent["mean_rt_ms"] - congruent["mean_rt_ms"]
        if congruent["mean_rt_ms"] is not None and incongruent["mean_rt_ms"] is not None
        else None
    )
    correct_count = sum(entry["correct"] for entry in scored)
    accuracy = correct_count / len(scored)
    chance = 1 / len(labels)
    precision = clamp_percent((accuracy - chance) / (1 - chance) * 100)
    if interference is None:
        resistance = 50.0
    else:
        resistance = clamp_percent((1 - max(0, interference) / scale) * 100)
    value = precision * (0.5 + 0.5 * resistance / 100)
    fastest = [
        entry["rt"]
        for entry in scored
        if entry["correct"] and entry["rt"] is not None and rt_min <= entry["rt"] <= rt_max
    ]
    gap = (
        round(congruent["accuracy"] - incongruent["accuracy"], 1)
        if congruent["accuracy"] is not None and incongruent["accuracy"] is not None
        else None
    )
    metrics = {
        "trials": len(scored),
        "correct": correct_count,
        "accuracy": round(accuracy * 100, 1),
        "congruent": congruent,
        "incongruent": incongruent,
        "interference_ms": interference,
        "accuracy_gap": gap,
        "precision": round(precision, 1),
        "resistance": round(resistance, 1),
        "percent": round(value, 1),
        "best_streak": best_streak([entry["correct"] for entry in scored]),
        "fastest_rt_ms": min(fastest) if fastest else None,
        "rt_window_ms": [rt_min, rt_max],
    }
    if gate.total:
        metrics["practice_trials"] = gate.total
    return PerformanceResult(
        metrics,
        [signal(settings["trait"], value, settings.get("weight", 4), instrument["tier"])],
        rows,
    )


def _stroop_demo_trial(
    word: str, ink: str, colors: list[str], rng: random.Random, skill: float
) -> dict:
    congruent = word == ink
    accuracy = 0.93 + 0.06 * skill if congruent else 0.78 + 0.18 * skill
    base = 1150 - 420 * skill
    rt = rng.gauss(base, 100) if congruent else rng.gauss(base + 280 - 180 * skill, 130)
    if rng.random() < accuracy:
        response = ink
    else:
        # L'erreur typique : lire le mot au lieu de regarder l'encre.
        reading = not congruent and rng.random() < 0.7
        response = word if reading else rng.choice([c for c in colors if c != ink])
        rt *= 0.92
    return {"word": word, "ink": ink, "response": response, "rt_ms": int(max(320, rt))}


def demo_stroop(instrument: dict, rng: random.Random, skill: float) -> list[dict]:
    settings = instrument["performance"]
    colors = [color["id"] for color in settings["colors"]]
    trials = [
        {**_stroop_demo_trial(word, ink, colors, rng, skill), "practice": True}
        for word, ink in stroop_sequence(colors, settings.get("practice_trials", 4), rng)
    ]
    sequence = stroop_sequence(
        colors, settings.get("trials", 32), rng, settings.get("congruent_ratio", 0.5)
    )
    trials += [_stroop_demo_trial(word, ink, colors, rng, skill) for word, ink in sequence]
    return trials


# --- Énigmes (suites et matrices) ---

SHAPE_NAMES = {
    "circle": "rond",
    "square": "carré",
    "triangle": "triangle",
    "diamond": "losange",
    "star": "étoile",
    "hexagon": "hexagone",
    "arrow": "flèche",
}
FILL_NAMES = {"full": "fond plein", "empty": "fond vide", "striped": "fond rayé"}
LINE_NAMES = {"h": "horizontal", "v": "vertical", "d1": "diagonale ↘", "d2": "diagonale ↗"}
DIRECTIONS = {0: "vers le haut", 90: "vers la droite", 180: "vers le bas", 270: "vers la gauche"}
KIND_LABELS = {"series": "Suite", "matrix": "Matrice 3×3"}


def describe_cell(cell: dict | None) -> str:
    """Décrit une case de matrice en mots, pour la psychologue qui ne voit pas le dessin."""
    if not cell:
        return "?"
    if "lines" in cell:
        names = [LINE_NAMES.get(line, line) for line in cell["lines"]]
        return "traits : " + (", ".join(names) or "aucun")
    shape = cell.get("shape")
    text = f"{cell.get('count', 1)} × {SHAPE_NAMES.get(shape, shape)}"
    if shape == "arrow":
        angle = cell.get("rotate", 0) % 360
        text += " " + DIRECTIONS.get(angle, f"à {angle}°")
    fill = cell.get("fill", "full")
    return f"{text}, {FILL_NAMES.get(fill, fill)}"


def describe_option(puzzle: dict, option_id: str | None) -> str | None:
    option = next((o for o in puzzle["options"] if o["id"] == option_id), None)
    if option is None:
        return None
    return option["label"] if "label" in option else describe_cell(option.get("cell"))


def score_logic(instrument: dict, trials: list[dict]) -> PerformanceResult:
    """Énigmes à choix : la clé de correction (`answer_key`) ne quitte jamais le serveur.

    Curseur = énigmes résolues / nombre d'énigmes du jeu × 100.
    """
    settings = instrument["performance"]
    key = instrument["answer_key"]
    puzzles = {puzzle["id"]: puzzle for puzzle in settings["puzzles"]}
    practice = {puzzle["id"]: puzzle for puzzle in settings.get("practice", [])}
    seen: set[str] = set()
    rows, results = [], []
    for index, trial in enumerate(check_trials(trials), start=1):
        puzzle_id = trial.get("puzzle")
        if (
            not isinstance(puzzle_id, str)
            or puzzle_id in seen
            or (puzzle_id not in puzzles and puzzle_id not in practice)
        ):
            raise InvalidAnswer("Énigme inconnue ou déjà jouée.")
        seen.add(puzzle_id)
        training = puzzle_id in practice
        puzzle = practice[puzzle_id] if training else puzzles[puzzle_id]
        response = trial.get("response")
        if response is not None and (
            not isinstance(response, str) or response not in {o["id"] for o in puzzle["options"]}
        ):
            raise InvalidAnswer("Réponse inconnue.")
        entry = puzzle if training else key[puzzle_id]
        expected = entry["answer"]
        correct = response == expected
        rt = response_time(trial)
        value = {
            "puzzle": puzzle_id,
            "kind": puzzle["kind"],
            "response": response,
            "response_text": describe_option(puzzle, response),
            "expected": expected,
            "expected_text": describe_option(puzzle, expected),
            "correct": correct,
        }
        if training:
            value["practice"] = True
        else:
            value["level"] = entry.get("level")
            if entry.get("source"):
                value["source"] = entry["source"]
            results.append(
                {"kind": puzzle["kind"], "correct": correct, "answered": response is not None, "rt": rt}
            )
        stimulus = ", ".join(puzzle["sequence"]) + ", ?" if puzzle.get("sequence") else ""
        rows.append(
            {
                "item_id": puzzle_id,
                "prompt": prompt_of(
                    PRACTICE_LABEL if training else "",
                    f"{KIND_LABELS.get(puzzle['kind'], puzzle['kind'])} {stimulus}".strip(),
                    f"règle : {entry['rule']}" if entry.get("rule") else "",
                ),
                "value": value,
                "label": "Passée" if response is None else "Résolue" if correct else "Non résolue",
                "response_ms": rt,
            }
        )
    if not results:
        raise InvalidAnswer("Aucune énigme comptée.")

    solved = sum(result["correct"] for result in results)
    total = len(puzzles)
    value = clamp_percent(solved / total * 100)
    by_kind: dict[str, dict] = {}
    for puzzle in puzzles.values():
        by_kind.setdefault(puzzle["kind"], {"solved": 0, "total": 0})["total"] += 1
    for result in results:
        by_kind[result["kind"]]["solved"] += result["correct"]
    times = [result["rt"] for result in results if result["answered"] and result["rt"] is not None]
    metrics = {
        "solved": solved,
        "attempted": sum(result["answered"] for result in results),
        "skipped": sum(not result["answered"] for result in results),
        "total": total,
        "percent": round(value, 1),
        "by_kind": by_kind,
        "best_streak": best_streak([result["correct"] for result in results]),
        "mean_rt_ms": round(mean(times)) if times else None,
    }
    training_count = sum(1 for puzzle_id in seen if puzzle_id in practice)
    if training_count:
        metrics["practice_trials"] = training_count
    return PerformanceResult(
        metrics,
        [signal(settings["trait"], value, settings.get("weight", 4), instrument["tier"])],
        rows,
    )


def demo_logic(instrument: dict, rng: random.Random, skill: float) -> list[dict]:
    settings = instrument["performance"]
    key = instrument["answer_key"]
    trials = [
        {
            "puzzle": puzzle["id"],
            "response": puzzle["answer"],
            "rt_ms": rng.randint(5000, 14000),
            "practice": True,
        }
        for puzzle in settings.get("practice", [])
    ]
    for puzzle in settings["puzzles"]:
        level = key[puzzle["id"]].get("level", 2)
        answer = key[puzzle["id"]]["answer"]
        chance = max(0.1, min(0.97, skill * 1.1 - 0.17 * (level - 1)))
        if rng.random() < 0.04:
            response = None
        elif rng.random() < chance:
            response = answer
        else:
            response = rng.choice([o["id"] for o in puzzle["options"] if o["id"] != answer])
        rt = int(rng.uniform(7000, 16000) * (1 + 0.35 * (level - 1)))
        trials.append({"puzzle": puzzle["id"], "response": response, "rt_ms": rt})
    return trials


SCORERS: dict[str, Scorer] = {
    # Empan : record, séries réussies et record par phase, sans les pourcentages.
    "span": Scorer(score_span, demo_span),
    # Stroop : meilleure série et réponse la plus rapide ; précision et interférence restent
    # à la psychologue.
    "stroop": Scorer(
        score_stroop, demo_stroop, keep_only("trials", "best_streak", "fastest_rt_ms", "practice_trials")
    ),
    # Énigmes : nombre d'énigmes résolues et meilleure série, sans le total ni le détail par type.
    "logic": Scorer(score_logic, demo_logic, keep_only("solved", "best_streak", "practice_trials")),
}

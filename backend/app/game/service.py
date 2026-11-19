"""Règles du jeu : parties, réponses, progression, fiche du jeune et vue psychologue.

Le jeune accepte à l'inscription que ses données soient transmises au Centre des Possibles
et à sa psychologue : tout ce qui est joué ici lui est visible, modifications comprises
(voir events.py).

Une partie se modifie toujours sous verrou (SELECT ... FOR UPDATE sur la partie) : une réponse
ne peut pas arriver dans une partie déjà terminée, et deux envois de la même réponse donnent
le même résultat qu'un seul.
"""
from __future__ import annotations

import math
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..errors import ApiError
from ..extensions import db
from ..models import (
    GameAnswer,
    GameFact,
    GameRun,
    GameRunStatus,
    Skill,
    SkillOrigin,
    SkillStatus,
    TraitFeedback,
    User,
    iso,
    utcnow,
)
from ..services import service
from . import events
from .catalog import ARCHETYPE_TEXTS, BALANCED_POLE, FACT_KEY, Catalog
from .discovery import reveal_with
from .performance import SCORERS, finite_ms, youth_metrics
from .scoring import (
    CONFIDENCE_THRESHOLDS,
    MAX_TEXT_FACT,
    TIER_WEIGHTS,
    InvalidAnswer,
    ScoredAnswer,
    UnsafeText,
    aggregate,
    clean_text,
    item_scale,
    scale_scores,
    score_answer,
    signal,
)

ONBOARDING_ID = "onboarding"
XP_PER_ANSWER = 2
XP_PER_TALENT = 25
XP_REPLAY = 10
BALANCED_MARGIN = 8
BALANCED_LABEL = "Entre les deux"
# Un attribut de la fiche ne se construit qu'avec des points forts : curseurs à 50 ou plus.
STRENGTH_FLOOR = 50
ATTRIBUTE_MIN, ATTRIBUTE_MAX = 10, 20
TIER_LABELS = {
    "validated": "Test validé",
    "translated": "Test validé, traduction maison non validée",
    "adapted": "Inspiré de travaux publiés, non validé",
    "custom": "Indicateur maison",
    "performance": "Tâche cognitive publiée",
    "talent": "Talent validé par le jeune",
}
VERDICTS = {"agree", "disagree"}


def catalog() -> Catalog:
    return service("game_catalog")


@dataclass
class YouthData:
    runs: list[GameRun]
    facts: list[GameFact]
    feedback: dict[str, TraitFeedback]
    talents: list[Skill]

    @property
    def found_talents(self) -> list[Skill]:
        """Talents repérés par Néo et gardés par le jeune : seuls ceux-là comptent pour les
        curseurs, l'XP et les badges. Un talent que le jeune ajoute lui-même n'a pas de vraie
        catégorie (la carte lui donne « savoir-faire » par défaut) et ne doit pas se gagner en
        tapant des noms : il reste sur sa carte et dans le backoffice."""
        return [talent for talent in self.talents if talent.origin == SkillOrigin.AI]


def load_youth(youth_id: uuid.UUID) -> YouthData:
    runs = db.session.scalars(
        select(GameRun).where(GameRun.youth_id == youth_id).order_by(GameRun.started_at)
    ).all()
    facts = db.session.scalars(
        select(GameFact).where(GameFact.youth_id == youth_id).order_by(GameFact.key)
    ).all()
    feedback = db.session.scalars(select(TraitFeedback).where(TraitFeedback.youth_id == youth_id)).all()
    talents = db.session.scalars(
        select(Skill)
        .where(Skill.youth_id == youth_id, Skill.status == SkillStatus.VALIDATED)
        .order_by(Skill.reviewed_at.desc())
    ).all()
    return YouthData(list(runs), list(facts), {f.trait_id: f for f in feedback}, list(talents))


# --- Signaux et curseurs ---


def _counts_for_cursors(run: GameRun, instrument: dict | None) -> bool:
    if run.status == GameRunStatus.COMPLETED:
        return True
    return bool(instrument and instrument["kind"] == "quiz")


def collect_signals(data: YouthData) -> list[dict]:
    """Tous les signaux du jeune, avec leur origine, pour pouvoir justifier chaque curseur."""
    cat = catalog()
    rows: list[dict] = []
    for run in data.runs:
        instrument = cat.instruments.get(run.instrument_id)
        if not _counts_for_cursors(run, instrument):
            continue
        base = {"instrument_id": run.instrument_id, "run_id": str(run.id)}
        for answer in run.answers:
            if answer.skipped:
                continue
            for row in answer.signals:
                rows.append(
                    {
                        **row,
                        **base,
                        "item_id": answer.item_id,
                        "prompt": answer.prompt,
                        "answer": answer.label,
                        "at": iso(answer.answered_at),
                    }
                )
        for row in run.signals:
            rows.append({**row, **base, "item_id": None, "prompt": None, "answer": None, "at": iso(run.completed_at)})
    for talent in data.found_talents:
        for row in cat.skill_signals.get(talent.category, []):
            rows.append(
                {
                    **signal(row["trait"], row["value"], row.get("weight", 1), "talent"),
                    "instrument_id": None,
                    "run_id": None,
                    "item_id": None,
                    "prompt": talent.name,
                    "answer": talent.source_quote,
                    "at": iso(talent.reviewed_at or talent.created_at),
                }
            )
    return rows


def cursors_of(data: YouthData) -> dict[str, dict]:
    return aggregate(catalog(), collect_signals(data))


def archetype_for(cursors: dict[str, dict]) -> dict | None:
    """L'archétype du jeune, recalculé à chaque fois à partir de tous ses signaux.

    Seuls comptent les curseurs de personnalité qui ont une valeur. Le plus éloigné du milieu
    l'emporte (à égalité, le premier dans traits/10_personality.json) et son pôle donne
    l'archétype ; s'il ne s'écarte pas de plus de BALANCED_MARGIN points, c'est l'archétype
    équilibré. Sans aucune valeur, pas encore d'archétype.
    """
    cat = catalog()
    best, distance = None, -1.0
    for trait_id in cat.archetype_traits():
        value = cursors[trait_id]["value"]
        if value is None:
            continue
        # Les valeurs sont arrondies au dixième (scoring._weighted) : l'écart aussi, sinon 64,1 et
        # 35,9 ne seraient pas à égalité en virgule flottante et l'ordre des curseurs ne jouerait plus.
        gap = round(abs(value - 50), 1)
        if gap > distance:
            best, distance = trait_id, gap
    if best is None:
        return None
    if distance <= BALANCED_MARGIN:
        return cat.archetype(None, BALANCED_POLE)
    return cat.archetype(best, "high" if cursors[best]["value"] > 50 else "low")


def youth_archetype(archetype: dict | None) -> dict | None:
    """L'archétype tel que le voit le jeune : sa qualité en clair, jamais le curseur, le pôle ni la
    valeur qui le désignent."""
    if archetype is None:
        return None
    trait_id = archetype["trait"]
    quality = catalog().traits[trait_id]["youth"][archetype["pole"]] if trait_id else BALANCED_LABEL
    return {**{k: archetype[k] for k in ARCHETYPE_TEXTS}, "quality": quality}


def archetype_info(archetype: dict) -> dict:
    """Pour la psychologue : l'archétype et le pôle qui le désigne, nommés comme ses curseurs."""
    trait_id = archetype["trait"]
    return {
        **youth_archetype(archetype),
        "trait": trait_id,
        "pole": archetype["pole"],
        "trait_label": _trait_label(trait_id) if trait_id else None,
        "pole_label": catalog().traits[trait_id]["psy"][archetype["pole"]] if trait_id else BALANCED_LABEL,
    }


def psy_archetype(archetype: dict | None, cursors: dict[str, dict]) -> dict | None:
    """Ajoute la valeur du curseur qui désigne l'archétype (None pour l'archétype équilibré)."""
    if archetype is None:
        return None
    trait_id = archetype["trait"]
    return {**archetype_info(archetype), "value": cursors[trait_id]["value"] if trait_id else None}


def youth_leaning(trait_id: str, value: float | None) -> str | None:
    """Libellé montré au jeune : le pôle vers lequel il penche, « Entre les deux », ou le nom
    du curseur s'il n'a qu'un pôle."""
    trait = catalog().traits[trait_id]
    if trait["kind"] != "bipolar":
        return trait["youth"]["label"]
    if value is None:
        return None
    if abs(value - 50) <= BALANCED_MARGIN:
        return BALANCED_LABEL
    return trait["youth"]["high"] if value > 50 else trait["youth"]["low"]


def verdict_applies(trait_id: str, value: float | None, row: TraitFeedback | None) -> bool:
    """Un verdict vaut pour ce que le jeune a jugé : sur un curseur bipolaire, le pôle affiché
    à ce moment-là. Si le curseur a basculé depuis, le jeune peut juger à nouveau."""
    if row is None:
        return False
    if catalog().traits[trait_id]["kind"] != "bipolar":
        return True
    return row.label_at_verdict == youth_leaning(trait_id, value)


# --- Progression ---


def level_floor(level: int) -> int:
    done = level - 1
    return 100 * done + 25 * done * (done - 1) // 2


def level_for(xp: int) -> int:
    level = 1
    while level_floor(level + 1) <= xp:
        level += 1
    return level


def total_xp(data: YouthData) -> int:
    cat = catalog()
    xp = XP_PER_TALENT * len(data.found_talents)
    seen: set[str] = set()
    completions: Counter[str] = Counter()
    for run in data.runs:
        if run.instrument_id not in seen:
            seen.add(run.instrument_id)
            instrument = cat.instruments.get(run.instrument_id)
            if instrument and instrument["kind"] != "performance":
                xp += XP_PER_ANSWER * sum(1 for answer in run.answers if not answer.skipped)
        if run.status == GameRunStatus.COMPLETED:
            completions[run.instrument_id] += 1
    for instrument_id, count in completions.items():
        instrument = cat.instruments.get(instrument_id)
        if instrument:
            xp += instrument["xp"] + XP_REPLAY * min(count - 1, 3)
    return xp


def _badge_earned(rule: dict, context: dict) -> bool:
    kind = rule["type"]
    if kind == "completed":
        return rule["instrument"] in context["completed"]
    if kind == "completed_count":
        pool = context["completed_kinds"]
        if "kind" in rule:
            count = pool[rule["kind"]]
        else:
            # `except_kind` laisse un type de côté : un mini-jeu, c'est tout sauf le quiz d'arrivée.
            count = sum(n for k, n in pool.items() if k != rule.get("except_kind"))
        return count >= rule["count"]
    if kind in {"talents", "facts", "level"}:
        return context[kind] >= rule["count"]
    return False


def progress(data: YouthData) -> dict:
    cat = catalog()
    xp = total_xp(data)
    level = level_for(xp)
    titles = cat.sheet.get("level_titles", [])
    completed = {r.instrument_id for r in data.runs if r.status == GameRunStatus.COMPLETED}
    kinds = Counter(
        cat.instruments[i]["kind"] for i in completed if i in cat.instruments
    )
    context = {
        "completed": completed,
        "completed_kinds": kinds,
        "talents": len(data.found_talents),
        "facts": len(data.facts),
        "level": level,
    }
    badges = [
        {
            "id": badge["id"],
            "label": badge["label"],
            "description": badge["description"],
            "icon": badge.get("icon", "star"),
            "earned": _badge_earned(badge["rule"], context),
        }
        for badge in cat.sheet.get("badges", [])
    ]
    return {
        "xp": xp,
        "level": level,
        "level_title": titles[min(level - 1, len(titles) - 1)] if titles else "",
        "level_xp": level_floor(level),
        "next_level_xp": level_floor(level + 1),
        "badges": badges,
    }


# --- Parties ---


def _instrument_or_404(instrument_id: str) -> dict:
    instrument = catalog().instruments.get(instrument_id)
    if instrument is None:
        raise ApiError(404, "not_found", "Jeu introuvable.")
    return instrument


def _item_count(instrument: dict) -> int:
    return len(instrument.get("items", []))


def min_answers(instrument: dict) -> int:
    return instrument.get("min_answers", math.ceil(_item_count(instrument) * 0.6))


def run_dict(run: GameRun, instrument: dict | None) -> dict:
    answered = sum(1 for a in run.answers if not a.skipped)
    seen = len(run.answers)
    return {
        "id": str(run.id),
        "instrument_id": run.instrument_id,
        "instrument_version": run.instrument_version,
        "status": run.status.value,
        "started_at": iso(run.started_at),
        "paused_at": iso(run.paused_at),
        "completed_at": iso(run.completed_at),
        "answered": answered,
        "seen": seen,
        "total": _item_count(instrument) if instrument else seen,
    }


def _open_run(youth_id: uuid.UUID, instrument_id: str) -> GameRun | None:
    return db.session.scalar(
        select(GameRun).where(
            GameRun.youth_id == youth_id,
            GameRun.instrument_id == instrument_id,
            GameRun.status == GameRunStatus.IN_PROGRESS,
        )
    )


def _has_completed(youth_id: uuid.UUID, instrument_id: str) -> bool:
    """Lu en base au moment de l'appel, pas dans une liste chargée plus tôt."""
    return db.session.scalar(
        select(GameRun.id)
        .where(
            GameRun.youth_id == youth_id,
            GameRun.instrument_id == instrument_id,
            GameRun.status == GameRunStatus.COMPLETED,
        )
        .limit(1)
    ) is not None


def _satisfied_requirements(runs: list[GameRun]) -> set[str]:
    """Instruments qui ne retiennent plus les jeux qui les exigent : une partie terminée, ou une
    partie qui a vu au moins `unlocks_after` questions, passées comprises, quand l'instrument en
    fixe un. Seule règle de déblocage : le départ d'une partie et l'état des jeux la suivent."""
    cat = catalog()
    satisfied: set[str] = set()
    for run in runs:
        if run.status == GameRunStatus.COMPLETED:
            satisfied.add(run.instrument_id)
            continue
        threshold = cat.instruments.get(run.instrument_id, {}).get("unlocks_after")
        if threshold is not None and len(run.answers) >= threshold:
            satisfied.add(run.instrument_id)
    return satisfied


def _is_locked(instrument: dict, satisfied: set[str]) -> bool:
    return any(required not in satisfied for required in instrument.get("requires", []))


def _locked_message(instrument: dict, satisfied: set[str]) -> str:
    required = next(r for r in instrument.get("requires", []) if r not in satisfied)
    threshold = catalog().instruments.get(required, {}).get("unlocks_after")
    if threshold is None:
        return "Ce jeu se débloque après le quiz d'arrivée."
    questions = "la première question" if threshold == 1 else f"les {threshold} premières questions"
    return f"Ce jeu se débloque après {questions} du quiz d’arrivée."


def _lock_run(run_id: uuid.UUID) -> GameRun | None:
    """Verrouille la partie jusqu'à la fin de la transaction et la relit depuis la base."""
    return db.session.get(GameRun, run_id, with_for_update=True, populate_existing=True)


def start_run(user: User, instrument_id: str) -> tuple[dict, bool]:
    instrument = _instrument_or_404(instrument_id)
    data = load_youth(user.id)
    satisfied = _satisfied_requirements(data.runs)
    if _is_locked(instrument, satisfied):
        raise ApiError(409, "locked", _locked_message(instrument, satisfied))

    created = False
    run = _open_run(user.id, instrument_id)
    if run is not None:
        # Reprise : la partie a pu se terminer entre-temps dans un autre onglet.
        run = _lock_run(run.id)
        if run is not None and run.status != GameRunStatus.IN_PROGRESS:
            run = None
    if run is None:
        if not instrument.get("replayable", True) and _has_completed(user.id, instrument_id):
            raise ApiError(409, "already_completed", "Tu as déjà terminé ce jeu.")
        run = GameRun(
            youth_id=user.id, instrument_id=instrument_id, instrument_version=instrument["version"]
        )
        db.session.add(run)
        created = True
    else:
        _reconcile(run, instrument)
    run.paused_at = None
    try:
        db.session.commit()
    except IntegrityError:  # Deux onglets ont démarré la même partie.
        db.session.rollback()
        run = _open_run(user.id, instrument_id)
        created = False
        if run is None:
            raise
    return run_payload(run, instrument), created


def run_payload(run: GameRun, instrument: dict) -> dict:
    return {
        "run": run_dict(run, instrument),
        "instrument": catalog().public_instrument(instrument),
        "answers": [
            {"item_id": a.item_id, "value": a.value, "skipped": a.skipped}
            for a in run.answers
        ],
    }


def own_run(user: User, run_id: uuid.UUID, lock: bool = False) -> tuple[GameRun, dict]:
    """La partie du jeune ; avec `lock`, verrouillée et relue avant toute modification."""
    run = _lock_run(run_id) if lock else db.session.get(GameRun, run_id)
    if run is None or run.youth_id != user.id:
        raise ApiError(404, "not_found", "Partie introuvable.")
    return run, _instrument_or_404(run.instrument_id)


def _require_open(run: GameRun) -> None:
    if run.status != GameRunStatus.IN_PROGRESS:
        raise ApiError(409, "run_closed", "Cette partie est terminée.")


def _clean_response_ms(value) -> int | None:
    """Temps de réponse envoyé par le navigateur ; ignoré s'il n'est pas un nombre fini."""
    return finite_ms(value)


def _scale_snapshot(instrument: dict, item: dict) -> dict | None:
    """Échelle d'une question Likert telle que proposée au jeune."""
    if item["type"] != "likert":
        return None
    scale = item_scale(instrument, item)
    return {"min": scale["min"], "max": scale["max"], "labels": list(scale.get("labels") or [])}


def _same_question(instrument: dict, item: dict, answer: GameAnswer) -> bool:
    """La question a gardé son type et son échelle depuis la réponse."""
    if answer.item_type is not None and answer.item_type != item["type"]:
        return False
    if item["type"] == "likert" and answer.item_scale is not None:
        return answer.item_scale == _scale_snapshot(instrument, item)
    return True


def _reconcile(run: GameRun, instrument: dict) -> None:
    """Remet une partie commencée sur une ancienne version du contenu à la version actuelle.

    Une réponse dont la question a disparu, ou changé de type ou d'échelle, est retirée ;
    les autres sont recalculées avec la définition actuelle, et retirées si elles ne sont plus
    valides. Ainsi une question renommée ne compte pas deux fois et la fin de partie ne bute
    pas sur une ancienne valeur. Les parties terminées gardent leur version.
    """
    if run.instrument_version == instrument["version"]:
        return
    if instrument["kind"] != "performance":
        cat = catalog()
        for answer in list(run.answers):
            item = cat.item(instrument, answer.item_id)
            if item is None or not _same_question(instrument, item, answer):
                run.answers.remove(answer)
                continue
            answer.position = instrument["items"].index(item)
            answer.item_type, answer.item_scale = item["type"], _scale_snapshot(instrument, item)
            if answer.skipped:
                continue
            try:
                scored = score_answer(instrument, item, answer.value)
            except InvalidAnswer:
                run.answers.remove(answer)
                continue
            answer.value, answer.label, answer.signals = scored.value, scored.label, scored.signals
    run.instrument_version = instrument["version"]


def _save_fact(user: User, instrument: dict, item: dict, fact: tuple[str, str, str]) -> None:
    key, label, value = fact
    row = db.session.get(GameFact, (user.id, key), with_for_update=True, populate_existing=True)
    if row is None:
        db.session.add(
            GameFact(
                youth_id=user.id,
                key=key,
                label=label,
                value=value,
                original_value=value,
                source_instrument_id=instrument["id"],
                source_item_id=item["id"],
            )
        )
        return
    # Une nouvelle réponse au jeu met à jour l'origine, sans écraser la correction du jeune.
    row.label, row.original_value = label, value
    row.source_instrument_id, row.source_item_id = instrument["id"], item["id"]
    if not row.edited:
        row.value = value
    row.updated_at = utcnow()


def _retract_fact(user: User, instrument: dict, item: dict) -> dict | None:
    """Le jeune passe une question de détail à laquelle il avait répondu : le détail venu de cette
    réponse quitte sa fiche, sauf s'il l'avait lui-même corrigé. Renvoie le détail retiré."""
    row = db.session.get(GameFact, (user.id, item["fact"]), with_for_update=True, populate_existing=True)
    if row is None or row.edited:
        return None
    if (row.source_instrument_id, row.source_item_id) != (instrument["id"], item["id"]):
        return None
    removed = {"key": row.key, "label": row.label, "value": row.value}
    db.session.delete(row)
    return removed


def _store_answer(
    user: User,
    run: GameRun,
    instrument: dict,
    item: dict,
    scored: ScoredAnswer | None,
    response_ms: int | None,
) -> bool:
    """Enregistre la réponse (ou le passage, si `scored` vaut None) et ce qu'elle change.

    Rien n'est envoyé en base avant le commit : une réponse ou un détail créé entre-temps par
    une autre requête lève donc l'IntegrityError au commit, là où save_answer la rattrape.
    Renvoie True pour une première réponse à cette question dans la partie.
    """
    skipped = scored is None
    with db.session.no_autoflush:
        answer = next((a for a in run.answers if a.item_id == item["id"]), None)
        previous = None if answer is None or answer.skipped else {"label": answer.label, "value": answer.value}
        if answer is None:
            answer = GameAnswer(run=run, item_id=item["id"])
            db.session.add(answer)
        answer.position = instrument["items"].index(item)
        answer.prompt = item["prompt"]
        answer.item_type, answer.item_scale = item["type"], _scale_snapshot(instrument, item)
        answer.skipped = skipped
        answer.value = None if skipped else scored.value
        answer.label = None if skipped else scored.label
        answer.signals = [] if skipped else scored.signals
        answer.response_ms = response_ms
        answer.answered_at = utcnow()

        subject = events.answer_subject(run.id, item["id"])
        if not skipped:
            if scored.fact:
                _save_fact(user, instrument, item, scored.fact)
            if previous is not None and previous["value"] != scored.value:
                after = {"label": scored.label, "value": scored.value}
                events.log(user.id, events.ANSWER_CHANGED, subject, previous, after)
        elif previous is not None:
            removed = _retract_fact(user, instrument, item) if "fact" in item else None
            after = {"label": None, "value": None, "skipped": True, "fact_removed": removed}
            events.log(user.id, events.ANSWER_RETRACTED, subject, previous, after)
    return previous is None


def save_answer(user: User, run_id: uuid.UUID, item_id: str, body: dict) -> dict:
    run, instrument = own_run(user, run_id, lock=True)
    _require_open(run)
    item = catalog().item(instrument, item_id)
    if item is None:
        raise ApiError(404, "not_found", "Question introuvable.")

    scored = None
    if body.get("skipped") is not True:
        try:
            scored = score_answer(instrument, item, body.get("value"))
        except InvalidAnswer as error:
            raise ApiError(400, "invalid_answer", str(error)) from error
    response_ms = _clean_response_ms(body.get("response_ms"))

    try:
        first_time = _store_answer(user, run, instrument, item, scored, response_ms)
        db.session.commit()
    except IntegrityError:
        # Double envoi : l'autre requête a créé cette réponse (ou ce détail) entre-temps.
        # On relit sous verrou et on applique celle-ci comme une modification : la dernière gagne.
        db.session.rollback()
        run, instrument = own_run(user, run_id, lock=True)
        _require_open(run)
        try:
            first_time = _store_answer(user, run, instrument, item, scored, response_ms)
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise ApiError(409, "answer_conflict", "Réponse en cours d’enregistrement, réessaie.") from error

    is_first_run = db.session.scalar(
        select(GameRun.id)
        .where(GameRun.youth_id == user.id, GameRun.instrument_id == run.instrument_id)
        .order_by(GameRun.started_at)
        .limit(1)
    ) == run.id
    return {
        "run": run_dict(run, instrument),
        "xp_gained": XP_PER_ANSWER if first_time and scored is not None and is_first_run else 0,
    }


def pause_run(user: User, run_id: uuid.UUID) -> dict:
    run, instrument = own_run(user, run_id, lock=True)
    _require_open(run)
    run.paused_at = utcnow()
    db.session.commit()
    return {"run": run_dict(run, instrument)}


def _highlights(cursors: dict[str, dict], feedback: dict[str, TraitFeedback], limit: int = 3) -> list[dict]:
    views = []
    for trait_id, cursor in cursors.items():
        view = youth_trait(trait_id, cursor, feedback)
        if view and view["value"] is not None:
            strength = abs(view["value"] - 50) if view["kind"] == "bipolar" else view["value"] - 50
            if strength > 0:
                views.append((strength, view))
    views.sort(key=lambda pair: pair[0], reverse=True)
    return [view for _, view in views[:limit]]


def complete_run(user: User, run_id: uuid.UUID, body: dict) -> dict:
    run, instrument = own_run(user, run_id, lock=True)
    if run.status != GameRunStatus.COMPLETED:
        _reconcile(run, instrument)
    data_before = load_youth(user.id)
    before = progress(data_before)
    if run.status == GameRunStatus.COMPLETED:
        return _result(user, run, instrument, before)
    # Seul un archétype déjà révélé peut changer : la fin du quiz le révèle sans annoncer de changement.
    archetype_before = archetype_for(cursors_of(data_before)) if _archetype_revealed(data_before) else None

    if instrument["kind"] == "performance":
        _score_performance(run, instrument, body.get("trials"))
    else:
        answered = sum(1 for a in run.answers if not a.skipped)
        needed = min_answers(instrument)
        if answered < needed:
            raise ApiError(409, "not_enough_answers", f"Il faut au moins {needed} réponses.")
        run.metrics = {"scales": scale_scores(instrument, run.answers)}
    run.status = GameRunStatus.COMPLETED
    run.completed_at = utcnow()
    run.paused_at = None
    db.session.commit()
    return _result(user, run, instrument, before, archetype_before)


def _score_performance(run: GameRun, instrument: dict, trials) -> None:
    scorer = SCORERS[instrument["performance"]["scorer"]]
    try:
        result = scorer.score(instrument, trials)
    except InvalidAnswer as error:
        raise ApiError(400, "invalid_trials", str(error)) from error
    run.metrics = result.metrics
    run.signals = result.signals
    run.answers.clear()
    db.session.flush()
    for position, row in enumerate(result.rows):
        db.session.add(
            GameAnswer(
                run=run,
                item_id=row["item_id"],
                position=position,
                prompt=row["prompt"],
                value=row.get("value"),
                label=row.get("label"),
                response_ms=row.get("response_ms"),
                signals=[],
                item_type="trial",
            )
        )


def _result(
    user: User, run: GameRun, instrument: dict, before: dict, archetype_before: dict | None = None
) -> dict:
    data = load_youth(user.id)
    after = progress(data)
    cursors = cursors_of(data)
    # Secret jusqu'à la fin du quiz d'arrivée, comme sur la fiche : un mini-jeu terminé avant ne le
    # montre pas, même s'il le fait changer.
    archetype = archetype_for(cursors) if _archetype_revealed(data) else None
    earned_before = {b["id"] for b in before["badges"] if b["earned"]}
    changed = (
        archetype_before is not None and archetype is not None and archetype_before["id"] != archetype["id"]
    )
    return {
        "run": run_dict(run, instrument),
        "xp_gained": after["xp"] - before["xp"],
        "progress": after,
        "leveled_up": after["level"] > before["level"],
        "new_badges": [b for b in after["badges"] if b["earned"] and b["id"] not in earned_before],
        "archetype": youth_archetype(archetype),
        # L'archétype suit le trait de caractère le plus marqué : le jeune voit quand une partie
        # le fait changer.
        "previous_archetype": youth_archetype(archetype_before) if changed else None,
        "highlights": _highlights(cursors, data.feedback),
        # Ses réussites seulement : les pourcentages et les mesures fines restent à la psychologue.
        "metrics": youth_metrics(instrument, run.metrics) if instrument["kind"] == "performance" else None,
    }


# --- Écrans du jeune ---


def game_status(user: User) -> dict:
    cat = catalog()
    data = load_youth(user.id)
    completed = Counter(r.instrument_id for r in data.runs if r.status == GameRunStatus.COMPLETED)
    latest_completion = {
        r.instrument_id: r.completed_at for r in data.runs if r.status == GameRunStatus.COMPLETED
    }
    open_runs = {r.instrument_id: r for r in data.runs if r.status == GameRunStatus.IN_PROGRESS}
    satisfied = _satisfied_requirements(data.runs)

    instruments = []
    for instrument in cat.ordered_instruments():
        run = open_runs.get(instrument["id"])
        count = completed[instrument["id"]]
        state = "in_progress" if run else "completed" if count else "new"
        instruments.append(
            {
                "id": instrument["id"],
                "kind": instrument["kind"],
                "title": instrument["title"],
                "tagline": instrument["tagline"],
                "icon": instrument["icon"],
                "duration_min": instrument["duration_min"],
                "xp": instrument["xp"],
                "source_note": instrument.get("source_note"),
                "state": state,
                "locked": _is_locked(instrument, satisfied),
                # Questions de cet instrument qui débloquent les jeux qui l'exigent (None : la fin).
                "unlocks_after": instrument.get("unlocks_after"),
                "replayable": instrument.get("replayable", True),
                "answered": sum(1 for a in run.answers if not a.skipped) if run else 0,
                # Questions vues, passées comprises : une partie où tout a été passé est commencée.
                "seen": len(run.answers) if run else 0,
                "total": _item_count(instrument),
                "completed_count": count,
                "last_completed_at": iso(latest_completion.get(instrument["id"])),
            }
        )

    onboarding_run = open_runs.get(ONBOARDING_ID)
    must_onboard = (
        ONBOARDING_ID in cat.instruments
        and not completed[ONBOARDING_ID]
        and not (onboarding_run and onboarding_run.paused_at)
    )
    return {
        "must_onboard": must_onboard,
        "progress": progress(data),
        "instruments": instruments,
    }


def youth_trait(trait_id: str, cursor: dict, feedback: dict[str, TraitFeedback]) -> dict:
    trait = catalog().traits[trait_id]
    value = cursor["value"]
    row = feedback.get(trait_id)
    view = {
        "id": trait_id,
        "group": trait["group"],
        "kind": trait["kind"],
        "value": value,
        "confidence": cursor["confidence"],
        # Null si le jeune n'a rien dit, ou s'il a jugé un autre pôle que celui affiché maintenant.
        "verdict": row.verdict if verdict_applies(trait_id, value, row) else None,
    }
    label = youth_leaning(trait_id, value)
    if trait["kind"] == "bipolar":
        return {**view, "low": trait["youth"]["low"], "high": trait["youth"]["high"], "label": label}
    return {**view, "label": label}


def _attribute_score(parts: list[dict], cursors: dict[str, dict]) -> int | None:
    """Moyenne pondérée des seuls points forts (curseurs à 50 ou plus), ramenée de 50-100 à 10-20.

    Un curseur bas ne fait jamais baisser un attribut : sans aucun point fort, l'attribut reste
    à découvrir (None).
    """
    total, weights = 0.0, 0.0
    for part in parts:
        value = cursors[part["trait"]]["value"]
        if value is None or value < STRENGTH_FLOOR:
            continue
        weight = part.get("weight", 1)
        total += value * weight
        weights += weight
    if not weights:
        return None
    mean = total / weights
    span = ATTRIBUTE_MAX - ATTRIBUTE_MIN
    return round(ATTRIBUTE_MIN + (mean - STRENGTH_FLOOR) * span / (100 - STRENGTH_FLOOR))


def _attributes(cursors: dict[str, dict], completed: set[str]) -> list[dict]:
    attributes = []
    for attribute in catalog().sheet["attributes"]:
        score = _attribute_score(attribute["traits"], cursors)
        attributes.append(
            {
                "id": attribute["id"],
                "label": attribute["label"],
                "description": attribute["description"],
                "icon": attribute.get("icon", "star"),
                "score": score,
                # Jeu à proposer tant que l'attribut reste à découvrir.
                "reveal_with": None
                if score is not None
                else reveal_with(catalog(), {p["trait"] for p in attribute["traits"]}, completed),
            }
        )
    return attributes


def fact_dict(fact: GameFact, psy: bool = False) -> dict:
    row = {
        "key": fact.key,
        "label": fact.label,
        "value": fact.value,
        "original_value": fact.original_value,
        "edited": fact.edited,
        "hidden": fact.hidden,
        "updated_at": iso(fact.updated_at),
        "edited_at": iso(fact.edited_at),
    }
    if psy:
        row["source_instrument_id"] = fact.source_instrument_id
        row["source_item_id"] = fact.source_item_id
    return row


def _is_shown_to_youth(view: dict, group: dict) -> bool:
    """Un curseur à un seul pôle ne montre au jeune que ses points forts, quel que soit son groupe."""
    if view["value"] is None:
        return False
    if view["kind"] == "unipolar" or group.get("youth_view") == "strengths":
        return view["value"] >= STRENGTH_FLOOR
    return True


def _archetype_revealed(data: YouthData) -> bool:
    """La fin du quiz d'arrivée révèle l'archétype. Avant, les réponses d'un quiz en pause et les
    talents déjà gardés comptent pour les curseurs, et la psychologue voit l'archétype qu'ils
    donnent, mais la fiche du jeune le garde secret comme elle le promet."""
    if ONBOARDING_ID not in catalog().instruments:
        return True
    return any(r.instrument_id == ONBOARDING_ID and r.status == GameRunStatus.COMPLETED for r in data.runs)


def character_sheet(user: User) -> dict:
    cat = catalog()
    data = load_youth(user.id)
    cursors = cursors_of(data)
    archetype = youth_archetype(archetype_for(cursors)) if _archetype_revealed(data) else None
    groups = []
    for group in cat.trait_groups:
        traits = [youth_trait(t, cursors[t], data.feedback) for t in group["trait_ids"]]
        known = [view for view in traits if _is_shown_to_youth(view, group)]
        if group.get("youth_view") == "strengths":
            known.sort(key=lambda view: -view["value"])
        groups.append({"id": group["id"], "label": group["youth_label"], "traits": known})
    pending = db.session.query(Skill).filter(
        Skill.youth_id == user.id, Skill.status == SkillStatus.PENDING
    ).count()
    return {
        "identity": {"display_name": user.display_name, "archetype": archetype},
        "progress": progress(data),
        "facts": [fact_dict(f) for f in data.facts],
        "attributes": _attributes(
            cursors, {r.instrument_id for r in data.runs if r.status == GameRunStatus.COMPLETED}
        ),
        "trait_groups": groups,
        "talents": {
            "validated": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "category": t.category,
                    "description": t.description,
                    "quote": t.source_quote,
                    "origin": t.origin.value,
                }
                for t in data.talents
            ],
            "pending_count": pending,
        },
    }


def update_fact(user: User, key: str, body: dict) -> dict:
    # Vérifiée avant la requête : Postgres refuse un octet nul dans un texte (500 sinon).
    if not FACT_KEY.fullmatch(key):
        raise ApiError(404, "not_found", "Détail introuvable.")
    fact = db.session.get(GameFact, (user.id, key), with_for_update=True, populate_existing=True)
    if fact is None:
        raise ApiError(404, "not_found", "Détail introuvable.")
    value = None
    if "value" in body:
        try:
            value = clean_text(body["value"], MAX_TEXT_FACT)
        except UnsafeText as error:
            raise ApiError(400, "invalid_field", str(error)) from error
        except InvalidAnswer as error:
            raise ApiError(400, "invalid_field", f"Écris entre 1 et {MAX_TEXT_FACT} caractères.") from error
    hidden = body.get("hidden")
    if "hidden" in body and not isinstance(hidden, bool):
        raise ApiError(400, "invalid_field", "hidden doit être vrai ou faux.")

    now = utcnow()
    subject = events.fact_subject(fact.key)
    changed = False
    if value is not None and value != fact.value:
        events.log(
            user.id,
            events.FACT_EDITED,
            subject,
            {"label": fact.label, "value": fact.value},
            {"label": fact.label, "value": value},
        )
        fact.value, fact.edited, fact.edited_at = value, True, now
        changed = True
    if isinstance(hidden, bool) and hidden != fact.hidden:
        events.log(
            user.id,
            events.FACT_HIDDEN if hidden else events.FACT_SHOWN,
            subject,
            {"label": fact.label, "value": fact.value, "hidden": fact.hidden},
            {"label": fact.label, "value": fact.value, "hidden": hidden},
        )
        fact.hidden = hidden
        changed = True
    if changed:
        fact.updated_at = now
        db.session.commit()
    return {"fact": fact_dict(fact)}


def _verdict_state(row: TraitFeedback) -> dict:
    return {
        "verdict": row.verdict,
        "label": row.label_at_verdict,
        "value": row.value_at_verdict,
        "at": iso(row.updated_at),
    }


def _apply_verdict(user: User, trait_id: str, verdict: str | None, label: str | None, value) -> None:
    row = db.session.get(
        TraitFeedback, (user.id, trait_id), with_for_update=True, populate_existing=True
    )
    subject = events.trait_subject(trait_id)
    now = {"verdict": verdict, "label": label, "value": value}
    if row is None:
        if verdict is not None:
            db.session.add(
                TraitFeedback(
                    youth_id=user.id,
                    trait_id=trait_id,
                    verdict=verdict,
                    label_at_verdict=label,
                    value_at_verdict=value,
                    updated_at=utcnow(),
                )
            )
            events.log(user.id, events.VERDICT_SET, subject, None, now)
        return
    before = _verdict_state(row)
    if verdict is None:
        # Le retrait laisse une trace : la psychologue sait ce que le jeune avait dit.
        db.session.delete(row)
        events.log(user.id, events.VERDICT_WITHDRAWN, subject, before, now)
        return
    current = verdict_applies(trait_id, value, row)
    if current and row.verdict == verdict:
        return  # Même verdict sur le même pôle : un double appui ne change rien.
    row.verdict, row.label_at_verdict, row.value_at_verdict = verdict, label, value
    row.updated_at = utcnow()
    # Sur un pôle qui a changé depuis, c'est un nouveau verdict ; sinon le jeune change d'avis.
    events.log(user.id, events.VERDICT_CHANGED if current else events.VERDICT_SET, subject, before, now)


def set_trait_feedback(user: User, trait_id: str, verdict) -> dict:
    if trait_id not in catalog().traits:
        raise ApiError(404, "not_found", "Curseur introuvable.")
    if verdict is not None and (not isinstance(verdict, str) or verdict not in VERDICTS):
        raise ApiError(400, "invalid_field", "Le verdict doit être agree, disagree ou null.")
    # Ce que le jeune juge est recalculé ici, jamais repris du navigateur.
    value = cursors_of(load_youth(user.id))[trait_id]["value"]
    label = youth_leaning(trait_id, value)
    try:
        _apply_verdict(user, trait_id, verdict, label, value)
        db.session.commit()
    except IntegrityError:
        # Deux appuis rapprochés : l'autre requête a créé le verdict, celui-ci le remplace.
        db.session.rollback()
        try:
            _apply_verdict(user, trait_id, verdict, label, value)
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise ApiError(409, "verdict_conflict", "Ton avis est en cours d’enregistrement, réessaie.") from error
    return {"trait_id": trait_id, "verdict": verdict}


# --- Backoffice psychologue ---


def source_dict(source_id: str) -> dict | None:
    return catalog().sources.get(source_id)


def instrument_info(instrument: dict) -> dict:
    return {
        "id": instrument["id"],
        "kind": instrument["kind"],
        "title": instrument["title"],
        "tier": instrument["tier"],
        "tier_label": TIER_LABELS[instrument["tier"]],
        "scoring_note": instrument.get("scoring_note"),
        "sources": [source_dict(s) for s in instrument.get("source_ids", [])],
        # Titres des chapitres : les réponses ne portent que l'identifiant du chapitre.
        "chapters": [{"id": c["id"], "title": c["title"]} for c in instrument.get("chapters", [])],
    }


def verdict_detail(trait_id: str, value: float | None, row: TraitFeedback | None) -> dict | None:
    """Ce que le jeune a jugé : pôle et valeur au moment du verdict, et s'il a basculé depuis."""
    if row is None:
        return None
    return {
        "verdict": row.verdict,
        "label_at_verdict": row.label_at_verdict,
        "value_at_verdict": row.value_at_verdict,
        "at": iso(row.updated_at),
        "stale": not verdict_applies(trait_id, value, row),
    }


def psy_cursor(trait_id: str, cursor: dict, feedback: dict[str, TraitFeedback]) -> dict:
    trait = catalog().traits[trait_id]
    value = cursor["value"]
    row = feedback.get(trait_id)
    view = {
        "id": trait_id,
        "kind": trait["kind"],
        "description": trait.get("description"),
        "reference": trait.get("reference"),
        "norm_note": trait.get("norm_note"),
        "value": value,
        "n": cursor["n"],
        "confidence": cursor["confidence"],
        "by_tier": {
            tier: {**detail, "label": TIER_LABELS[tier]} for tier, detail in cursor["by_tier"].items()
        },
        "verdict": row.verdict if row else None,
        "verdict_detail": verdict_detail(trait_id, value, row),
    }
    if trait["kind"] == "bipolar":
        low, high = trait["psy"]["low"], trait["psy"]["high"]
        headline = None
        if value is not None:
            side, percent = (high, value) if value >= 50 else (low, 100 - value)
            headline = {"percent": round(percent), "label": side}
        return {**view, "low": low, "high": high, "headline": headline}
    label = trait["psy"]["label"]
    headline = {"percent": round(value), "label": label} if value is not None else None
    return {**view, "label": label, "headline": headline}


def _uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def _answer_subject(run: GameRun | None, item_id: str) -> tuple[str, dict]:
    if run is None:
        return item_id, {"instrument_id": None}
    cat = catalog()
    instrument = cat.instruments.get(run.instrument_id)
    answer = next((a for a in run.answers if a.item_id == item_id), None)
    item = cat.item(instrument, item_id) if instrument else None
    prompt = answer.prompt if answer else item["prompt"] if item else item_id
    title = instrument["title"] if instrument else run.instrument_id
    return f"{title} · {prompt}", {"instrument_id": run.instrument_id}


def psy_events(data: YouthData, youth_id: uuid.UUID) -> list[dict]:
    """Modifications du jeune, de la plus récente à la plus ancienne, nommées en clair."""
    runs = {run.id: run for run in data.runs}
    rows = []
    for event in events.recent(youth_id):
        kind, ref = events.parse_subject(event.subject)
        if kind == "fact":
            state = event.after or event.before or {}
            subject, target = state.get("label") or ref, {"type": "fact", "key": ref}
        elif kind == "trait":
            subject, target = _trait_label(ref), {"type": "trait", "trait_id": ref}
        else:
            run_id, _, item_id = ref.partition("/")
            subject, extra = _answer_subject(runs.get(_uuid(run_id)), item_id)
            target = {"type": "answer", "run_id": run_id, "item_id": item_id, **extra}
        rows.append(
            {
                "id": event.id,
                "kind": event.kind,
                "subject": subject,
                "ref": target,
                "before": event.before,
                "after": event.after,
                "at": iso(event.created_at),
            }
        )
    return rows


def psy_overview(user: User) -> dict:
    cat = catalog()
    data = load_youth(user.id)
    cursors = cursors_of(data)
    runs = []
    for run in reversed(data.runs):
        instrument = cat.instruments.get(run.instrument_id)
        runs.append(
            {
                **run_dict(run, instrument),
                "instrument": instrument_info(instrument) if instrument else None,
                "metrics": run.metrics,
            }
        )
    current = progress(data)
    return {
        "youth": {"id": str(user.id), "display_name": user.display_name},
        "progress": {k: current[k] for k in ("xp", "level", "level_title")},
        "archetype": psy_archetype(archetype_for(cursors), cursors),
        "cursor_groups": [
            {
                "id": group["id"],
                "label": group["label"],
                "cursors": [psy_cursor(t, cursors[t], data.feedback) for t in group["trait_ids"]],
            }
            for group in cat.trait_groups
        ],
        "facts": [fact_dict(f, psy=True) for f in data.facts],
        "runs": runs,
        "events": psy_events(data, user.id),
    }


def _trait_label(trait_id: str) -> str:
    trait = catalog().traits.get(trait_id)
    if trait is None:
        return trait_id
    psy = trait["psy"]
    return f"{psy['low']} ↔ {psy['high']}" if trait["kind"] == "bipolar" else psy["label"]


def _item_source(instrument: dict | None, item: dict | None) -> dict | None:
    reference = (item or {}).get("source")
    if not reference:
        return None
    return {**reference, "source": source_dict(reference["source_id"])}


def _hidden_items(facts) -> set[tuple[str | None, str | None]]:
    """Questions dont le jeune a masqué le détail : un identifiant de question n'est unique que
    dans son instrument."""
    return {(f.source_instrument_id, f.source_item_id) for f in facts if f.hidden}


def _offered_options(item: dict | None) -> list[dict] | None:
    if not item or item["type"] != "choice":
        return None
    return [{"id": option["id"], "label": option["label"]} for option in item["options"]]


def psy_run_detail(user: User, run_id: uuid.UUID) -> dict:
    run = db.session.get(GameRun, run_id)
    if run is None or run.youth_id != user.id:
        raise ApiError(404, "not_found", "Partie introuvable.")
    cat = catalog()
    instrument = cat.instruments.get(run.instrument_id)
    hidden = _hidden_items(
        db.session.scalars(
            select(GameFact).where(GameFact.youth_id == user.id, GameFact.hidden.is_(True))
        )
    )
    answers = {answer.item_id: answer for answer in run.answers}
    items = instrument.get("items", []) if instrument else []
    ordered = [item["id"] for item in items] + [i for i in answers if i not in {x["id"] for x in items}]
    rows = []
    for position, item_id in enumerate(ordered, start=1):
        item = cat.item(instrument, item_id) if instrument else None
        answer = answers.get(item_id)
        rows.append(
            {
                "item_id": item_id,
                "position": position,
                "chapter": (item or {}).get("chapter"),
                "type": (item or {}).get("type", "trial"),
                "prompt": answer.prompt if answer else item["prompt"],
                "status": "unanswered" if answer is None else "skipped" if answer.skipped else "answered",
                "answer_label": answer.label if answer else None,
                "value": answer.value if answer else None,
                # Ce qui était proposé au jeune : choix possibles, ou échelle et ses libellés
                # (celle gardée avec la réponse, sinon celle du contenu actuel).
                "options": _offered_options(item),
                "scale": (answer.item_scale if answer else None)
                or (_scale_snapshot(instrument, item) if instrument and item else None),
                # Le jeune a masqué ce détail de sa fiche : la psychologue le voit quand même.
                "hidden_by_youth": (run.instrument_id, item_id) in hidden,
                "response_ms": answer.response_ms if answer else None,
                "answered_at": iso(answer.answered_at) if answer else None,
                "signals": []
                if answer is None
                else [{**s, "trait_label": _trait_label(s["trait"])} for s in answer.signals],
                "source": _item_source(instrument, item),
            }
        )
    return {
        "run": {**run_dict(run, instrument), "metrics": run.metrics},
        "instrument": instrument_info(instrument) if instrument else None,
        "run_signals": [{**s, "trait_label": _trait_label(s["trait"])} for s in run.signals],
        "answers": rows,
    }


def psy_trait_detail(user: User, trait_id: str) -> dict:
    cat = catalog()
    if trait_id not in cat.traits:
        raise ApiError(404, "not_found", "Curseur introuvable.")
    data = load_youth(user.id)
    hidden = _hidden_items(data.facts)
    signals = collect_signals(data)
    cursors = aggregate(cat, signals)
    rows = []
    for row in signals:
        if row["trait"] != trait_id:
            continue
        instrument = cat.instruments.get(row["instrument_id"]) if row["instrument_id"] else None
        rows.append(
            {
                **row,
                "tier_label": TIER_LABELS.get(row["tier"], row["tier"]),
                "instrument_title": instrument["title"] if instrument else None,
                "hidden_by_youth": row["item_id"] is not None
                and (row["instrument_id"], row["item_id"]) in hidden,
            }
        )
    return {"cursor": psy_cursor(trait_id, cursors[trait_id], data.feedback), "signals": rows}


def psy_catalog() -> dict:
    cat = catalog()
    return {
        "instruments": [instrument_info(i) for i in cat.ordered_instruments()],
        "sources": list(cat.sources.values()),
        # Poids de chaque niveau de preuve dans les curseurs, et poids total minimal de chaque
        # niveau de confiance (en dessous de « medium » : « low », sans donnée : « none »).
        "weights": dict(TIER_WEIGHTS),
        "confidence_thresholds": dict(CONFIDENCE_THRESHOLDS),
        # Chaque archétype montré au jeune et le pôle qui le désigne (archetype_for).
        "archetypes": [archetype_info(archetype) for archetype in cat.archetypes],
    }

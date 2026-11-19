"""Règles du jeu : parties, réponses, progression, fiche du jeune et vue psychologue.

Le jeune accepte à l'inscription que ses données soient transmises au Centre des Possibles
et à sa psychologue : tout ce qui est joué ici lui est visible, modifications comprises.
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
    SkillStatus,
    TraitFeedback,
    User,
    iso,
    utcnow,
)
from ..services import service
from .catalog import Catalog
from .discovery import reveal_with
from .performance import SCORERS, finite_ms, youth_metrics
from .scoring import (
    MAX_TEXT_FACT,
    InvalidAnswer,
    UnsafeText,
    aggregate,
    clean_text,
    scale_scores,
    score_answer,
    signal,
)

ONBOARDING_ID = "onboarding"
XP_PER_ANSWER = 2
XP_PER_TALENT = 25
XP_REPLAY = 10
BALANCED_MARGIN = 8
TIER_LABELS = {
    "validated": "Test validé",
    "adapted": "Inspiré d'un test validé",
    "custom": "Indicateur maison",
    "performance": "Tâche cognitive publiée",
    "talent": "Talent validé par le jeune",
}


def catalog() -> Catalog:
    return service("game_catalog")


@dataclass
class YouthData:
    runs: list[GameRun]
    facts: list[GameFact]
    feedback: dict[str, str]
    talents: list[Skill]


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
    return YouthData(list(runs), list(facts), {f.trait_id: f.verdict for f in feedback}, list(talents))


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
    for talent in data.talents:
        for row in cat.skill_signals.get(talent.category, []):
            rows.append(
                {
                    **signal(row["trait"], row["value"], row.get("weight", 1), "talent"),
                    "instrument_id": None,
                    "run_id": None,
                    "item_id": None,
                    "prompt": talent.name,
                    "answer": talent.source_quote,
                    "at": iso(talent.reviewed_at),
                }
            )
    return rows


def clan_for(cursors: dict[str, dict]) -> dict | None:
    best, best_value = None, -1.0
    for clan in catalog().clans:
        value = cursors[clan["trait"]]["value"]
        if value is not None and value > best_value:
            best, best_value = clan, value
    return best


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
    xp = XP_PER_TALENT * len(data.talents)
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
        count = pool[rule["kind"]] if "kind" in rule else sum(pool.values())
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
        "talents": len(data.talents),
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


def _is_locked(instrument: dict, completed: set[str]) -> bool:
    return any(required not in completed for required in instrument.get("requires", []))


def start_run(user: User, instrument_id: str) -> tuple[dict, bool]:
    instrument = _instrument_or_404(instrument_id)
    data = load_youth(user.id)
    completed = {r.instrument_id for r in data.runs if r.status == GameRunStatus.COMPLETED}
    if _is_locked(instrument, completed):
        raise ApiError(409, "locked", "Ce jeu se débloque après le quiz d'arrivée.")

    created = False
    run = _open_run(user.id, instrument_id)
    if run is None:
        if instrument_id in completed and not instrument.get("replayable", True):
            raise ApiError(409, "already_completed", "Tu as déjà terminé ce jeu.")
        run = GameRun(
            youth_id=user.id, instrument_id=instrument_id, instrument_version=instrument["version"]
        )
        db.session.add(run)
        created = True
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


def own_run(user: User, run_id: uuid.UUID) -> tuple[GameRun, dict]:
    run = db.session.get(GameRun, run_id)
    if run is None or run.youth_id != user.id:
        raise ApiError(404, "not_found", "Partie introuvable.")
    return run, _instrument_or_404(run.instrument_id)


def _require_open(run: GameRun) -> None:
    if run.status != GameRunStatus.IN_PROGRESS:
        raise ApiError(409, "run_closed", "Cette partie est terminée.")


def _clean_response_ms(value) -> int | None:
    """Temps de réponse envoyé par le navigateur ; ignoré s'il n'est pas un nombre fini."""
    return finite_ms(value)


def _save_fact(user: User, item: dict, fact: tuple[str, str, str]) -> None:
    key, label, value = fact
    row = db.session.get(GameFact, (user.id, key))
    if row is None:
        db.session.add(
            GameFact(
                youth_id=user.id,
                key=key,
                label=label,
                value=value,
                original_value=value,
                source_item_id=item["id"],
            )
        )
        return
    # Une nouvelle réponse au jeu met à jour l'origine, sans écraser la correction du jeune.
    row.label, row.original_value, row.source_item_id = label, value, item["id"]
    if not row.edited:
        row.value = value
    row.updated_at = utcnow()


def save_answer(user: User, run_id: uuid.UUID, item_id: str, body: dict) -> dict:
    run, instrument = own_run(user, run_id)
    _require_open(run)
    cat = catalog()
    item = cat.item(instrument, item_id)
    if item is None:
        raise ApiError(404, "not_found", "Question introuvable.")

    skipped = body.get("skipped") is True
    value, label, signals, fact = None, None, [], None
    if not skipped:
        try:
            scored = score_answer(instrument, item, body.get("value"))
        except InvalidAnswer as error:
            raise ApiError(400, "invalid_answer", str(error)) from error
        value, label, signals, fact = scored.value, scored.label, scored.signals, scored.fact

    answer = next((a for a in run.answers if a.item_id == item_id), None)
    first_time = answer is None or answer.skipped
    if answer is None:
        answer = GameAnswer(
            run=run,
            item_id=item_id,
            position=instrument["items"].index(item),
            prompt=item["prompt"],
        )
        db.session.add(answer)
    answer.value, answer.label, answer.skipped, answer.signals = value, label, skipped, signals
    answer.response_ms = _clean_response_ms(body.get("response_ms"))
    answer.answered_at = utcnow()
    if fact:
        _save_fact(user, item, fact)
    try:
        db.session.commit()
    except IntegrityError as error:  # Double envoi : la première réponse est déjà enregistrée.
        db.session.rollback()
        raise ApiError(409, "already_answered", "Réponse déjà enregistrée.") from error

    is_first_run = db.session.scalar(
        select(GameRun.id)
        .where(GameRun.youth_id == user.id, GameRun.instrument_id == run.instrument_id)
        .order_by(GameRun.started_at)
        .limit(1)
    ) == run.id
    return {
        "run": run_dict(run, instrument),
        "xp_gained": XP_PER_ANSWER if first_time and not skipped and is_first_run else 0,
    }


def pause_run(user: User, run_id: uuid.UUID) -> dict:
    run, instrument = own_run(user, run_id)
    _require_open(run)
    run.paused_at = utcnow()
    db.session.commit()
    return {"run": run_dict(run, instrument)}


def _highlights(cursors: dict[str, dict], feedback: dict[str, str], limit: int = 3) -> list[dict]:
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
    run, instrument = own_run(user, run_id)
    before = progress(load_youth(user.id))
    if run.status == GameRunStatus.COMPLETED:
        return _result(user, run, instrument, before)

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
    return _result(user, run, instrument, before)


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
            )
        )


def _result(user: User, run: GameRun, instrument: dict, before: dict) -> dict:
    data = load_youth(user.id)
    after = progress(data)
    cursors = aggregate(catalog(), collect_signals(data))
    earned_before = {b["id"] for b in before["badges"] if b["earned"]}
    return {
        "run": run_dict(run, instrument),
        "xp_gained": after["xp"] - before["xp"],
        "progress": after,
        "leveled_up": after["level"] > before["level"],
        "new_badges": [b for b in after["badges"] if b["earned"] and b["id"] not in earned_before],
        "clan": clan_for(cursors),
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
                "locked": _is_locked(instrument, set(completed)),
                "replayable": instrument.get("replayable", True),
                "answered": sum(1 for a in run.answers if not a.skipped) if run else 0,
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


def youth_trait(trait_id: str, cursor: dict, feedback: dict[str, str]) -> dict | None:
    trait = catalog().traits[trait_id]
    value = cursor["value"]
    view = {
        "id": trait_id,
        "group": trait["group"],
        "kind": trait["kind"],
        "value": value,
        "confidence": cursor["confidence"],
        "verdict": feedback.get(trait_id),
    }
    if trait["kind"] == "bipolar":
        low, high = trait["youth"]["low"], trait["youth"]["high"]
        leaning = None
        if value is not None:
            if abs(value - 50) <= BALANCED_MARGIN:
                leaning = "Entre les deux"
            else:
                leaning = high if value > 50 else low
        return {**view, "low": low, "high": high, "label": leaning}
    return {**view, "label": trait["youth"]["label"]}


def _attributes(cursors: dict[str, dict], completed: set[str]) -> list[dict]:
    attributes = []
    for attribute in catalog().sheet["attributes"]:
        total, weights = 0.0, 0.0
        for part in attribute["traits"]:
            value = cursors[part["trait"]]["value"]
            if value is not None:
                weight = part.get("weight", 1)
                total += value * weight
                weights += weight
        score = round(8 + (total / weights) * 12 / 100) if weights else None
        attributes.append(
            {
                "id": attribute["id"],
                "label": attribute["label"],
                "description": attribute["description"],
                "icon": attribute.get("icon", "star"),
                "score": score,
                # Jeu à proposer tant que l'attribut reste inconnu.
                "reveal_with": None
                if score is not None
                else reveal_with(catalog(), {p["trait"] for p in attribute["traits"]}, completed),
            }
        )
    return attributes


def fact_dict(fact: GameFact) -> dict:
    return {
        "key": fact.key,
        "label": fact.label,
        "value": fact.value,
        "original_value": fact.original_value,
        "edited": fact.edited,
        "hidden": fact.hidden,
        "updated_at": iso(fact.updated_at),
    }


def character_sheet(user: User) -> dict:
    cat = catalog()
    data = load_youth(user.id)
    cursors = aggregate(cat, collect_signals(data))
    groups = []
    for group in cat.trait_groups:
        traits = [youth_trait(t, cursors[t], data.feedback) for t in group["trait_ids"]]
        known = [t for t in traits if t["value"] is not None]
        if group.get("youth_view") == "strengths":
            known = sorted((t for t in known if t["value"] >= 50), key=lambda t: -t["value"])
        groups.append({"id": group["id"], "label": group["youth_label"], "traits": known})
    pending = db.session.query(Skill).filter(
        Skill.youth_id == user.id, Skill.status == SkillStatus.PENDING
    ).count()
    return {
        "identity": {"display_name": user.display_name, "clan": clan_for(cursors)},
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
                }
                for t in data.talents
            ],
            "pending_count": pending,
        },
    }


def update_fact(user: User, key: str, body: dict) -> dict:
    fact = db.session.get(GameFact, (user.id, key))
    if fact is None:
        raise ApiError(404, "not_found", "Détail introuvable.")
    if "value" in body:
        try:
            value = clean_text(body["value"], MAX_TEXT_FACT)
        except UnsafeText as error:
            raise ApiError(400, "invalid_field", str(error)) from error
        except InvalidAnswer as error:
            raise ApiError(400, "invalid_field", f"Écris entre 1 et {MAX_TEXT_FACT} caractères.") from error
        fact.value, fact.edited = value, True
    if "hidden" in body:
        if not isinstance(body["hidden"], bool):
            raise ApiError(400, "invalid_field", "hidden doit être vrai ou faux.")
        fact.hidden = body["hidden"]
    fact.updated_at = utcnow()
    db.session.commit()
    return {"fact": fact_dict(fact)}


def set_trait_feedback(user: User, trait_id: str, verdict) -> dict:
    if trait_id not in catalog().traits:
        raise ApiError(404, "not_found", "Curseur introuvable.")
    if verdict not in {"agree", "disagree", None}:
        raise ApiError(400, "invalid_field", "Le verdict doit être agree, disagree ou null.")
    row = db.session.get(TraitFeedback, (user.id, trait_id))
    if verdict is None:
        if row:
            db.session.delete(row)
    elif row:
        row.verdict, row.updated_at = verdict, utcnow()
    else:
        db.session.add(TraitFeedback(youth_id=user.id, trait_id=trait_id, verdict=verdict))
    db.session.commit()
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


def psy_cursor(trait_id: str, cursor: dict, feedback: dict[str, str]) -> dict:
    trait = catalog().traits[trait_id]
    value = cursor["value"]
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
        "verdict": feedback.get(trait_id),
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


def psy_overview(user: User) -> dict:
    cat = catalog()
    data = load_youth(user.id)
    cursors = aggregate(cat, collect_signals(data))
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
        "clan": clan_for(cursors),
        "cursor_groups": [
            {
                "id": group["id"],
                "label": group["label"],
                "cursors": [psy_cursor(t, cursors[t], data.feedback) for t in group["trait_ids"]],
            }
            for group in cat.trait_groups
        ],
        "facts": [fact_dict(f) for f in data.facts],
        "runs": runs,
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


def psy_run_detail(user: User, run_id: uuid.UUID) -> dict:
    run = db.session.get(GameRun, run_id)
    if run is None or run.youth_id != user.id:
        raise ApiError(404, "not_found", "Partie introuvable.")
    cat = catalog()
    instrument = cat.instruments.get(run.instrument_id)
    hidden_items = {
        f.source_item_id
        for f in db.session.scalars(
            select(GameFact).where(GameFact.youth_id == user.id, GameFact.hidden.is_(True))
        )
    }
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
                # Le jeune a masqué ce détail de sa fiche : la psychologue le voit quand même.
                "hidden_by_youth": item_id in hidden_items,
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
    hidden_items = {f.source_item_id for f in data.facts if f.hidden}
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
                "hidden_by_youth": row["item_id"] is not None and row["item_id"] in hidden_items,
            }
        )
    return {"cursor": psy_cursor(trait_id, cursors[trait_id], data.feedback), "signals": rows}


def psy_catalog() -> dict:
    cat = catalog()
    return {
        "instruments": [instrument_info(i) for i in cat.ordered_instruments()],
        "sources": list(cat.sources.values()),
    }

"""Espace jeune : talents à valider, talents ajoutés par le jeune, accord de partage."""
from __future__ import annotations

import uuid

from flask import g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..errors import ApiError
from ..extensions import db
from ..models import (
    Conversation,
    Role,
    Skill,
    SkillAction,
    SkillOrigin,
    SkillStatus,
    YouthProfile,
    iso,
    utcnow,
)
from ..security import require_roles
from ..services import service
from ..services.guardrails import name_key
from . import api
from .helpers import json_body, text_field

REVIEW_ACTIONS = {
    SkillStatus.VALIDATED.value: SkillAction.VALIDATED,
    SkillStatus.REJECTED.value: SkillAction.REJECTED,
}
DEFAULT_CATEGORY = "savoir_faire"


def _conversations() -> list[Conversation]:
    return list(
        db.session.scalars(select(Conversation).where(Conversation.youth_id == g.user.id)).all()
    )


def _commit_skill(skill: Skill) -> None:
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(409, "skill_exists", "Tu as déjà un talent avec ce nom.") from error


@api.get("/me/skills")
@require_roles(Role.YOUTH)
def list_my_skills():
    skills = db.session.scalars(
        select(Skill).where(Skill.youth_id == g.user.id).order_by(Skill.created_at.desc())
    ).all()
    return jsonify(
        {
            "skills": [skill.to_dict() for skill in skills],
            "extracting": any(c.is_extracting for c in _conversations()),
        }
    )


@api.post("/me/skills")
@require_roles(Role.YOUTH)
def add_my_skill():
    """Le jeune ajoute un talent que Néo n'a pas vu."""
    data = json_body()
    name = text_field(data, "name", "Le nom", 3, 80)
    description = str(data.get("description") or "").strip()[:300]
    skill = Skill(
        youth_id=g.user.id,
        origin=SkillOrigin.YOUTH,
        name=name,
        name_key=name_key(name),
        category=DEFAULT_CATEGORY,
        description=description,
        status=SkillStatus.VALIDATED,
        reviewed_at=utcnow(),
    )
    skill.record(SkillAction.ADDED)
    db.session.add(skill)
    _commit_skill(skill)
    return jsonify({"skill": skill.to_dict()}), 201


@api.post("/me/skills/refresh")
@require_roles(Role.YOUTH)
def refresh_my_skills():
    """Analyse les messages pas encore lus, par exemple à l'ouverture de l'écran."""
    extraction = service("extraction")
    conversations = _conversations()
    for conversation in conversations:
        extraction.schedule(conversation)
    return jsonify({"extracting": any(c.is_extracting for c in conversations)})


@api.patch("/me/skills/<uuid:skill_id>")
@require_roles(Role.YOUTH)
def review_my_skill(skill_id: uuid.UUID):
    """Le jeune garde, retire ou renomme un talent. Chaque choix est gardé dans l'historique."""
    skill = db.session.get(Skill, skill_id)
    if skill is None or skill.youth_id != g.user.id:
        raise ApiError(404, "not_found", "Talent introuvable.")

    data = json_body()
    if "status" in data and data["status"] not in REVIEW_ACTIONS:
        raise ApiError(400, "invalid_field", "Le statut doit être validated ou rejected.")
    if "name" in data:
        name = text_field(data, "name", "Le nom", 3, 80)
        if name != skill.name:
            previous = skill.name
            skill.name = name
            skill.name_key = name_key(name)
            skill.record(SkillAction.RENAMED, previous_name=previous)
    if "status" in data:
        status = SkillStatus(data["status"])
        if status != skill.status:
            skill.status = status
            skill.reviewed_at = utcnow()
            skill.record(REVIEW_ACTIONS[status.value])
    _commit_skill(skill)
    return jsonify({"skill": skill.to_dict()})


@api.get("/me/privacy")
@require_roles(Role.YOUTH)
def get_privacy():
    profile = db.session.get(YouthProfile, g.user.id)
    return jsonify(
        {
            "share_transcripts": bool(profile and profile.share_transcripts),
            "consent_at": iso(profile.consent_at) if profile else None,
        }
    )

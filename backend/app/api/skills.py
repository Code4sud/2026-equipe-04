"""Espace jeune : compétences à valider et choix de partage."""
from __future__ import annotations

import uuid

from flask import g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..errors import ApiError
from ..extensions import db
from ..models import Conversation, Role, Skill, SkillStatus, YouthProfile, iso, utcnow
from ..security import require_roles
from ..services import service
from ..services.guardrails import name_key
from . import api
from .helpers import json_body, text_field

REVIEW_STATUSES = {SkillStatus.VALIDATED.value, SkillStatus.REJECTED.value}


def _conversations() -> list[Conversation]:
    return list(
        db.session.scalars(select(Conversation).where(Conversation.youth_id == g.user.id)).all()
    )


def _profile() -> YouthProfile:
    profile = db.session.get(YouthProfile, g.user.id)
    if profile is None:
        profile = YouthProfile(user_id=g.user.id)
        db.session.add(profile)
        db.session.flush()
    return profile


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
    """Le jeune valide, refuse ou renomme une compétence : lui seul décide."""
    skill = db.session.get(Skill, skill_id)
    if skill is None or skill.youth_id != g.user.id:
        raise ApiError(404, "not_found", "Compétence introuvable.")

    data = json_body()
    if "name" in data:
        skill.name = text_field(data, "name", "Le nom", 3, 80)
        skill.name_key = name_key(skill.name)
    if "status" in data:
        status = data["status"]
        if status not in REVIEW_STATUSES:
            raise ApiError(400, "invalid_field", "Le statut doit être validated ou rejected.")
        skill.status = SkillStatus(status)
        skill.reviewed_at = utcnow()
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(409, "skill_exists", "Tu as déjà une compétence avec ce nom.") from error
    return jsonify({"skill": skill.to_dict()})


def _privacy_payload(profile: YouthProfile) -> dict:
    return {
        "share_transcripts": profile.share_transcripts,
        "share_updated_at": iso(profile.share_updated_at),
    }


@api.get("/me/privacy")
@require_roles(Role.YOUTH)
def get_privacy():
    return jsonify(_privacy_payload(_profile()))


@api.patch("/me/privacy")
@require_roles(Role.YOUTH)
def update_privacy():
    value = json_body().get("share_transcripts")
    if not isinstance(value, bool):
        raise ApiError(400, "invalid_field", "share_transcripts doit être vrai ou faux.")
    profile = _profile()
    profile.share_transcripts = value
    profile.share_updated_at = utcnow()
    db.session.commit()
    return jsonify(_privacy_payload(profile))

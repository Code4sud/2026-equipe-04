"""Backoffice psychologue.

Ne montre que ce que le jeune a accepté : ses compétences validées, et ses conversations
seulement s'il a activé le partage.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from flask import jsonify
from sqlalchemy import func, select

from ..errors import ApiError
from ..extensions import db
from ..models import Conversation, Role, Skill, SkillStatus, User, YouthProfile, as_utc, iso
from ..security import require_roles
from ..services import service
from . import api
from .conversations import public_message

STAFF_ROLES = (Role.PSYCHOLOGIST, Role.ADMIN)


def _youth_or_404(youth_id: uuid.UUID) -> tuple[User, YouthProfile]:
    row = db.session.execute(
        select(User, YouthProfile)
        .join(YouthProfile, YouthProfile.user_id == User.id)
        .where(User.id == youth_id, User.role == Role.YOUTH)
    ).first()
    if row is None:
        raise ApiError(404, "not_found", "Jeune introuvable.")
    return row[0], row[1]


@api.get("/backoffice/youths")
@require_roles(*STAFF_ROLES)
def list_youths():
    youths = db.session.execute(
        select(User, YouthProfile)
        .join(YouthProfile, YouthProfile.user_id == User.id)
        .where(User.role == Role.YOUTH, User.is_active.is_(True))
    ).all()

    skill_counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for youth_id, status, count in db.session.execute(
        select(Skill.youth_id, Skill.status, func.count()).group_by(Skill.youth_id, Skill.status)
    ):
        skill_counts[youth_id][status.value] = count

    activity = {
        youth_id: (count, last_at)
        for youth_id, count, last_at in db.session.execute(
            select(
                Conversation.youth_id,
                func.count(),
                func.max(Conversation.last_message_at),
            ).group_by(Conversation.youth_id)
        )
    }

    items = []
    for user, profile in youths:
        counts = skill_counts.get(user.id, {})
        conversation_count, last_at = activity.get(user.id, (0, None))
        items.append(
            {
                "id": str(user.id),
                "display_name": user.display_name,
                "share_transcripts": profile.share_transcripts,
                "conversation_count": conversation_count,
                "last_activity_at": iso(last_at),
                "validated_skills": counts.get(SkillStatus.VALIDATED.value, 0),
                "pending_skills": counts.get(SkillStatus.PENDING.value, 0),
                "_sort": as_utc(last_at).timestamp() if last_at else 0,
            }
        )
    items.sort(key=lambda item: item.pop("_sort"), reverse=True)
    return jsonify({"youths": items})


@api.get("/backoffice/youths/<uuid:youth_id>")
@require_roles(*STAFF_ROLES)
def get_youth(youth_id: uuid.UUID):
    user, profile = _youth_or_404(youth_id)
    validated = db.session.scalars(
        select(Skill)
        .where(Skill.youth_id == user.id, Skill.status == SkillStatus.VALIDATED)
        .order_by(Skill.reviewed_at.desc())
    ).all()
    pending = db.session.scalar(
        select(func.count())
        .select_from(Skill)
        .where(Skill.youth_id == user.id, Skill.status == SkillStatus.PENDING)
    )
    conversations = db.session.scalars(
        select(Conversation)
        .where(Conversation.youth_id == user.id)
        .order_by(Conversation.last_message_at.desc())
    ).all()
    return jsonify(
        {
            "youth": {
                "id": str(user.id),
                "display_name": user.display_name,
                "share_transcripts": profile.share_transcripts,
            },
            "skills": [skill.to_dict() for skill in validated],
            "pending_skills": pending,
            "conversations": [c.to_dict() for c in conversations],
        }
    )


@api.get("/backoffice/youths/<uuid:youth_id>/conversations/<uuid:conversation_id>")
@require_roles(*STAFF_ROLES)
def get_youth_conversation(youth_id: uuid.UUID, conversation_id: uuid.UUID):
    user, profile = _youth_or_404(youth_id)
    if not profile.share_transcripts:
        raise ApiError(403, "transcript_not_shared", "Ce jeune ne partage pas ses conversations.")
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None or conversation.youth_id != user.id:
        raise ApiError(404, "not_found", "Conversation introuvable.")
    transcript = service("chat").transcript(conversation)
    return jsonify(
        {
            "conversation": conversation.to_dict(),
            "messages": [public_message(message) for message in transcript["messages"]],
        }
    )

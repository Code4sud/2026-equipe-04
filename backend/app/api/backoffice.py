"""Backoffice psychologue du Centre des Possibles.

Le jeune accepte à l'inscription que son parcours soit partagé : la psychologue voit ses
discussions, tous ses talents et l'historique de ses choix, pour pouvoir en parler avec lui.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from flask import jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..errors import ApiError
from ..extensions import db
from ..models import (
    Conversation,
    GameAnswer,
    GameEvent,
    GameRun,
    Role,
    Skill,
    SkillAction,
    SkillEvent,
    SkillOrigin,
    SkillStatus,
    User,
    YouthProfile,
    as_utc,
    iso,
)
from ..security import require_roles
from ..services import service
from . import api
from .conversations import public_message

STAFF_ROLES = (Role.PSYCHOLOGIST, Role.ADMIN)
YOUTH_DECISIONS = (SkillAction.ADDED, SkillAction.REJECTED, SkillAction.RENAMED)


def _youth_or_404(youth_id: uuid.UUID) -> tuple[User, YouthProfile]:
    row = db.session.execute(
        select(User, YouthProfile)
        .join(YouthProfile, YouthProfile.user_id == User.id)
        .where(User.id == youth_id, User.role == Role.YOUTH)
    ).first()
    if row is None:
        raise ApiError(404, "not_found", "Jeune introuvable.")
    return row[0], row[1]


def _to_discuss(skill: Skill) -> bool:
    """Un talent dont le jeune s'est écarté de la proposition de Néo, ou qu'il a ajouté."""
    return any(event.action in YOUTH_DECISIONS for event in skill.events) or (
        skill.origin == SkillOrigin.YOUTH
    )


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

    decisions = dict(
        db.session.execute(
            select(SkillEvent.youth_id, func.count(func.distinct(SkillEvent.skill_id)))
            .where(SkillEvent.action.in_(YOUTH_DECISIONS))
            .group_by(SkillEvent.youth_id)
        ).all()
    )

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

    # Le quiz, les jeux, les choix du jeune sur ses talents et ses modifications dans le jeu
    # comptent aussi comme activité : un jeune qui ne fait que jouer n'est pas « inactif ».
    other_activity: dict[uuid.UUID, list] = defaultdict(list)
    for query in (
        select(GameRun.youth_id, func.max(GameRun.started_at)).group_by(GameRun.youth_id),
        select(GameRun.youth_id, func.max(GameRun.completed_at)).group_by(GameRun.youth_id),
        select(GameRun.youth_id, func.max(GameAnswer.answered_at))
        .join(GameAnswer, GameAnswer.run_id == GameRun.id)
        .group_by(GameRun.youth_id),
        select(GameEvent.youth_id, func.max(GameEvent.created_at)).group_by(GameEvent.youth_id),
        select(SkillEvent.youth_id, func.max(SkillEvent.created_at))
        .where(SkillEvent.actor == SkillOrigin.YOUTH)
        .group_by(SkillEvent.youth_id),
    ):
        for youth_id, at in db.session.execute(query):
            if at is not None:
                other_activity[youth_id].append(as_utc(at))

    # Avis donnés ou modifications faites dans le jeu : chaque détail, curseur ou réponse une fois.
    game_changes = dict(
        db.session.execute(
            select(GameEvent.youth_id, func.count(func.distinct(GameEvent.subject))).group_by(
                GameEvent.youth_id
            )
        ).all()
    )

    items = []
    for user, profile in youths:
        counts = skill_counts.get(user.id, {})
        conversation_count, chat_at = activity.get(user.id, (0, None))
        moments = [as_utc(chat_at)] if chat_at else []
        last_at = max([*moments, *other_activity.get(user.id, [])], default=None)
        items.append(
            {
                "id": str(user.id),
                "display_name": user.display_name,
                "share_transcripts": profile.share_transcripts,
                "conversation_count": conversation_count,
                "last_activity_at": iso(last_at),
                "validated_skills": counts.get(SkillStatus.VALIDATED.value, 0),
                "pending_skills": counts.get(SkillStatus.PENDING.value, 0),
                "rejected_skills": counts.get(SkillStatus.REJECTED.value, 0),
                "skills_to_discuss": decisions.get(user.id, 0),
                "game_changes": game_changes.get(user.id, 0),
                "_sort": last_at.timestamp() if last_at else 0,
            }
        )
    items.sort(key=lambda item: item.pop("_sort"), reverse=True)
    return jsonify({"youths": items})


@api.get("/backoffice/youths/<uuid:youth_id>")
@require_roles(*STAFF_ROLES)
def get_youth(youth_id: uuid.UUID):
    user, profile = _youth_or_404(youth_id)
    skills = db.session.scalars(
        select(Skill)
        .options(selectinload(Skill.events))
        .where(Skill.youth_id == user.id)
        .order_by(Skill.created_at.desc())
    ).all()
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
                "consent_at": iso(profile.consent_at),
            },
            "skills": [
                {**skill.to_dict(with_history=True), "to_discuss": _to_discuss(skill)}
                for skill in skills
            ],
            "pending_skills": sum(skill.status == SkillStatus.PENDING for skill in skills),
            "conversations": [c.to_dict() for c in conversations],
        }
    )


@api.get("/backoffice/youths/<uuid:youth_id>/conversations/<uuid:conversation_id>")
@require_roles(*STAFF_ROLES)
def get_youth_conversation(youth_id: uuid.UUID, conversation_id: uuid.UUID):
    user, _profile = _youth_or_404(youth_id)
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

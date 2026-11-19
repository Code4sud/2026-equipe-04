"""Espace jeune : conversations avec le compagnon, réponses en flux (SSE)."""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import closing

from flask import Response, current_app, g, jsonify, stream_with_context
from sqlalchemy import func, select

from ..errors import ApiError, LLMError, StorageError
from ..extensions import db
from ..models import Conversation, ConversationStatus, Role, Skill, SkillStatus, YouthProfile
from ..security import require_roles
from ..services import service
from ..services.chat import FLAG_CRISIS, FLAG_INTERRUPTED
from . import api
from .helpers import json_body, text_field

logger = logging.getLogger(__name__)


def public_message(message: dict) -> dict:
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "created_at": message["created_at"],
        "flags": message.get("flags", []),
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _own_conversation(conversation_id: uuid.UUID) -> Conversation:
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None or conversation.youth_id != g.user.id:
        raise ApiError(404, "not_found", "Conversation introuvable.")
    return conversation


def _conversation_payload(conversation: Conversation) -> dict:
    transcript = service("chat").transcript(conversation)
    messages = [public_message(message) for message in transcript["messages"]]
    crisis_card = None
    if any(FLAG_CRISIS in message["flags"] for message in messages):
        crisis_card = service("guardrails").crisis_card
    profile = db.session.get(YouthProfile, conversation.youth_id)
    return {
        "conversation": conversation.to_dict(),
        "messages": messages,
        "safety": crisis_card,
        # Le jeune voit toujours si cette discussion est lisible par la psychologue.
        "share_transcripts": bool(profile and profile.share_transcripts),
    }


@api.get("/conversations")
@require_roles(Role.YOUTH)
def list_conversations():
    conversations = db.session.scalars(
        select(Conversation)
        .where(Conversation.youth_id == g.user.id)
        .order_by(Conversation.last_message_at.desc())
    ).all()
    return jsonify({"conversations": [c.to_dict() for c in conversations]})


@api.post("/conversations")
@require_roles(Role.YOUTH)
def open_conversation():
    """Renvoie la conversation en cours, ou en démarre une nouvelle."""
    conversation, created = service("chat").get_or_create_active(g.user)
    return jsonify(_conversation_payload(conversation)), 201 if created else 200


@api.get("/conversations/<uuid:conversation_id>")
@require_roles(Role.YOUTH)
def get_conversation(conversation_id: uuid.UUID):
    return jsonify(_conversation_payload(_own_conversation(conversation_id)))


@api.post("/conversations/<uuid:conversation_id>/close")
@require_roles(Role.YOUTH)
def close_conversation(conversation_id: uuid.UUID):
    conversation = _own_conversation(conversation_id)
    service("chat").close(conversation)
    extracting = service("extraction").schedule(conversation)
    return jsonify({"conversation": conversation.to_dict(), "extracting": extracting})


@api.post("/conversations/<uuid:conversation_id>/messages")
@require_roles(Role.YOUTH)
def post_message(conversation_id: uuid.UUID):
    """Enregistre le message du jeune puis diffuse la réponse du compagnon.

    Événements : start, safety (si détresse repérée), reply, delta, done ou error.
    Avec {"retry": true}, relance la réponse au dernier message resté sans réponse.
    """
    conversation = _own_conversation(conversation_id)
    if conversation.status != ConversationStatus.ACTIVE:
        raise ApiError(409, "conversation_closed", "Cette conversation est terminée.")

    data = json_body()
    chat = service("chat")
    user_message = None
    if data.get("retry") is True:
        transcript = chat.transcript(conversation)
        last = transcript["messages"][-1]
        if last["role"] != "user":
            raise ApiError(409, "nothing_to_retry", "Aucun message en attente de réponse.")
        crisis = FLAG_CRISIS in last.get("flags", [])
    else:
        maximum = current_app.config["MAX_MESSAGE_CHARS"]
        content = text_field(data, "content", "Le message", 1, maximum)
        crisis = service("guardrails").is_crisis(content)
        flags = [FLAG_CRISIS] if crisis else []
        stored, transcript = chat.append_message(conversation.id, "user", content, flags)
        user_message = public_message(stored)

    stream = _reply_stream(
        conversation_id, g.user.id, user_message, chat.plan_reply(transcript), crisis
    )
    return Response(
        stream_with_context(stream),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _reply_stream(conversation_id, youth_id, user_message, plan, crisis):
    chat = service("chat")
    yield _sse("start", {"user_message": user_message})
    if crisis:
        yield _sse("safety", service("guardrails").crisis_card)

    # Détresse et sujets sensibles reçoivent un texte relu, jamais une génération libre.
    prepared, kind, revealed = chat.prepared_reply(plan)
    yield _sse("reply", {"kind": kind})
    if prepared is not None:
        source = _word_by_word(prepared, current_app.config["PREPARED_REPLY_WORD_DELAY"])
    else:
        source = _model_words(chat, plan)

    parts: list[str] = []
    try:
        with closing(source) as tokens:
            for token in tokens:
                # Mistral commence souvent sa réponse par une espace.
                if not parts:
                    token = token.lstrip()
                    if not token:
                        continue
                parts.append(token)
                yield _sse("delta", {"text": token})
    except LLMError as error:
        logger.error("Réponse du compagnon impossible : %s", error)
        yield _sse("error", {"code": "llm_unavailable"})
        return
    except GeneratorExit:
        _save_partial_reply(conversation_id, parts)
        raise

    reply = "".join(parts).strip()
    if not reply:
        yield _sse("error", {"code": "empty_reply"})
        return
    try:
        assistant_message, _ = chat.append_message(conversation_id, "assistant", reply)
    except StorageError as error:
        logger.error("Réponse non enregistrée : %s", error)
        yield _sse("error", {"code": "storage_unavailable"})
        return

    conversation = db.session.get(Conversation, conversation_id)
    talent = None
    if revealed is not None:
        saved = service("extraction").save_revealed(conversation, revealed)
        talent = saved.to_dict() if saved else None
    scheduled = service("extraction").maybe_schedule(conversation)
    pending = db.session.scalar(
        select(func.count())
        .select_from(Skill)
        .where(Skill.youth_id == youth_id, Skill.status == SkillStatus.PENDING)
    )
    yield _sse(
        "done",
        {
            "assistant_message": public_message(assistant_message),
            "pending_skills": pending,
            "talent": talent,
            "extracting": scheduled or conversation.is_extracting,
        },
    )


def _word_by_word(text: str, delay: float):
    for index, word in enumerate(text.split(" ")):
        if index and delay:
            time.sleep(delay)
        yield word if index == 0 else f" {word}"


def _model_words(chat, plan):
    # La réponse est vérifiée en entier avant affichage, pour écarter les répétitions.
    yield from _word_by_word(chat.model_reply(plan), current_app.config["PREPARED_REPLY_WORD_DELAY"])


def _save_partial_reply(conversation_id, parts: list[str]) -> None:
    """Le jeune a quitté pendant la réponse : on garde ce qui a été écrit."""
    reply = "".join(parts).strip()
    if not reply:
        return
    try:
        service("chat").append_message(conversation_id, "assistant", reply, [FLAG_INTERRUPTED])
    except Exception:
        logger.exception("Réponse partielle non enregistrée")

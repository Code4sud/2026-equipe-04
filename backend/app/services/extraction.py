"""Repérage des compétences dans le récit du jeune, en arrière-plan.

Le modèle propose ; le code vérifie. Une compétence n'est enregistrée que si sa citation
existe vraiment dans les messages du jeune et si elle respecte les garde-fous. Elle reste
« à valider » tant que le jeune ne l'a pas acceptée.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Flask
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from ..errors import LLMError, StorageError
from ..extensions import db
from ..models import EXTRACTION_LEASE, Conversation, Skill, SkillAction, utcnow
from .chat import FLAG_CRISIS
from .guardrails import find_quote, name_key

logger = logging.getLogger(__name__)

CATEGORIES = (
    "savoir_faire",
    "organisation",
    "relationnel",
    "communication",
    "resolution_problemes",
    "autonomie",
    "creativite",
    "apprentissage",
)
MAX_SKILLS_PER_RUN = 3
MAX_MESSAGES_PER_RUN = 12
MIN_MESSAGE_CHARS = 20

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "competences": {
            "type": "array",
            "maxItems": MAX_SKILLS_PER_RUN,
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "categorie": {"type": "string", "enum": list(CATEGORIES)},
                    "description": {"type": "string"},
                    "citation": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["nom", "categorie", "description", "citation", "message"],
            },
        }
    },
    "required": ["competences"],
}


class ExtractionService:
    def __init__(self, app: Flask, llm, store, prompts, guardrails):
        self.app = app
        self.llm = llm
        self.store = store
        self.prompts = prompts
        self.guardrails = guardrails
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extraction")

    def maybe_schedule(self, conversation: Conversation) -> bool:
        threshold = self.app.config["EXTRACTION_EVERY_MESSAGES"]
        if conversation.unprocessed_messages < threshold:
            return False
        return self.schedule(conversation)

    def schedule(self, conversation: Conversation) -> bool:
        """Lance une analyse s'il reste des messages et qu'aucune n'est en cours."""
        if conversation.unprocessed_messages <= 0:
            return False
        conversation_id = conversation.id
        if not self._claim(conversation_id):
            return False
        if self.app.config["EXTRACTION_SYNC"]:
            self._run(conversation_id)
        else:
            self._executor.submit(self._run, conversation_id)
        return True

    def _claim(self, conversation_id: uuid.UUID) -> bool:
        now = utcnow()
        result = db.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                or_(
                    Conversation.extraction_started_at.is_(None),
                    Conversation.extraction_started_at < now - EXTRACTION_LEASE,
                ),
            )
            .values(extraction_started_at=now)
        )
        db.session.commit()
        return result.rowcount == 1

    def _run(self, conversation_id: uuid.UUID) -> None:
        with self.app.app_context():
            processed = None
            try:
                processed = self._extract(conversation_id)
            except (LLMError, StorageError) as error:
                # Les messages restent à traiter : la prochaine analyse les reprendra.
                logger.warning("Analyse reportée pour %s : %s", conversation_id, error)
            except Exception:
                logger.exception("Analyse en échec pour %s", conversation_id)
            finally:
                db.session.rollback()
                values = {"extraction_started_at": None}
                if processed is not None:
                    values["extracted_message_count"] = processed
                db.session.execute(
                    update(Conversation).where(Conversation.id == conversation_id).values(**values)
                )
                db.session.commit()

    def _extract(self, conversation_id: uuid.UUID) -> int:
        conversation = db.session.get(Conversation, conversation_id)
        transcript = self.store.load(conversation.transcript_key)
        all_messages = transcript["messages"]
        new_messages = all_messages[conversation.extracted_message_count :]
        candidates = [
            message
            for message in new_messages
            if message["role"] == "user"
            and FLAG_CRISIS not in message.get("flags", [])
            and len(message["content"]) >= MIN_MESSAGE_CHARS
        ][-MAX_MESSAGES_PER_RUN:]
        if not candidates:
            return len(all_messages)

        existing = db.session.execute(
            select(Skill.name, Skill.name_key, Skill.source_quote).where(
                Skill.youth_id == conversation.youth_id
            )
        ).all()
        known_keys = {row.name_key for row in existing}
        known_quotes = {name_key(row.source_quote) for row in existing}

        answer = self.llm.generate_json(
            self.prompts.extraction,
            self._user_prompt(candidates, [row.name for row in existing]),
            RESPONSE_SCHEMA,
        )
        proposals = answer.get("competences", []) if isinstance(answer, dict) else []
        aliases = {f"m{index}": m["id"] for index, m in enumerate(candidates, start=1)}

        accepted = 0
        for proposal in proposals:
            if accepted >= MAX_SKILLS_PER_RUN:
                break
            skill = self._build_skill(conversation, proposal, candidates, aliases)
            if skill is None or skill.name_key in known_keys:
                continue
            quote_key = name_key(skill.source_quote)
            if quote_key in known_quotes:
                continue
            try:
                with db.session.begin_nested():
                    skill.record(SkillAction.PROPOSED)
                    db.session.add(skill)
            except IntegrityError:
                continue
            known_keys.add(skill.name_key)
            known_quotes.add(quote_key)
            accepted += 1
        db.session.commit()
        return len(all_messages)

    def _build_skill(self, conversation, proposal, candidates, aliases) -> Skill | None:
        if not isinstance(proposal, dict):
            return None
        name = str(proposal.get("nom", "")).strip()[:80]
        description = str(proposal.get("description", "")).strip()[:300]
        citation = str(proposal.get("citation", "")).strip()
        category = proposal.get("categorie")
        if len(name) < 3 or not name_key(name):
            return None
        match = find_quote(citation, candidates, aliases.get(str(proposal.get("message", ""))))
        if match is None:
            return None
        description = self.guardrails.review_skill(name, description, match.quote)
        if description is None:
            return None
        return Skill(
            youth_id=conversation.youth_id,
            conversation_id=conversation.id,
            source_message_id=match.message_id,
            name=name,
            name_key=name_key(name),
            category=category if category in CATEGORIES else "savoir_faire",
            description=description,
            source_quote=match.quote,
        )

    @staticmethod
    def _user_prompt(candidates: list[dict], known_names: list[str]) -> str:
        lines = [f"[m{index}] {m['content']}" for index, m in enumerate(candidates, start=1)]
        known = ", ".join(known_names) if known_names else "aucune"
        return (
            "Messages écrits par le jeune :\n"
            + "\n".join(lines)
            + f"\n\nCompétences déjà repérées, à ne pas répéter : {known}"
        )

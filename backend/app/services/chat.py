"""Vie d'une conversation : création, ajout de messages, contexte envoyé au modèle."""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..errors import LLMError
from ..extensions import db
from ..models import Conversation, ConversationStatus, User, utcnow
from .guardrails import find_quote, matches_any, name_key, words
from .transcripts import new_message, new_transcript, transcript_key

logger = logging.getLogger(__name__)

FLAG_CRISIS = "crisis"
FLAG_INTERRUPTED = "interrupted"
# Après un message de détresse, le compagnon reste prudent pendant quelques échanges.
RECENT_CRISIS_WINDOW = 3
FOLLOW_UP_WORDS = 20
REVEAL_SOURCE_MESSAGES = 2
MAX_REVEAL_QUOTE_CHARS = 140
MAX_REVEAL_SKILL_CHARS = 70
_INFINITIVE = re.compile(r"^(?:s |se |me )?\w+(?:er|ir|re)\b")

REVEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "citation": {"type": "string"},
        "savoir_faire": {"type": "string"},
    },
    "required": ["citation", "savoir_faire"],
}


@dataclass(frozen=True)
class ReplyPlan:
    fixed_text: str | None = None
    # Réponse générée au fil de l'eau, aussi utilisée si la révélation n'aboutit pas.
    messages: list[dict] | None = None
    reveal_from: tuple[dict, ...] = ()
    reveal_formula: str = ""
    companion_text: str = ""


class ChatService:
    def __init__(self, llm, store, prompts, guardrails):
        self.llm = llm
        self.store = store
        self.prompts = prompts
        self.guardrails = guardrails

    def active_conversation(self, youth_id: uuid.UUID) -> Conversation | None:
        return db.session.scalar(
            select(Conversation).where(
                Conversation.youth_id == youth_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
        )

    def get_or_create_active(self, youth: User) -> tuple[Conversation, bool]:
        existing = self.active_conversation(youth.id)
        if existing:
            return existing, False

        youth_id = youth.id
        conversation_id = uuid.uuid4()
        key = transcript_key(youth_id, conversation_id)
        transcript = new_transcript(youth_id, conversation_id)
        transcript["messages"].append(new_message("assistant", self.prompts.greeting))

        conversation = Conversation(
            id=conversation_id,
            youth_id=youth_id,
            transcript_key=key,
            message_count=1,
            # L'accueil n'est pas un message du jeune : rien à analyser.
            extracted_message_count=1,
        )
        db.session.add(conversation)
        try:
            db.session.flush()
        except IntegrityError:
            # Deux requêtes simultanées : la contrainte garantit une seule conversation active.
            db.session.rollback()
            return self.active_conversation(youth_id), False
        try:
            self.store.save(key, transcript)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return conversation, True

    def transcript(self, conversation: Conversation) -> dict:
        return self.store.load(conversation.transcript_key)

    def append_message(
        self, conversation_id: uuid.UUID, role: str, content: str, flags: list[str] | None = None
    ) -> tuple[dict, dict]:
        # Le verrou de ligne évite de perdre un message si deux écritures se croisent.
        conversation = db.session.execute(
            select(Conversation).where(Conversation.id == conversation_id).with_for_update()
        ).scalar_one()
        try:
            transcript = self.store.load(conversation.transcript_key)
            message = new_message(role, content, flags)
            transcript["messages"].append(message)
            self.store.save(conversation.transcript_key, transcript)
            conversation.message_count = len(transcript["messages"])
            conversation.last_message_at = utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return message, transcript

    def close(self, conversation: Conversation) -> None:
        if conversation.status == ConversationStatus.ACTIVE:
            conversation.status = ConversationStatus.CLOSED
            conversation.closed_at = utcnow()
            db.session.commit()

    def plan_reply(self, transcript: dict) -> ReplyPlan:
        """Choisit entre un texte relu (cas sensibles) et une réponse du modèle."""
        youth_messages = [m for m in transcript["messages"] if m["role"] == "user"]
        last = youth_messages[-1]
        turn = len(youth_messages)
        text = last["content"]

        if FLAG_CRISIS in last.get("flags", []):
            return ReplyPlan(fixed_text=self.guardrails.crisis_reply)
        sensitive = self.guardrails.sensitive_reply(text, turn)
        # Une courte relance juste après un sujet sensible reste sur ce sujet.
        if not sensitive and len(youth_messages) > 1 and len(words(text)) < FOLLOW_UP_WORDS:
            sensitive = self.guardrails.sensitive_reply(youth_messages[-2]["content"], turn)
        if sensitive:
            return ReplyPlan(fixed_text=sensitive)

        settings = self.prompts.conversation
        if matches_any(text, settings["identite"]["declencheurs"]):
            return ReplyPlan(fixed_text=settings["identite"]["reponse"])
        relaunch = settings["relances"]
        if " ".join(words(text)) in {" ".join(words(t)) for t in relaunch["declencheurs"]}:
            replies = relaunch["reponses"]
            return ReplyPlan(fixed_text=replies[turn % len(replies)])

        in_crisis = any(
            FLAG_CRISIS in m.get("flags", []) for m in youth_messages[-RECENT_CRISIS_WINDOW:]
        )
        messages = self._llm_messages(transcript, settings, in_crisis)
        turns = settings["tours"]
        every = turns["revelation_tous_les"]
        if in_crisis or turn % every or len(words(text)) < turns["mots_minimum_revelation"]:
            return ReplyPlan(messages=messages)

        formulas = turns["formules_revelation"]
        return ReplyPlan(
            messages=messages,
            reveal_from=tuple(youth_messages[-REVEAL_SOURCE_MESSAGES:]),
            reveal_formula=formulas[(turn // every - 1) % len(formulas)],
            companion_text=" ".join(
                name_key(m["content"]) for m in transcript["messages"] if m["role"] == "assistant"
            ),
        )

    def prepared_reply(self, plan: ReplyPlan) -> str | None:
        """Texte déjà prêt pour ce tour, ou None s'il faut laisser le modèle écrire."""
        if plan.fixed_text is not None:
            return plan.fixed_text
        return self._reveal(plan) if plan.reveal_from else None

    def _reveal(self, plan: ReplyPlan) -> str | None:
        """Compose la révélation d'une compétence à partir d'une citation vérifiée.

        Le modèle propose la citation et le savoir-faire, le code écrit la phrase. Si le
        résultat n'est pas sûr, le compagnon continue simplement à écouter.
        """
        lines = [f"[m{i}] {m['content']}" for i, m in enumerate(plan.reveal_from, start=1)]
        try:
            answer = self.llm.generate_json(self.prompts.reveal, "\n".join(lines), REVEAL_SCHEMA)
        except LLMError as error:
            logger.warning("Révélation impossible : %s", error)
            return None
        if not isinstance(answer, dict):
            return None

        skill = str(answer.get("savoir_faire", "")).strip().rstrip(".!").strip()
        match = find_quote(str(answer.get("citation", "")), list(plan.reveal_from))
        if match is None or len(match.quote) > MAX_REVEAL_QUOTE_CHARS:
            return None
        if not skill or len(skill) > MAX_REVEAL_SKILL_CHARS:
            return None
        if not _INFINITIVE.match(" ".join(words(skill))):
            return None
        if self.guardrails.review_skill(skill, "", match.quote) is None:
            return None
        if name_key(match.quote) in plan.companion_text:
            return None
        skill = skill[0].lower() + skill[1:]
        return plan.reveal_formula.format(citation=match.quote, savoir_faire=skill)

    def _llm_messages(self, transcript: dict, settings: dict, in_crisis: bool) -> list[dict]:
        limit = current_app.config["CHAT_HISTORY_MESSAGES"]
        recent = transcript["messages"][-limit:]
        # Le format de Mistral attend un échange qui commence par la personne.
        while recent and recent[0]["role"] == "assistant":
            recent = recent[1:]

        parts = [self.prompts.companion]
        family = self.guardrails.family_instruction(recent[-1]["content"])
        if family:
            parts.append(family)
        parts.append(
            self.guardrails.crisis_instruction if in_crisis else settings["tours"]["ecoute"]
        )
        parts.append(settings["fin_de_consigne"])

        history = [{"role": m["role"], "content": m["content"]} for m in recent]
        return [{"role": "system", "content": "\n\n".join(parts)}, *history]

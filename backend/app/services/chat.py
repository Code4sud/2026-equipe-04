"""Vie d'une conversation : création, ajout de messages, contexte envoyé au modèle."""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..errors import LLMError
from ..extensions import db
from ..models import Conversation, ConversationStatus, User, utcnow
from .guardrails import find_quote, matches_any, name_key, words
from .referentiel import CATEGORIES
from .transcripts import new_message, new_transcript, transcript_key

logger = logging.getLogger(__name__)

FLAG_CRISIS = "crisis"
FLAG_INTERRUPTED = "interrupted"
# Après un message de détresse, le compagnon reste prudent pendant quelques échanges.
RECENT_CRISIS_WINDOW = 3
FOLLOW_UP_WORDS = 20
REVEAL_SOURCE_MESSAGES = 1
SHORT_MESSAGE_WORDS = 3
PASSIVE_MESSAGE_WORDS = 6
MIN_STORY_WORDS = 4
MAX_ENCOURAGING_QUOTE_CHARS = 90
MODEL_ATTEMPTS = 2
RECENT_REPLIES_COMPARED = 6
SIMILAR_REPLY_RATIO = 0.72
QUESTION_TEMPERATURES = (0.35, 0.5, 0.65)
MAX_REACTION_WORDS = 13
MAX_QUESTION_WORDS = 18
MAX_FREE_REPLY_WORDS = 35
# Tournures fréquentes de Mistral en français : « tu choisis-tu », « tu organisez », « Il semble ».
_BROKEN_FRENCH = re.compile(
    r"\btu\s+(?:[\w’'-]+\s+){0,2}?[\w’'-]+-tu\b|\btu\s+(?:les?\s+|la\s+)?\w+ez\b|\bt[’']\w+-tu\b",
    re.IGNORECASE,
)
_THIRD_PERSON_START = re.compile(r"^(?:il|elle|on dirait|la personne)\b", re.IGNORECASE)
RECENT_STORY_MESSAGES = 4
RECENT_QUESTIONS = 4
COMMON_WORDS = frozenset(
    "alors aussi avec avoir beaucoup comme dans depuis des fois fait faire fais juste mais meme "
    "moins plus pour quand quoi sais suis sans sont souvent tout tous tres trop vraiment".split()
)
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"reaction": {"type": "string"}, "question": {"type": "string"}},
    "required": ["reaction", "question"],
}
SIMILAR_QUESTION_RATIO = 0.8
MAX_REVEAL_QUOTE_CHARS = 140
MAX_REVEAL_SKILL_CHARS = 70
_INFINITIVE = re.compile(r"^(?:s |se |me )?\w+(?:er|ir|re)\b")

REVEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "citation": {"type": "string"},
        "savoir_faire": {"type": "string"},
        "categorie": {"type": "string", "enum": list(CATEGORIES)},
    },
    "required": ["citation", "savoir_faire", "categorie"],
}


@dataclass(frozen=True)
class RevealedTalent:
    """Talent annoncé par Néo dans sa réponse, enregistré tout de suite pour le jeune."""

    name: str
    quote: str
    message_id: str
    category: str = ""


@dataclass(frozen=True)
class ReplyPlan:
    kind: str = "model"
    fixed_text: str | None = None
    # Réponse générée au fil de l'eau, aussi utilisée si la révélation n'aboutit pas.
    messages: list[dict] | None = None
    reveal_from: tuple[dict, ...] = ()
    reveal_formula: str = ""
    companion_text: str = ""
    previous_replies: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    question_prompt: str | None = None
    last_message: str = ""
    generic_questions: tuple[str, ...] = ()
    fallback_replies: tuple[str, ...] = ()
    turn: int = 0


def _similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, words(first), words(second), autojunk=False).ratio()


def _last_sentence(text: str) -> str:
    parts = [part for part in re.split(r"(?<=[.!?…])\s+", text.strip()) if words(part)]
    return parts[-1] if parts else ""


def _is_repetition(reply: str, previous: tuple[str, ...]) -> bool:
    question = _last_sentence(reply)
    return any(
        _similarity(reply, earlier) >= SIMILAR_REPLY_RATIO
        or _similarity(question, _last_sentence(earlier)) >= SIMILAR_QUESTION_RATIO
        for earlier in previous
    )


def _reads_badly(text: str) -> bool:
    return bool(_BROKEN_FRENCH.search(text) or _THIRD_PERSON_START.match(text.strip()))


def _topic_stems(text: str) -> set[str]:
    return {word[:4] for word in words(text) if len(word) >= 4 and word not in COMMON_WORDS}


def _fresh_reply(replies: list[str] | tuple[str, ...], said: list[str], turn: int) -> str:
    """Prend la prochaine réponse pas encore dite dans cette conversation."""
    rotated = [replies[(turn + index) % len(replies)] for index in range(len(replies))]
    return next((reply for reply in rotated if reply not in said), rotated[0])


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
            return ReplyPlan(kind="crisis", fixed_text=self.guardrails.crisis_reply)
        sensitive = self.guardrails.sensitive_reply(text, turn)
        # Une courte relance juste après un sujet sensible reste sur ce sujet.
        if not sensitive and len(youth_messages) > 1 and len(words(text)) < FOLLOW_UP_WORDS:
            sensitive = self.guardrails.sensitive_reply(youth_messages[-2]["content"], turn)
        if sensitive:
            return ReplyPlan(kind="sensitive", fixed_text=sensitive)

        settings = self.prompts.conversation
        if matches_any(text, settings["identite"]["declencheurs"]):
            return ReplyPlan(kind="identity", fixed_text=settings["identite"]["reponse"])
        said = [m["content"] for m in transcript["messages"] if m["role"] == "assistant"]
        if matches_any(text, settings["encouragement"]["declencheurs"]):
            reply = self._encouragement(youth_messages[:-1], said, turn, settings)
            return ReplyPlan(kind="encourage", fixed_text=reply)
        normalized = " ".join(words(text))
        is_one_of = lambda triggers: normalized in {" ".join(words(t)) for t in triggers}
        if is_one_of(settings["salutations"]["declencheurs"]):
            reply = _fresh_reply(settings["salutations"]["reponses"], said, turn)
            return ReplyPlan(kind="greeting", fixed_text=reply)
        relaunch = settings["relances"]
        passive = len(words(text)) <= PASSIVE_MESSAGE_WORDS and matches_any(
            text, relaunch["messages_passifs"]
        )
        if passive or is_one_of(relaunch["declencheurs"]):
            reply = _fresh_reply(settings["relances"]["reponses"], said, turn)
            return ReplyPlan(kind="relaunch", fixed_text=reply)
        # Trop peu de matière pour le modèle : il inventerait ou se répéterait.
        if len(words(text)) < SHORT_MESSAGE_WORDS:
            return ReplyPlan(kind="followup", fixed_text=_fresh_reply(settings["rebonds"], said, turn))

        in_crisis = any(
            FLAG_CRISIS in m.get("flags", []) for m in youth_messages[-RECENT_CRISIS_WINDOW:]
        )
        messages = self._llm_messages(transcript, settings, in_crisis, turn)
        generation = {
            "messages": messages,
            "previous_replies": tuple(said[-RECENT_REPLIES_COMPARED:]),
            "fallback_replies": tuple(settings["rebonds"]),
            "turn": turn,
            "forbidden_phrases": tuple(settings["phrases_interdites"]),
        }
        turns = settings["tours"]
        if not in_crisis:
            generation.update(
                question_prompt=self._question_prompt(youth_messages, said, turn, turns),
                last_message=text,
                generic_questions=tuple(turns["questions_passe_partout"]),
            )
        every = turns["revelation_tous_les"]
        if in_crisis or turn % every or len(words(text)) < turns["mots_minimum_revelation"]:
            return ReplyPlan(**generation)

        formulas = turns["formules_revelation"]
        return ReplyPlan(
            **generation,
            reveal_from=tuple(youth_messages[-REVEAL_SOURCE_MESSAGES:]),
            reveal_formula=formulas[(turn // every - 1) % len(formulas)],
            companion_text=" ".join(
                name_key(m["content"]) for m in transcript["messages"] if m["role"] == "assistant"
            ),
        )

    def _encouragement(
        self, earlier: list[dict], said: list[str], turn: int, settings: dict
    ) -> str:
        """Répond au doute en s'appuyant, si possible, sur ce que le jeune a déjà raconté."""
        texts = settings["encouragement"]
        for message in reversed(earlier):
            story = message["content"].strip().rstrip(".!")
            usable = (
                MIN_STORY_WORDS <= len(words(story))
                and len(story) <= MAX_ENCOURAGING_QUOTE_CHARS
                and FLAG_CRISIS not in message.get("flags", [])
                and not matches_any(story, texts["declencheurs"])
                and self.guardrails.review_skill(story, "", "") is not None
            )
            if usable:
                options = [option.format(citation=story) for option in texts["avec_citation"]]
                return _fresh_reply(options, said, turn)
        return _fresh_reply(texts["sans_citation"], said, turn)

    def prepared_reply(self, plan: ReplyPlan) -> tuple[str | None, str, RevealedTalent | None]:
        """Texte déjà prêt pour ce tour (ou None), type de réponse et talent révélé."""
        if plan.fixed_text is not None:
            return plan.fixed_text, plan.kind, None
        revealed = self._reveal(plan) if plan.reveal_from else None
        if revealed is None:
            return None, "model", None
        text, talent = revealed
        return text, "reveal", talent

    def model_reply(self, plan: ReplyPlan) -> str:
        """Fait écrire le modèle, en refusant qu'il répète ce qui vient d'être dit."""
        personal = self._personal_reply(plan)
        if personal:
            return personal
        messages = list(plan.messages or [])
        for _ in range(MODEL_ATTEMPTS):
            reply = "".join(self.llm.chat_stream(messages)).strip().strip('"').strip()
            usable = (
                reply
                and len(words(reply)) <= MAX_FREE_REPLY_WORDS
                and not _reads_badly(reply)
                and self.guardrails.review_skill(reply, "", "") is not None
                and not matches_any(reply, list(plan.forbidden_phrases))
            )
            if usable and not _is_repetition(reply, plan.previous_replies):
                return reply
            logger.info("Réponse répétitive écartée")
            messages = [
                {
                    "role": "system",
                    "content": f"{messages[0]['content']}\n\nTa réponse précédente répétait la "
                    "conversation. Réagis à son dernier message et pose une question nouvelle.",
                },
                *messages[1:],
            ]
        return _fresh_reply(plan.fallback_replies, list(plan.previous_replies), plan.turn)

    def _question_prompt(
        self, youth_messages: list[dict], said: list[str], turn: int, turns: dict
    ) -> str:
        last = youth_messages[-1]["content"]
        story = [
            m["content"] for m in youth_messages[:-1] if len(words(m["content"])) >= SHORT_MESSAGE_WORDS
        ][-RECENT_STORY_MESSAGES:]
        asked = [_last_sentence(reply) for reply in said if "?" in reply][-RECENT_QUESTIONS:]
        tracks = turns["pistes_question"]
        lines = []
        if story:
            lines.append("Déjà raconté :\n" + "\n".join(f"- {item}" for item in story))
        if asked:
            lines.append("Questions déjà posées :\n" + "\n".join(f"- {item}" for item in asked))
        lines.append(f"Piste : {tracks[turn % len(tracks)]}")
        family = self.guardrails.family_instruction(last)
        if family:
            lines.append(family)
        lines.append(f"Dernier message : {last}")
        return "\n\n".join(lines)

    def _personal_reply(self, plan: ReplyPlan) -> str | None:
        """Construit une réaction et une question propres à ce que le jeune vient de dire."""
        if not plan.question_prompt:
            return None
        prompt = plan.question_prompt
        examples = []
        for example in self.prompts.question_examples:
            examples.append({"role": "user", "content": example["demande"]})
            answer = json.dumps(example["reponse"], ensure_ascii=False)
            examples.append({"role": "assistant", "content": answer})
        for temperature in QUESTION_TEMPERATURES:
            answer = self.llm.generate_json(
                self.prompts.question,
                prompt,
                QUESTION_SCHEMA,
                temperature=temperature,
                examples=examples,
            )
            reply = self._checked_question(answer, plan)
            if reply:
                return reply
            prompt = f"{plan.question_prompt}\n\nSois plus simple et plus précis que ta proposition précédente."
        return None

    def _checked_question(self, answer: object, plan: ReplyPlan) -> str | None:
        if not isinstance(answer, dict):
            return None
        reaction = str(answer.get("reaction", "")).strip()
        question = str(answer.get("question", "")).strip()
        if not reaction or "?" in reaction or not question.endswith("?") or question.count("?") != 1:
            return None
        if len(words(reaction)) > MAX_REACTION_WORDS or len(words(question)) > MAX_QUESTION_WORDS:
            return None
        if re.search(r"[.!…]", question) or _reads_badly(reaction) or _reads_badly(question):
            return None
        normalized = " ".join(words(question))
        if any(" ".join(words(generic)) in normalized for generic in plan.generic_questions):
            return None
        reply = f"{reaction} {question}"
        topic = _topic_stems(plan.last_message)
        if topic and not topic & _topic_stems(reply):
            return None
        if self.guardrails.review_skill(reply, "", "") is None:
            return None
        if matches_any(reply, list(plan.forbidden_phrases)):
            return None
        return None if _is_repetition(reply, plan.previous_replies) else reply

    def _reveal(self, plan: ReplyPlan) -> tuple[str, RevealedTalent] | None:
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
        if matches_any(match.quote, self.prompts.conversation["tours"]["echecs_sans_revelation"]):
            return None
        if not skill or len(skill) > MAX_REVEAL_SKILL_CHARS:
            return None
        if not _INFINITIVE.match(" ".join(words(skill))):
            return None
        if self.guardrails.review_talent(skill, "", match.quote) is None:
            return None
        if name_key(match.quote) in plan.companion_text:
            return None
        category = answer.get("categorie")
        talent = RevealedTalent(
            skill[0].upper() + skill[1:],
            match.quote,
            match.message_id,
            category if category in CATEGORIES else "",
        )
        skill = skill[0].lower() + skill[1:]
        return plan.reveal_formula.format(citation=match.quote, savoir_faire=skill), talent

    def _llm_messages(
        self, transcript: dict, settings: dict, in_crisis: bool, turn: int
    ) -> list[dict]:
        limit = current_app.config["CHAT_HISTORY_MESSAGES"]
        recent = transcript["messages"][-limit:]
        # Le format de Mistral attend un échange qui commence par la personne.
        while recent and recent[0]["role"] == "assistant":
            recent = recent[1:]

        parts = [self.prompts.companion]
        family = self.guardrails.family_instruction(recent[-1]["content"])
        if family:
            parts.append(family)
        turns = settings["tours"]
        angles = turns["angles_ecoute"]
        listening = turns["ecoute"].format(angle=angles[turn % len(angles)])
        parts.append(self.guardrails.crisis_instruction if in_crisis else listening)
        parts.append(settings["fin_de_consigne"])

        # Une phrase déjà répétée dans l'historique pousserait le modèle à continuer.
        history = []
        seen: set[str] = set()
        for message in recent:
            key = " ".join(words(message["content"]))
            if message["role"] == "assistant" and key in seen:
                continue
            seen.add(key)
            history.append({"role": message["role"], "content": message["content"]})
        return [{"role": "system", "content": "\n\n".join(parts)}, *history]

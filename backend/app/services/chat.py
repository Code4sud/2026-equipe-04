"""Vie d'une conversation : création, ajout de messages, contexte envoyé au modèle."""
from __future__ import annotations

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
# Réponse de Truffe qui annonce un talent : la réponse courte qui suit en tient compte.
FLAG_REVEAL = "revelation"
# Le jeune confie subir des violences : orienté vers de l'aide, signalé à la psychologue.
FLAG_VICTIM = "victime"
# Sujet interdit (sexe, actes illégaux, violence, haine) : Truffe n'en parle pas.
FLAG_OFF_LIMITS = "hors_cadre"
# Messages jamais analysés pour les talents ni relus par le modèle de discussion.
SHIELDED_FLAGS = (FLAG_CRISIS, FLAG_VICTIM, FLAG_OFF_LIMITS)
HIDDEN_FROM_MODEL = "[message retiré : sujet dont Truffe ne parle pas]"
# Après un message de détresse, le compagnon reste prudent pendant quelques échanges.
RECENT_CRISIS_WINDOW = 3
FOLLOW_UP_WORDS = 20
REVEAL_SOURCE_MESSAGES = 1
SHORT_MESSAGE_WORDS = 3
PASSIVE_MESSAGE_WORDS = 6
BRIEF_MESSAGE_WORDS = 8
MIN_STORY_WORDS = 4
MAX_ENCOURAGING_QUOTE_CHARS = 90
RECENT_REPLIES_COMPARED = 6
SIMILAR_REPLY_RATIO = 0.72
SIMILAR_QUESTION_RATIO = 0.8
REPLY_TEMPERATURES = (0.7, 0.8, 0.9)
MAX_FREE_REPLY_WORDS = 45
MAX_REVEAL_QUOTE_CHARS = 140
MAX_REVEAL_SKILL_CHARS = 70
_INFINITIVE = re.compile(r"^(?:s |se |me )?\w+(?:er|ir|re)\b")
# Tournures fautives fréquentes des petits modèles : « tu choisis-tu », « tu organisez ».
_BROKEN_FRENCH = re.compile(
    r"\btu\s+(?:[\w’'-]+\s+){0,2}?[\w’'-]+-tu\b|\btu\s+(?:les?\s+|la\s+)?\w+ez\b|\bt[’']\w+-tu\b",
    re.IGNORECASE,
)
_THIRD_PERSON_START = re.compile(r"^(?:il|elle|on dirait|la personne)\b", re.IGNORECASE)
# Mot répété par erreur : « une sacrée sacrée dose » (« vous vous » reste correct).
_REPEATED_WORD = re.compile(r"\b(?!(?:nous|vous)\b)(\w{3,})\s+\1\b", re.IGNORECASE)
# Élision oubliée : « qui te occupe », « je aime », « de un ».
_MISSING_ELISION = re.compile(
    r"\b(?:je|me|te|se|le|la|ne|de|que)\s+(?!(?:ouf|oui|ouais|onze|un|une|ouest|ok)\b)[aeiouéèêàâîïôû]\w*",
    re.IGNORECASE,
)
_GREETING_START = re.compile(r"^(?:salut|bonjour|bonsoir|coucou|hello|hey)\b", re.IGNORECASE)
# Le lecteur de talents s'en charge avec une citation vérifiée : le compagnon n'en parle pas.
_TALENT_WORDS = re.compile(r"\b(?:talents?|compétences?)\b", re.IGNORECASE)
_SPEAKER_PREFIX = re.compile(r"^\s*(?:truffe|toi|moi)\s*:\s*", re.IGNORECASE)

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
    """Talent annoncé par Truffe dans sa réponse, enregistré tout de suite pour le jeune."""

    name: str
    quote: str
    message_id: str
    category: str = ""


@dataclass(frozen=True)
class ReplyPlan:
    kind: str = "model"
    fixed_text: str | None = None
    # Réponse générée par le modèle, aussi utilisée si la révélation n'aboutit pas.
    messages: list[dict] | None = None
    reveal_from: tuple[dict, ...] = ()
    reveal_formula: str = ""
    companion_text: str = ""
    previous_replies: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    fallback_replies: tuple[str, ...] = ()
    turn: int = 0
    # Ce tour-ci, Truffe réagit ou invite à raconter sans poser de question.
    no_question: bool = False


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
    return bool(
        _BROKEN_FRENCH.search(text)
        or _THIRD_PERSON_START.match(text.strip())
        or _MISSING_ELISION.search(text)
        or _REPEATED_WORD.search(text)
    )


def _clean_reply(text: str) -> str:
    reply = _SPEAKER_PREFIX.sub("", text.strip())
    return reply.strip().strip('"“”«»').strip()


def _fresh_reply(replies: list[str] | tuple[str, ...], said: list[str], turn: int) -> str:
    """Prend la prochaine réponse pas encore dite dans cette conversation."""
    rotated = [replies[(turn + index) % len(replies)] for index in range(len(replies))]
    return next((reply for reply in rotated if reply not in said), rotated[0])


def is_shielded(message: dict) -> bool:
    return any(flag in message.get("flags", []) for flag in SHIELDED_FLAGS)


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
        flags = last.get("flags", [])
        said = [m["content"] for m in transcript["messages"] if m["role"] == "assistant"]

        if FLAG_CRISIS in flags:
            return ReplyPlan(kind="crisis", fixed_text=self.guardrails.crisis_reply)
        earlier_flags = {flag for m in youth_messages[:-1] for flag in m.get("flags", [])}
        if FLAG_VICTIM in flags:
            if FLAG_VICTIM in earlier_flags:
                # La confidence continue : les numéros sont déjà affichés, on ne les répète pas.
                follow = self.guardrails.victim_texts["reponses_suite"]
                return ReplyPlan(kind="victim", fixed_text=_fresh_reply(follow, said, turn))
            return ReplyPlan(kind="victim", fixed_text=self.guardrails.victim_reply)
        if FLAG_OFF_LIMITS in flags:
            reply = self._off_limits_reply(youth_messages[:-1], said, turn)
            return ReplyPlan(kind="off_limits", fixed_text=reply)
        brief = len(words(text)) < BRIEF_MESSAGE_WORDS
        previous_flags = youth_messages[-2].get("flags", []) if turn > 1 else []
        if brief and FLAG_OFF_LIMITS in previous_flags:
            # « Pourquoi ? » juste après un refus : on explique, sans revenir sur le sujet.
            reply = self._off_limits_reply(youth_messages[:-1], said, turn, explain=True)
            return ReplyPlan(kind="off_limits", fixed_text=reply)
        if brief and (FLAG_VICTIM in previous_flags or FLAG_CRISIS in previous_flags):
            texts = (
                self.guardrails.victim_texts["apres_confidence"]
                if FLAG_VICTIM in previous_flags
                else self.guardrails.crisis_follow_ups
            )
            return ReplyPlan(kind="sensitive", fixed_text=_fresh_reply(texts, said, turn))
        sensitive = self.guardrails.sensitive_reply(text, turn)
        # Une courte relance juste après un sujet sensible reste sur ce sujet.
        if not sensitive and len(youth_messages) > 1 and len(words(text)) < FOLLOW_UP_WORDS:
            sensitive = self.guardrails.sensitive_reply(youth_messages[-2]["content"], turn)
        if sensitive:
            return ReplyPlan(kind="sensitive", fixed_text=sensitive)

        settings = self.prompts.conversation
        if matches_any(text, settings["identite"]["declencheurs"]):
            return ReplyPlan(kind="identity", fixed_text=settings["identite"]["reponse"])
        if matches_any(text, settings["encouragement"]["declencheurs"]):
            reply = self._encouragement(youth_messages[:-1], said, turn, settings)
            return ReplyPlan(kind="encourage", fixed_text=reply)
        normalized = " ".join(words(text))
        is_one_of = lambda triggers: normalized in {" ".join(words(t)) for t in triggers}
        assistant = [m for m in transcript["messages"] if m["role"] == "assistant"]
        if assistant and FLAG_REVEAL in assistant[-1].get("flags", []):
            # « Ouais » juste après un talent annoncé : on le fête ou on rassure, sans relancer à vide.
            after = settings["apres_revelation"]
            if is_one_of(after["oui"]):
                return ReplyPlan(kind="reveal_answer", fixed_text=_fresh_reply(after["reponses_oui"], said, turn))
            if is_one_of(after["non"]):
                return ReplyPlan(kind="reveal_answer", fixed_text=_fresh_reply(after["reponses_non"], said, turn))
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
        if len(words(text)) < SHORT_MESSAGE_WORDS:
            # « Ouais » ne dit rien : relance relue. « Jett » répond à sa question : le modèle
            # rebondit dessus, c'est ce qui rend la discussion naturelle.
            asked = bool(assistant) and "?" in assistant[-1]["content"]
            if not asked or is_one_of(settings["acquiescements"]["mots"]):
                return ReplyPlan(kind="followup", fixed_text=_fresh_reply(settings["rebonds"], said, turn))

        in_crisis = any(
            FLAG_CRISIS in m.get("flags", []) for m in youth_messages[-RECENT_CRISIS_WINDOW:]
        )
        turns = settings["tours"]
        instruction, no_question = self._turn_instruction(transcript, turns, turn)
        if in_crisis:
            instruction, no_question = self.guardrails.crisis_instruction, False
        generation = {
            "messages": self._llm_messages(transcript, settings, instruction),
            "previous_replies": tuple(said[-RECENT_REPLIES_COMPARED:]),
            "fallback_replies": tuple(settings["rebonds"]),
            "turn": turn,
            "forbidden_phrases": tuple(settings["phrases_interdites"]),
            "no_question": no_question,
        }
        every = turns["revelation_tous_les"]
        if in_crisis or turn % every or len(words(text)) < turns["mots_minimum_revelation"]:
            return ReplyPlan(**generation)

        formulas = turns["formules_revelation"]
        return ReplyPlan(
            **generation,
            reveal_from=tuple(youth_messages[-REVEAL_SOURCE_MESSAGES:]),
            reveal_formula=formulas[(turn // every - 1) % len(formulas)],
            companion_text=" ".join(name_key(reply) for reply in said),
        )

    def _story_quote(self, earlier: list[dict], exclude: list[str]) -> str | None:
        """Un passage court et sans risque de ce que le jeune a déjà raconté."""
        for message in reversed(earlier):
            story = message["content"].strip().rstrip(".!")
            usable = (
                MIN_STORY_WORDS <= len(words(story))
                and len(story) <= MAX_ENCOURAGING_QUOTE_CHARS
                and not is_shielded(message)
                and not self.guardrails.is_sensitive(story)
                and not matches_any(story, exclude)
                and self.guardrails.review_skill(story, "", "") is not None
            )
            if usable:
                return story
        return None

    def _encouragement(
        self, earlier: list[dict], said: list[str], turn: int, settings: dict
    ) -> str:
        """Répond au doute en s'appuyant, si possible, sur ce que le jeune a déjà raconté."""
        texts = settings["encouragement"]
        story = self._story_quote(earlier, texts["declencheurs"])
        if story:
            options = [option.format(citation=story) for option in texts["avec_citation"]]
            return _fresh_reply(options, said, turn)
        return _fresh_reply(texts["sans_citation"], said, turn)

    def _off_limits_reply(
        self, earlier: list[dict], said: list[str], turn: int, explain: bool = False
    ) -> str:
        """« Je ne peux pas parler de ce sujet », puis une autre piste, si possible la sienne."""
        texts = self.guardrails.off_limits
        story = self._story_quote(earlier, self.prompts.conversation["encouragement"]["declencheurs"])
        if story:
            options = [option.format(citation=story) for option in texts["avec_citation"]]
        else:
            options = texts["propositions"]
        opening = texts["explication"] if explain else texts["refus"]
        return _fresh_reply([f"{opening} {option}" for option in options], said, turn)

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
        """Fait écrire le modèle librement, puis relit sa réponse avant de la montrer."""
        messages = list(plan.messages or [])
        for attempt, temperature in enumerate(REPLY_TEMPERATURES):
            reply = _clean_reply(self.llm.complete(messages, {"temperature": temperature}))
            problem = self._reply_problem(reply, plan, strict=attempt == 0)
            if problem is None:
                return reply
            logger.info("Réponse du compagnon écartée : %s", problem)
            messages = [
                {
                    "role": "system",
                    "content": f"{plan.messages[0]['content']}\n\nTa réponse précédente a été refusée : {problem}",
                },
                *plan.messages[1:],
            ]
        return _fresh_reply(plan.fallback_replies, list(plan.previous_replies), plan.turn)

    def _reply_problem(self, reply: str, plan: ReplyPlan, strict: bool = False) -> str | None:
        if not reply:
            return "elle était vide."
        if strict and plan.no_question and "?" in reply:
            # Règle souple : au deuxième essai, une question vaut mieux qu'une réponse toute faite.
            return "cette fois, pas de question. Réagis ou invite-la à raconter, sans point d'interrogation."
        if len(words(reply)) > MAX_FREE_REPLY_WORDS:
            return "elle était trop longue. Écris 1 à 3 phrases courtes."
        if reply.count("?") > 1:
            return "elle posait plusieurs questions. Une seule au maximum."
        if _reads_badly(reply):
            return "elle était mal formulée. Parle directement à la personne, en tutoyant, en français correct."
        if _GREETING_START.match(reply):
            return "elle commençait par une salutation. La discussion a déjà commencé."
        if _TALENT_WORDS.search(reply):
            return "elle parlait de talents ou de compétences. Contente-toi de discuter."
        if self.guardrails.review_skill(reply, "", "") is None:
            return "elle parlait de santé, d'origine, de religion ou des proches de la personne."
        if matches_any(reply, list(plan.forbidden_phrases)):
            return "elle n'était pas encourageante."
        if _is_repetition(reply, plan.previous_replies):
            return "elle répétait une réponse déjà donnée. Dis quelque chose de nouveau."
        return None

    def _turn_instruction(self, transcript: dict, turns: dict, turn: int) -> tuple[str, bool]:
        """Varie la forme des réponses pour éviter l'effet interrogatoire."""
        replies = [m["content"] for m in transcript["messages"] if m["role"] == "assistant"]
        youth = [m for m in transcript["messages"] if m["role"] == "user"]
        last_words = len(words(youth[-1]["content"]))
        moves = turns["mouvements"]
        # Une question sur deux au plus quand le jeune raconte : le reste du temps, Truffe
        # réagit ou l'invite à raconter, comme dans une vraie discussion.
        asked = sum("?" in reply for reply in replies[-2:])
        if last_words < BRIEF_MESSAGE_WORDS and turn >= 3:
            pistes = turns["pistes"]
            move = moves["nouvelle_piste"].format(piste=pistes[turn % len(pistes)])
        elif last_words < BRIEF_MESSAGE_WORDS:
            move = moves["reponse_courte"]
        elif asked >= 2 or (asked == 1 and turn % 2 == 0):
            move = moves["impression"] if turn % 4 < 2 else moves["recit"]
            return turns["consigne"].format(mouvement=move), True
        else:
            angles = turns["angles"]
            move = moves["question"].format(angle=angles[turn % len(angles)])
        return turns["consigne"].format(mouvement=move), False

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

    def _llm_messages(self, transcript: dict, settings: dict, instruction: str) -> list[dict]:
        limit = current_app.config["CHAT_HISTORY_MESSAGES"]
        recent = transcript["messages"][-limit:]
        # Les formats de discussion des modèles attendent un échange qui commence par la personne.
        while recent and recent[0]["role"] == "assistant":
            recent = recent[1:]

        parts = [self.prompts.companion]
        family = self.guardrails.family_instruction(recent[-1]["content"])
        if family:
            parts.append(family)
        parts.append(instruction)
        parts.append(settings["fin_de_consigne"])

        # Une phrase déjà répétée dans l'historique pousserait le modèle à continuer.
        history = []
        seen: set[str] = set()
        for message in recent:
            key = " ".join(words(message["content"]))
            if message["role"] == "assistant" and key in seen:
                continue
            seen.add(key)
            hidden = message["role"] == "user" and any(
                flag in message.get("flags", []) for flag in (FLAG_VICTIM, FLAG_OFF_LIMITS)
            )
            content = HIDDEN_FROM_MODEL if hidden else message["content"]
            history.append({"role": message["role"], "content": content})
        return [{"role": "system", "content": "\n\n".join(parts)}, *history]

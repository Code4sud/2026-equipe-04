"""Repérage des compétences dans le récit du jeune, en arrière-plan, après chaque message.

Le repérage lui-même (indices, référentiel ROME/ESCO, embeddings, vérification) est dans
talent_detector.py. Ici : choix des messages à lire, doublons et enregistrement. Une
compétence n'est enregistrée que si sa citation existe vraiment dans les messages du jeune et
si elle respecte les garde-fous. Truffe l'épingle directement ; le jeune peut la retirer.
"""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Flask
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from ..errors import LLMError, StorageError
from ..extensions import db
from ..models import EXTRACTION_LEASE, Conversation, Skill, SkillAction, SkillStatus, utcnow
from .chat import is_shielded
from .guardrails import name_key
from .referentiel import CATEGORIES
from .talent_detector import Finding, TalentDetector

logger = logging.getLogger(__name__)

MAX_SKILLS_PER_RUN = 4
MAX_MESSAGES_PER_RUN = 12
MIN_MESSAGE_CHARS = 12
MAX_RETRIES = 3
RETRY_DELAY = 5
MAX_CONTEXT_CHARS = 220


class ExtractionService:
    def __init__(self, app: Flask, llm, store, prompts, guardrails, detector: TalentDetector):
        self.app = app
        self.llm = llm
        self.store = store
        self.prompts = prompts
        self.guardrails = guardrails
        self.detector = detector
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extraction")
        self._failures: dict[uuid.UUID, int] = {}

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
            if processed is None:
                # Ollama a échoué : on réessaie un peu plus tard plutôt que d'attendre le
                # prochain message du jeune, pour qu'aucun récit ne reste sans analyse.
                attempt = self._failures.get(conversation_id, 0) + 1
                self._failures[conversation_id] = attempt
                if attempt <= MAX_RETRIES and not self.app.config["EXTRACTION_SYNC"]:
                    timer = threading.Timer(RETRY_DELAY * attempt, self._retry, [conversation_id])
                    timer.daemon = True
                    timer.start()
                return
            self._failures.pop(conversation_id, None)
            # Le jeune a pu écrire pendant l'analyse : on lit tout de suite la suite, sinon
            # ces messages attendraient le prochain message ou l'ouverture de l'écran.
            conversation = db.session.get(Conversation, conversation_id)
            if conversation is not None and conversation.unprocessed_messages > 0:
                self.schedule(conversation)

    def _retry(self, conversation_id: uuid.UUID) -> None:
        with self.app.app_context():
            conversation = db.session.get(Conversation, conversation_id)
            if conversation is not None:
                self.schedule(conversation)
            db.session.remove()

    def _extract(self, conversation_id: uuid.UUID) -> int:
        conversation = db.session.get(Conversation, conversation_id)
        transcript = self.store.load(conversation.transcript_key)
        all_messages = transcript["messages"]
        start = conversation.extracted_message_count
        candidates = []
        for position, message in enumerate(all_messages[start:], start=start):
            if (
                message["role"] != "user"
                # Détresse, violences confiées, sujets interdits : jamais lus pour les talents.
                or is_shielded(message)
                or len(message["content"]) < MIN_MESSAGE_CHARS
                # Santé, origine, religion : Truffe a répondu hors sujet, rien à en tirer.
                or self.guardrails.is_sensitive(message["content"])
            ):
                continue
            candidates.append({**message, "context": self._question_before(all_messages, position)})
        candidates = candidates[-MAX_MESSAGES_PER_RUN:]
        if not candidates:
            return len(all_messages)

        existing = db.session.execute(
            select(Skill.name, Skill.name_key, Skill.source_quote, Skill.category).where(
                Skill.youth_id == conversation.youth_id
            )
        ).all()
        known_keys = {row.name_key for row in existing}
        # Une même phrase peut montrer deux talents de domaines différents
        # (« j'ai aidé à réparer la voiture » : mécanique et entraide), pas deux fois le même.
        known_quotes = {(name_key(row.source_quote), row.category) for row in existing}

        findings = self.detector.detect(candidates, [row.name for row in existing])
        accepted = 0
        for finding in findings:
            if accepted >= MAX_SKILLS_PER_RUN:
                break
            skill = self._build_skill(conversation, finding)
            quote_key = (name_key(skill.source_quote), skill.category)
            if skill.name_key in known_keys or quote_key in known_quotes:
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

    @staticmethod
    def _question_before(messages: list[dict], position: int) -> str:
        """Ce que Truffe venait de dire : « tous les samedis » n'a de sens qu'avec la question."""
        for message in reversed(messages[:position]):
            if message["role"] == "assistant":
                return message["content"][:MAX_CONTEXT_CHARS]
            if message["role"] == "user":
                return ""
        return ""

    @staticmethod
    def _build_skill(conversation, finding: Finding) -> Skill:
        return Skill(
            youth_id=conversation.youth_id,
            conversation_id=conversation.id,
            source_message_id=finding.message_id,
            name=finding.name[:80],
            name_key=name_key(finding.name),
            category=finding.category if finding.category in CATEGORIES else "savoir_faire",
            description=finding.description[:300],
            source_quote=finding.quote,
            # Néo épingle directement ce qu'il trouve : le jeune peut le retirer ensuite.
            status=SkillStatus.VALIDATED,
        )

    def save_revealed(self, conversation: Conversation, talent) -> Skill | None:
        """Enregistre le talent que Néo vient d'annoncer dans la discussion."""
        key = name_key(talent.name)
        exists = db.session.scalar(
            select(Skill.id).where(Skill.youth_id == conversation.youth_id, Skill.name_key == key)
        )
        if exists or not key:
            return None
        skill = Skill(
            youth_id=conversation.youth_id,
            conversation_id=conversation.id,
            source_message_id=talent.message_id,
            name=talent.name[:80],
            name_key=key,
            category=self._revealed_category(talent),
            description="",
            source_quote=talent.quote,
            status=SkillStatus.VALIDATED,
        )
        try:
            with db.session.begin_nested():
                skill.record(SkillAction.PROPOSED)
                db.session.add(skill)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None
        return skill

    def _revealed_category(self, talent) -> str:
        """Catégorie donnée par la révélation, sinon celle du référentiel le plus proche."""
        if getattr(talent, "category", "") in CATEGORIES:
            return talent.category
        referentiel = self.detector.referentiel
        entry = referentiel.by_name(talent.name)
        if entry is None:
            hits = referentiel.lexical(f"{talent.name} {talent.quote}")
            entry = hits[0][0] if hits else None
        return entry.category if entry else "apprentissage"

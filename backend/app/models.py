"""Modèle de données.

Postgres garde les comptes, les métadonnées de conversation et les compétences.
Le texte des conversations vit uniquement dans le stockage S3 (voir services/transcripts.py).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db

EXTRACTION_LEASE = timedelta(minutes=5)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite perd le fuseau : une date sans fuseau est toujours de l'UTC ici."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


def _enum(enum_class: type[enum.Enum]) -> Enum:
    return Enum(
        enum_class,
        native_enum=False,
        length=20,
        create_constraint=True,
        name=enum_class.__name__.lower(),
        values_callable=lambda members: [member.value for member in members],
    )


class Role(str, enum.Enum):
    YOUTH = "youth"
    PSYCHOLOGIST = "psychologist"
    ADMIN = "admin"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class SkillStatus(str, enum.Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


class SkillOrigin(str, enum.Enum):
    AI = "ai"
    YOUTH = "youth"


class SkillAction(str, enum.Enum):
    PROPOSED = "proposed"
    ADDED = "added"
    VALIDATED = "validated"
    REJECTED = "rejected"
    RENAMED = "renamed"


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[Role] = mapped_column(_enum(Role), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    youth_profile: Mapped["YouthProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value,
        }


class YouthProfile(db.Model):
    __tablename__ = "youth_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Accord donné à l'inscription : discussions et talents vont au Centre des Possibles.
    share_transcripts: Mapped[bool] = mapped_column(Boolean, default=False)
    share_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="youth_profile")


class Conversation(db.Model):
    __tablename__ = "conversations"
    __table_args__ = (
        Index(
            "uq_conversations_one_active_per_youth",
            "youth_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ConversationStatus] = mapped_column(
        _enum(ConversationStatus), default=ConversationStatus.ACTIVE
    )
    transcript_key: Mapped[str] = mapped_column(String(255), unique=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Nombre de messages déjà analysés pour y repérer des compétences.
    extracted_message_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_extracting(self) -> bool:
        started = as_utc(self.extraction_started_at)
        return started is not None and utcnow() - started < EXTRACTION_LEASE

    @property
    def unprocessed_messages(self) -> int:
        return max(0, self.message_count - self.extracted_message_count)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "status": self.status.value,
            "message_count": self.message_count,
            "started_at": iso(self.started_at),
            "last_message_at": iso(self.last_message_at),
            "closed_at": iso(self.closed_at),
        }


class Skill(db.Model):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("youth_id", "name_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Vides pour un talent ajouté par le jeune lui-même.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    source_message_id: Mapped[str | None] = mapped_column(String(36))
    origin: Mapped[SkillOrigin] = mapped_column(_enum(SkillOrigin), default=SkillOrigin.AI)
    name: Mapped[str] = mapped_column(String(80))
    # Forme normalisée du nom : évite de reproposer une compétence déjà vue ou refusée.
    name_key: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    # Extrait mot pour mot d'un message du jeune, vérifié avant enregistrement.
    source_quote: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[SkillStatus] = mapped_column(_enum(SkillStatus), default=SkillStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["SkillEvent"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", order_by="SkillEvent.created_at"
    )

    def record(self, action: SkillAction, previous_name: str | None = None) -> None:
        """Garde la trace d'un changement, pour que la psychologue puisse en parler."""
        by_ai = action == SkillAction.PROPOSED
        self.events.append(
            SkillEvent(
                youth_id=self.youth_id,
                action=action,
                actor=SkillOrigin.AI if by_ai else SkillOrigin.YOUTH,
                previous_name=previous_name,
                name=self.name,
            )
        )

    def to_dict(self, with_history: bool = False) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "quote": self.source_quote,
            "status": self.status.value,
            "origin": self.origin.value,
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "source_message_id": self.source_message_id,
            "created_at": iso(self.created_at),
            "reviewed_at": iso(self.reviewed_at),
        }
        if with_history:
            data["history"] = [event.to_dict() for event in self.events]
        return data


class SkillEvent(db.Model):
    """Historique d'un talent : proposé par Néo, ajouté, gardé, retiré ou renommé par le jeune."""

    __tablename__ = "skill_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), index=True
    )
    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[SkillAction] = mapped_column(_enum(SkillAction))
    actor: Mapped[SkillOrigin] = mapped_column(_enum(SkillOrigin))
    name: Mapped[str] = mapped_column(String(80))
    previous_name: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    skill: Mapped[Skill] = relationship(back_populates="events")

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "actor": self.actor.value,
            "name": self.name,
            "previous_name": self.previous_name,
            "at": iso(self.created_at),
        }


class GameRunStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class GameRun(db.Model):
    """Une partie d'un quiz, d'un questionnaire ou d'un jeu (voir app/game/)."""

    __tablename__ = "game_runs"
    __table_args__ = (
        Index("ix_game_runs_youth_instrument", "youth_id", "instrument_id"),
        Index(
            "uq_game_runs_one_open_per_instrument",
            "youth_id",
            "instrument_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
            sqlite_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    youth_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    instrument_id: Mapped[str] = mapped_column(String(60))
    instrument_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[GameRunStatus] = mapped_column(
        _enum(GameRunStatus), default=GameRunStatus.IN_PROGRESS
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Signaux calculés sur toute la partie (jeux chronométrés).
    signals: Mapped[list] = mapped_column(JSON, default=list)
    # Scores bruts par échelle et mesures du jeu, montrés à la psychologue.
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    answers: Mapped[list["GameAnswer"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="GameAnswer.position"
    )


class GameAnswer(db.Model):
    """Réponse brute, avec le texte tel qu'il a été montré et ce qu'elle a apporté aux curseurs."""

    __tablename__ = "game_answers"
    __table_args__ = (UniqueConstraint("run_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_runs.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text)
    value: Mapped[object | None] = mapped_column(JSON)
    label: Mapped[str | None] = mapped_column(Text)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Type et échelle de la question au moment de la réponse : une nouvelle version du contenu
    # qui les change rend la réponse caduque (voir game/service.py, _reconcile).
    item_type: Mapped[str | None] = mapped_column(String(20))
    item_scale: Mapped[dict | None] = mapped_column(JSON)

    run: Mapped[GameRun] = relationship(back_populates="answers")


class GameFact(db.Model):
    """Détail simple donné par le jeune (couleur préférée, passion...).

    Le jeune peut le corriger ou le masquer de sa fiche ; la psychologue voit toujours
    la réponse d'origine et la modification, pour pouvoir en parler avec lui.
    """

    __tablename__ = "game_facts"

    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(String(160))
    # Réponse donnée dans le jeu, avant toute correction par le jeune.
    original_value: Mapped[str | None] = mapped_column(String(160))
    # Question d'origine : un identifiant de question n'est unique que dans son instrument.
    source_instrument_id: Mapped[str | None] = mapped_column(String(60))
    source_item_id: Mapped[str | None] = mapped_column(String(60))
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Dernière correction de la valeur par le jeune (jamais touchée par le jeu ni par « masquer »).
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TraitFeedback(db.Model):
    """Le jeune dit s'il se reconnaît dans un curseur, tel qu'il était quand il a répondu."""

    __tablename__ = "game_trait_feedback"

    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    trait_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(10))
    # Libellé montré au jeune et valeur du curseur au moment du verdict, calculés par le serveur.
    label_at_verdict: Mapped[str | None] = mapped_column(String(80))
    value_at_verdict: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GameEvent(db.Model):
    """Modification faite par le jeune (détail, verdict, réponse), pour la psychologue seulement.

    `subject` désigne ce qui a changé (« fact:passion », « trait:extraversion »,
    « answer:<partie>/<question> ») ; `before` et `after` gardent l'état avant et après.
    """

    __tablename__ = "game_events"
    __table_args__ = (Index("ix_game_events_youth_created", "youth_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    youth_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(160))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

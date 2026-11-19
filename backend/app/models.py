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
    # Le jeune choisit explicitement de montrer ses conversations à la psychologue.
    share_transcripts: Mapped[bool] = mapped_column(Boolean, default=False)
    share_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Réponses aux jeux et curseurs : None tant que la question n'a pas été posée au jeune.
    share_game_results: Mapped[bool | None] = mapped_column(Boolean)
    share_game_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    source_message_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(80))
    # Forme normalisée du nom : évite de reproposer une compétence déjà vue ou refusée.
    name_key: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    # Extrait mot pour mot d'un message du jeune, vérifié avant enregistrement.
    source_quote: Mapped[str] = mapped_column(Text)
    status: Mapped[SkillStatus] = mapped_column(_enum(SkillStatus), default=SkillStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "quote": self.source_quote,
            "status": self.status.value,
            "conversation_id": str(self.conversation_id),
            "source_message_id": self.source_message_id,
            "created_at": iso(self.created_at),
            "reviewed_at": iso(self.reviewed_at),
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

    run: Mapped[GameRun] = relationship(back_populates="answers")


class GameFact(db.Model):
    """Détail simple donné par le jeune (couleur préférée, passion...), modifiable par lui."""

    __tablename__ = "game_facts"

    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(String(160))
    source_item_id: Mapped[str | None] = mapped_column(String(60))
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TraitFeedback(db.Model):
    """Le jeune dit s'il se reconnaît dans un curseur."""

    __tablename__ = "game_trait_feedback"

    youth_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    trait_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

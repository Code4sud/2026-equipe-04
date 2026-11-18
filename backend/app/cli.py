"""Commandes d'administration : `flask create-user` et `flask seed-demo`."""
from __future__ import annotations

import uuid

import click
from flask import Flask, current_app
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .demo import YOUTHS
from .extensions import db
from .models import Conversation, Role, Skill, SkillStatus, User, YouthProfile, utcnow
from .services import service
from .services.guardrails import find_quote, name_key
from .services.transcripts import new_message, new_transcript, transcript_key


def _create_user(email: str, name: str, password: str, role: Role) -> User:
    user = User(
        email=email.strip().lower(),
        display_name=name,
        password_hash=generate_password_hash(password),
        role=role,
    )
    if role == Role.YOUTH:
        user.youth_profile = YouthProfile()
    db.session.add(user)
    db.session.flush()
    return user


def _exists(email: str) -> bool:
    return db.session.scalar(select(User.id).where(User.email == email.lower())) is not None


def _seed_youth(data: dict, email: str, password: str) -> None:
    user = _create_user(email, data["display_name"], password, Role.YOUTH)
    user.youth_profile.share_transcripts = data["share_transcripts"]
    if data["share_transcripts"]:
        user.youth_profile.share_updated_at = utcnow()

    conversation_id = uuid.uuid4()
    key = transcript_key(user.id, conversation_id)
    transcript = new_transcript(user.id, conversation_id)
    transcript["messages"].append(new_message("assistant", service("prompts").greeting))
    transcript["messages"].extend(new_message(role, text) for role, text in data["messages"])
    count = len(transcript["messages"])
    service("transcripts").save(key, transcript)

    db.session.add(
        Conversation(
            id=conversation_id,
            youth_id=user.id,
            transcript_key=key,
            message_count=count,
            extracted_message_count=count,
        )
    )
    db.session.flush()

    youth_messages = [m for m in transcript["messages"] if m["role"] == "user"]
    for skill in data["skills"]:
        match = find_quote(skill["quote"], youth_messages)
        if match is None:
            raise click.ClickException(f"Citation de démonstration introuvable : {skill['quote']}")
        status = SkillStatus(skill["status"])
        db.session.add(
            Skill(
                youth_id=user.id,
                conversation_id=conversation_id,
                source_message_id=match.message_id,
                name=skill["name"],
                name_key=name_key(skill["name"]),
                category=skill["category"],
                description=skill["description"],
                source_quote=match.quote,
                status=status,
                reviewed_at=None if status == SkillStatus.PENDING else utcnow(),
            )
        )


def register_cli(app: Flask) -> None:
    @app.cli.command("create-user")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt="Nom affiché")
    @click.option(
        "--role",
        type=click.Choice([role.value for role in Role]),
        default=Role.PSYCHOLOGIST.value,
        show_default=True,
    )
    @click.password_option("--password", prompt="Mot de passe")
    def create_user(email: str, name: str, role: str, password: str) -> None:
        """Crée un compte, notamment psychologue."""
        if _exists(email):
            raise click.ClickException("Un compte existe déjà avec cet e-mail.")
        _create_user(email, name, password, Role(role))
        db.session.commit()
        click.echo(f"Compte {role} créé pour {email.lower()}.")

    @app.cli.command("seed-demo")
    def seed_demo() -> None:
        """Crée les comptes et données fictives de démonstration (sans doublon)."""
        config = current_app.config
        psy_password = config["SEED_PSY_PASSWORD"]
        youth_password = config["SEED_YOUTH_PASSWORD"]
        if not psy_password or not youth_password:
            click.echo("Démo ignorée : SEED_PSY_PASSWORD et SEED_YOUTH_PASSWORD sont vides.")
            return

        if not _exists(config["SEED_PSY_EMAIL"]):
            _create_user(config["SEED_PSY_EMAIL"], "Psychologue démo", psy_password, Role.PSYCHOLOGIST)
        for data in YOUTHS:
            email = config[data["email_setting"]] if "email_setting" in data else data["email"]
            if not _exists(email):
                _seed_youth(data, email, youth_password)
        db.session.commit()
        click.echo("Données de démonstration prêtes.")

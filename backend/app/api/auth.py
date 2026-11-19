from __future__ import annotations

import re

from flask import g, jsonify
from flask_jwt_extended import create_access_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import ApiError
from ..extensions import db
from ..models import Role, User, YouthProfile, utcnow
from ..security import require_roles
from . import api
from .helpers import json_body, text_field

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Empêche de deviner quels e-mails existent en comparant les temps de réponse.
_DUMMY_HASH = generate_password_hash("compte-inexistant")


def _session_payload(user: User) -> dict:
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.value})
    return {"access_token": token, "user": user.to_dict()}


def _email(data: dict) -> str:
    email = text_field(data, "email", "L'e-mail", 3, 254).lower()
    if not EMAIL_PATTERN.match(email):
        raise ApiError(400, "invalid_field", "L'e-mail n'est pas valide.")
    return email


@api.post("/auth/register")
def register():
    """Crée un compte jeune. Les comptes psychologues passent par `flask create-user`."""
    data = json_body()
    # Le Centre des Possibles accompagne le jeune : son accord est demandé à l'inscription.
    if data.get("accept_sharing") is not True:
        raise ApiError(
            400,
            "consent_required",
            "Pour continuer, accepte de partager ton parcours avec le Centre des Possibles.",
        )
    user = User(
        email=_email(data),
        display_name=text_field(data, "display_name", "Le prénom ou pseudo", 1, 80),
        password_hash=generate_password_hash(text_field(data, "password", "Le mot de passe", 8, 200)),
        role=Role.YOUTH,
    )
    now = utcnow()
    user.youth_profile = YouthProfile(share_transcripts=True, share_updated_at=now, consent_at=now)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError(409, "email_taken", "Un compte existe déjà avec cet e-mail.") from error
    return jsonify(_session_payload(user)), 201


@api.post("/auth/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = db.session.scalar(select(User).where(User.email == email))
    valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
    if user is None or not valid or not user.is_active:
        raise ApiError(401, "invalid_credentials", "E-mail ou mot de passe incorrect.")
    return jsonify(_session_payload(user))


@api.get("/auth/me")
@require_roles()
def me():
    return jsonify({"user": g.user.to_dict()})

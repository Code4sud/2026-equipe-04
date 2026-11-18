"""Contrôle d'accès par rôle."""
from __future__ import annotations

import uuid
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from .errors import ApiError
from .extensions import db
from .models import Role, User


def require_roles(*roles: Role):
    """Vérifie le jeton, recharge le compte et contrôle son rôle (tous si aucun rôle donné)."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            try:
                user_id = uuid.UUID(get_jwt_identity())
            except (TypeError, ValueError) as error:
                raise ApiError(401, "invalid_token", "Session invalide.") from error
            user = db.session.get(User, user_id)
            if user is None or not user.is_active:
                raise ApiError(401, "invalid_token", "Session invalide.")
            if roles and user.role not in roles:
                raise ApiError(403, "forbidden", "Accès non autorisé.")
            g.user = user
            return view(*args, **kwargs)

        return wrapper

    return decorator

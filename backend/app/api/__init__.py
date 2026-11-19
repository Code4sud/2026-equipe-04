from flask import Blueprint

api = Blueprint("api", __name__, url_prefix="/api")

from . import auth, backoffice, conversations, game, health, skills  # noqa: E402,F401

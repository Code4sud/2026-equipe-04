"""Application factory de l'API."""
from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from .config import check_config, load_config
from .errors import error_response, register_error_handlers
from .extensions import db, jwt, migrate
from .game.catalog import Catalog
from .services.chat import ChatService
from .services.embeddings import OllamaEmbedder, ReferentielIndex
from .services.extraction import ExtractionService
from .services.referentiel import Referentiel
from .services.talent_detector import TalentDetector
from .services.guardrails import Guardrails
from .services.llm import OllamaClient
from .services.prompts import PromptLibrary
from .services.transcripts import S3TranscriptStore


def create_app(config: dict | None = None, services: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(load_config())
    app.config.update(config or {})
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not app.config.get("TESTING"):
        check_config(app.config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    _register_jwt_errors()
    register_error_handlers(app)

    if app.config["CORS_ORIGINS"]:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    _register_services(app, services or {})

    from . import models  # noqa: F401  (modèles visibles par Alembic)
    from .api import api
    from .cli import register_cli

    app.register_blueprint(api)
    register_cli(app)
    return app


def _register_services(app: Flask, overrides: dict) -> None:
    config = app.config
    prompts = PromptLibrary(config["PROMPTS_DIR"])
    guardrails = Guardrails(prompts)
    llm = overrides.get("llm") or OllamaClient(
        config["OLLAMA_URL"], config["OLLAMA_MODEL"], config["OLLAMA_TIMEOUT"]
    )
    transcripts = overrides.get("transcripts") or S3TranscriptStore(
        config["S3_ENDPOINT"],
        config["S3_ACCESS_KEY"],
        config["S3_SECRET_KEY"],
        config["S3_BUCKET"],
        config["S3_REGION"],
    )
    referentiel = Referentiel(prompts)
    # Un faux modèle de test sans faux embeddings : pas d'appel réseau, repérage sans rapprochement.
    if "embedder" in overrides:
        embedder = overrides["embedder"]
    elif "llm" in overrides or not config["OLLAMA_EMBED_MODEL"]:
        embedder = None
    else:
        embedder = OllamaEmbedder(config["OLLAMA_URL"], config["OLLAMA_EMBED_MODEL"], config["OLLAMA_TIMEOUT"])
    index = ReferentielIndex(embedder, referentiel) if embedder else None
    detector = TalentDetector(llm, prompts, guardrails, referentiel, index)
    app.extensions.update(
        prompts=prompts,
        guardrails=guardrails,
        llm=llm,
        transcripts=transcripts,
        chat=ChatService(llm, transcripts, prompts, guardrails),
        referentiel=referentiel,
        extraction=ExtractionService(app, llm, transcripts, prompts, guardrails, detector),
        game_catalog=overrides.get("game_catalog") or Catalog(),
    )


def _register_jwt_errors() -> None:
    @jwt.unauthorized_loader
    def missing_token(_reason):
        return error_response(401, "auth_required", "Connexion requise.")

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return error_response(401, "invalid_token", "Session invalide, reconnecte-toi.")

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return error_response(401, "token_expired", "Session expirée, reconnecte-toi.")

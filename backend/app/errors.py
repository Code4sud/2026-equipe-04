"""Erreurs de l'API, toujours renvoyées sous la forme {"error": {code, message}}."""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class StorageError(Exception):
    """Le stockage S3 des conversations est indisponible ou a refusé l'opération."""


class LLMError(Exception):
    """Ollama est injoignable, ou le modèle n'a pas pu répondre."""


def error_response(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_response(error.status, error.code, error.message)

    @app.errorhandler(StorageError)
    def handle_storage_error(error: StorageError):
        logger.error("Stockage indisponible : %s", error)
        return error_response(
            503, "storage_unavailable", "Le stockage des conversations est indisponible."
        )

    @app.errorhandler(LLMError)
    def handle_llm_error(error: LLMError):
        logger.error("Modèle indisponible : %s", error)
        return error_response(503, "llm_unavailable", "Le compagnon est indisponible.")

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        return error_response(error.code or 500, "http_error", error.description or error.name)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        logger.exception("Erreur inattendue", exc_info=error)
        return error_response(500, "internal_error", "Une erreur inattendue est survenue.")

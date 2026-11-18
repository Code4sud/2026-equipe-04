from __future__ import annotations

from flask import jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..services import service
from . import api


def _database_ok() -> bool:
    try:
        db.session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        db.session.rollback()
        return False


@api.get("/health")
def health():
    """Vérification légère, utilisée par le healthcheck Docker."""
    healthy = _database_ok()
    return jsonify({"status": "ok" if healthy else "unavailable"}), 200 if healthy else 503


@api.get("/health/services")
def services_health():
    """État détaillé des dépendances, pour diagnostiquer un démarrage."""
    llm = service("llm").status()
    checks = {
        "database": _database_ok(),
        "storage": service("transcripts").ping(),
        "llm": llm,
    }
    ready = checks["database"] and checks["storage"] and llm["model_ready"]
    return jsonify({"status": "ok" if ready else "degraded", "services": checks})

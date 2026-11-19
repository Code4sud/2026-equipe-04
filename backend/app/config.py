"""Configuration lue dans l'environnement (voir .env.example à la racine)."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Utile hors Docker uniquement : les variables déjà définies restent prioritaires.
load_dotenv(BACKEND_DIR / ".env")

REQUIRED_SETTINGS = (
    "DATABASE_URL",
    "S3_ENDPOINT",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "JWT_SECRET_KEY",
)


def normalize_database_url(url: str) -> str:
    """Force le pilote psycopg 3, quelle que soit la forme de l'URL reçue."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


def load_config() -> dict:
    database_url = normalize_database_url(os.environ.get("DATABASE_URL", ""))
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    return {
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": database_url or "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        "S3_ENDPOINT": os.environ.get("S3_ENDPOINT", ""),
        "S3_ACCESS_KEY": os.environ.get("S3_ACCESS_KEY", ""),
        "S3_SECRET_KEY": os.environ.get("S3_SECRET_KEY", ""),
        "S3_BUCKET": os.environ.get("S3_BUCKET", "conversations"),
        "S3_REGION": os.environ.get("S3_REGION", "us-east-1"),
        "OLLAMA_URL": os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "mistral-nemo"),
        "OLLAMA_TIMEOUT": _int("OLLAMA_TIMEOUT", 300),
        # Embeddings multilingues pour rapprocher le récit du référentiel ROME/ESCO ; vide = désactivé.
        "OLLAMA_EMBED_MODEL": os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3"),
        "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY", ""),
        "JWT_ACCESS_TOKEN_EXPIRES": timedelta(hours=_int("JWT_EXPIRES_HOURS", 12)),
        "JWT_TOKEN_LOCATION": ["headers"],
        "CORS_ORIGINS": origins,
        "PROMPTS_DIR": os.environ.get("PROMPTS_DIR", str(BACKEND_DIR / "prompts")),
        "CHAT_HISTORY_MESSAGES": _int("CHAT_HISTORY_MESSAGES", 12),
        "MAX_MESSAGE_CHARS": _int("MAX_MESSAGE_CHARS", 4000),
        # Rythme d'affichage des réponses déjà écrites, en secondes par mot.
        "PREPARED_REPLY_WORD_DELAY": 0.025,
        # Nombre de nouveaux messages (jeune + compagnon) avant une analyse automatique :
        # 2 = après chaque message du jeune et la réponse de Néo.
        "EXTRACTION_EVERY_MESSAGES": _int("EXTRACTION_EVERY_MESSAGES", 2),
        "EXTRACTION_SYNC": False,
        "SEED_PSY_EMAIL": os.environ.get("SEED_PSY_EMAIL", "psy@example.org"),
        "SEED_PSY_PASSWORD": os.environ.get("SEED_PSY_PASSWORD", ""),
        "SEED_YOUTH_EMAIL": os.environ.get("SEED_YOUTH_EMAIL", "sam@example.org"),
        "SEED_YOUTH_PASSWORD": os.environ.get("SEED_YOUTH_PASSWORD", ""),
    }


def check_config(config: dict) -> None:
    """Refuse de démarrer sans configuration complète ni vrai secret JWT."""
    missing = [name for name in REQUIRED_SETTINGS if not config.get(name)]
    if missing:
        raise RuntimeError(
            "Variables d'environnement manquantes : " + ", ".join(missing)
            + ". Lancez ./run.sh pour créer la configuration."
        )
    secret = config["JWT_SECRET_KEY"]
    if secret.startswith("change-me") or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY doit être un secret d'au moins 32 caractères "
            "(par exemple : openssl rand -hex 32)."
        )

"""API de développement autonome pour travailler sur le jeu, sans Docker ni Ollama.

    python scripts/dev_game.py 5101

Base SQLite recréée à chaque lancement. Comptes (mot de passe « motdepasse ») :
- psy@example.org : psychologue
- sam@example.org : jeune avec toutes les parties jouées et partagées
- noa@example.org : jeune qui a tout joué sans partager
- lea@example.org : nouveau jeune, qui arrive sur le quiz
Le contenu réel est complété par les contenus fictifs de tests/fixtures/game.
"""
from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402
from app.cli import _create_user  # noqa: E402
from app.extensions import db  # noqa: E402
from app.game.catalog import Catalog  # noqa: E402
from app.models import Role  # noqa: E402

PASSWORD = "motdepasse"


class MemoryStore:
    def __init__(self):
        self.objects: dict[str, dict] = {}

    def load(self, key):
        return copy.deepcopy(self.objects[key])

    def save(self, key, transcript):
        self.objects[key] = copy.deepcopy(transcript)

    def ping(self):
        return True


class SilentLLM:
    def chat_stream(self, _messages):
        yield "Mode développement : pas de modèle branché."

    def generate_json(self, *_args, **_kwargs):
        return {"competences": []}

    def status(self):
        return {"reachable": True, "model": "dev", "model_ready": True}


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5101
    database = Path(tempfile.gettempdir()) / f"equipe04-game-dev-{port}.db"
    database.unlink(missing_ok=True)
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
            "SQLALCHEMY_ENGINE_OPTIONS": {},
            "JWT_SECRET_KEY": "cle-de-developpement-suffisamment-longue-0123456789",
            "EXTRACTION_SYNC": True,
            "SEED_PSY_PASSWORD": PASSWORD,
            "SEED_YOUTH_PASSWORD": PASSWORD,
            "SEED_PSY_EMAIL": "psy@example.org",
            "SEED_YOUTH_EMAIL": "sam@example.org",
        },
        {
            "llm": SilentLLM(),
            "transcripts": MemoryStore(),
            "game_catalog": Catalog(overlays=[BACKEND / "tests/fixtures/game"], overlays_win=False),
        },
    )
    with app.app_context():
        db.create_all()
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    if result.exit_code != 0:
        raise SystemExit(result.output or str(result.exception))
    with app.app_context():
        _create_user("lea@example.org", "Léa", PASSWORD, Role.YOUTH)
        db.session.commit()
    print(f"API de développement sur http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()

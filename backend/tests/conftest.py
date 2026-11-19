from __future__ import annotations

import copy
import json
import os

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.errors import LLMError, StorageError
from app.extensions import db
from app.models import Role, User, YouthProfile


class FakeStore:
    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.fail = False

    def load(self, key):
        if self.fail or key not in self.objects:
            raise StorageError(key)
        return copy.deepcopy(self.objects[key])

    def save(self, key, transcript):
        if self.fail:
            raise StorageError(key)
        self.objects[key] = copy.deepcopy(transcript)

    def ping(self):
        return not self.fail


VARIED_REPLIES = (
    "Des roues voilées, sacré boulot ! Qui t'a montré ça ?",
    "Les freins demandent du soin. Tu commences par quoi ?",
    "Tes copains comptent sur toi ? Raconte une fois précise.",
    "Pas facile au début, non ? Qu'est-ce qui coinçait ?",
    "Sympa cette chaîne propre. Combien de temps ça te prend ?",
    "Et les pneus crevés, tu gères aussi ? Montre-moi comment.",
)


class FakeLLM:
    def __init__(self):
        self.tokens = ["Bien ", "joué !"]
        self.varied = list(VARIED_REPLIES)
        self.fail = False
        self.chat_calls: list[list[dict]] = []
        self.proposals: list[dict] = []
        self.json_calls: list[tuple[str, str]] = []
        self.reveal = {"citation": "", "savoir_faire": ""}
        self.reveal_calls: list[str] = []
        self.questions: list[dict] = []
        self.question_calls: list[str] = []

    def chat_stream(self, messages):
        self.chat_calls.append(messages)
        if self.fail:
            raise LLMError("indisponible")
        if len(self.chat_calls) > 1 and self.tokens == ["Bien ", "joué !"]:
            yield self.varied[(len(self.chat_calls) - 2) % len(self.varied)]
            return
        yield from self.tokens

    def generate_json(self, system, user, schema, temperature=None, examples=None):
        if self.fail:
            raise LLMError("indisponible")
        if "question" in schema["properties"]:
            self.question_calls.append(user)
            return self.questions.pop(0) if self.questions else {}
        if "savoir_faire" in schema["properties"]:
            self.reveal_calls.append(user)
            return self.reveal
        self.json_calls.append((system, user))
        return {"competences": self.proposals}

    def status(self):
        return {"reachable": True, "model": "fake", "model_ready": True}


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def app(tmp_path, llm, store):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": url,
            "JWT_SECRET_KEY": "cle-de-test-suffisamment-longue-0123456789",
            "EXTRACTION_SYNC": True,
            "EXTRACTION_EVERY_MESSAGES": 4,
            "PREPARED_REPLY_WORD_DELAY": 0,
        },
        {"llm": llm, "transcripts": store},
    )
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, name="Léa", email=None) -> dict:
    email = email or f"{name.lower().replace('é', 'e')}@example.org"
    response = client.post(
        "/api/auth/register",
        json={"display_name": name, "email": email, "password": "motdepasse", "accept_sharing": True},
    )
    assert response.status_code == 201, response.get_json()
    return auth(response.get_json()["access_token"])


@pytest.fixture
def youth(client):
    return register(client)


@pytest.fixture
def psychologist(app, client):
    with app.app_context():
        db.session.add(
            User(
                email="psy@example.org",
                display_name="Psy",
                password_hash=generate_password_hash("motdepasse"),
                role=Role.PSYCHOLOGIST,
            )
        )
        db.session.commit()
    response = client.post(
        "/api/auth/login", json={"email": "psy@example.org", "password": "motdepasse"}
    )
    return auth(response.get_json()["access_token"])


def parse_sse(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.get_data(as_text=True).strip().split("\n\n"):
        lines = block.split("\n")
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return events


def send(client, headers, conversation_id, content) -> list[tuple[str, dict]]:
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": content},
        headers=headers,
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return parse_sse(response)


__all__ = ["YouthProfile", "auth", "parse_sse", "register", "send"]

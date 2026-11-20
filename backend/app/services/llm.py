"""Client Ollama : réponses du compagnon, JSON structuré pour l'analyse et le garde-fou.

Le compagnon passe toujours avant le lecteur de talents : quand Ollama ne sert qu'une
requête à la fois (OLLAMA_NUM_PARALLEL=1, réglage par défaut), une analyse en cours
s'interrompt dès qu'une réponse au jeune est demandée, puis reprend après elle (voir
ChatPriority). La discussion n'attend donc jamais le lecteur.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import requests

from ..errors import LLMError

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 5
# La démo peut rester sans message un moment : recharger le modèle coûterait 3 à 5 s.
KEEP_ALIVE = "2h"
CHAT_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_ctx": 6144,
    "num_predict": 160,
    # Une réponse tient en un paragraphe : on coupe si le modèle invente la suite du dialogue.
    "stop": ["\n\n", "[INST]", "\nTu :", "\nPersonne :", "\nJeune :", "\nToi :", "\nMoi :", "\nTruffe :"],
}
JSON_OPTIONS = {"temperature": 0.1, "num_ctx": 6144, "num_predict": 800}
# Temps maximal pendant lequel le lecteur attend la fin d'une réponse au jeune.
READER_MAX_WAIT = 120
READER_POLL = 0.15
MAX_PREEMPTIONS = 2


class Preempted(LLMError):
    """Une réponse au jeune a été demandée : l'analyse en cours s'arrête pour la laisser passer."""


class ChatPriority:
    """Priorité du compagnon sur le lecteur, partagée entre les processus de gunicorn.

    Une réponse au jeune garde un verrou partagé sur un fichier pendant qu'elle est écrite. Le
    lecteur ne démarre une requête que si personne ne le tient, et coupe sa requête en cours
    (Ollama arrête alors de générer) dès qu'une réponse le prend. Un verrou exclusif en attente
    ne bloque jamais un nouveau verrou partagé : le compagnon n'attend jamais le lecteur.
    """

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(tempfile.gettempdir(), "flair-ollama-priorite.lock")
        self._local = threading.local()

    def _fd(self) -> int:
        fd = getattr(self._local, "fd", None)
        if fd is None:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            self._local.fd = fd
        return fd

    @contextmanager
    def chat(self):
        # Un descripteur par appel : flock est attaché au descripteur, et plusieurs réponses
        # peuvent s'écrire en même temps dans des fils différents.
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def chat_active(self) -> bool:
        fd = self._fd()
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False

    def wait_for_chat(self, timeout: float = READER_MAX_WAIT) -> None:
        deadline = time.monotonic() + timeout
        while self.chat_active():
            if time.monotonic() > deadline:
                raise LLMError("Le compagnon occupe le modèle depuis trop longtemps")
            time.sleep(READER_POLL)


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 300,
        think: bool | None = False,
        priority: ChatPriority | None = None,
        yields_to_chat: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Les modèles qui réfléchissent avant de répondre (Gemma 4, Qwen 3.5) le font par
        # défaut : False coupe cette réflexion, None laisse le réglage du modèle.
        self.think = think
        self.priority = priority
        self.yields_to_chat = yields_to_chat

    def reader(self, model: str | None = None, think: bool | None = None) -> "OllamaClient":
        """Client du lecteur de talents : même serveur, il cède la place au compagnon."""
        return OllamaClient(
            self.base_url,
            model or self.model,
            self.timeout,
            self.think if think is None else think,
            self.priority,
            yields_to_chat=self.priority is not None,
        )

    # -- compagnon ------------------------------------------------------------------------
    def chat_stream(self, messages: list[dict], options: dict | None = None) -> Iterator[str]:
        payload = self._payload(messages, {**CHAT_OPTIONS, **(options or {})}, stream=True)
        with self._chat_turn():
            yield from self._stream(payload)

    def complete(self, messages: list[dict], options: dict | None = None) -> str:
        """Réponse entière du compagnon, relue avant d'être montrée au jeune."""
        return "".join(self.chat_stream(messages, options))

    # -- analyse --------------------------------------------------------------------------
    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict,
        temperature: float | None = None,
        examples: list[dict] | None = None,
        options: dict | None = None,
    ) -> dict:
        messages = [
            {"role": "system", "content": system},
            *(examples or []),
            {"role": "user", "content": user},
        ]
        merged = {**JSON_OPTIONS, **(options or {})}
        if temperature is not None:
            merged["temperature"] = temperature
        payload = self._payload(messages, merged, stream=True)
        payload["format"] = schema
        if not self.yields_to_chat:
            with self._chat_turn():
                return self._parse("".join(self._stream(payload)))
        # Le lecteur cède la place au plus deux fois par requête, puis la termine : un jeune qui
        # écrit sans s'arrêter ne doit jamais empêcher ses talents d'être trouvés.
        for _ in range(MAX_PREEMPTIONS):
            self.priority.wait_for_chat()
            try:
                return self._parse("".join(self._stream(payload, preemptible=True)))
            except Preempted:
                logger.info("Analyse interrompue pour laisser répondre le compagnon")
        self.priority.wait_for_chat()
        return self._parse("".join(self._stream(payload)))

    def status(self) -> dict:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=(2, 3))
            response.raise_for_status()
            names = [model.get("name", "") for model in response.json().get("models", [])]
        except (requests.RequestException, ValueError):
            return {"reachable": False, "model": self.model, "model_ready": False}
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return {"reachable": True, "model": self.model, "model_ready": wanted in names}

    # -- interne --------------------------------------------------------------------------
    def _payload(self, messages: list[dict], options: dict, stream: bool) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": KEEP_ALIVE,
            "options": options,
        }
        if self.think is not None:
            payload["think"] = self.think
        return payload

    @contextmanager
    def _chat_turn(self):
        if self.priority is None:
            yield
            return
        with self.priority.chat():
            yield

    def _stream(self, payload: dict, preemptible: bool = False) -> Iterator[str]:
        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=(CONNECT_TIMEOUT, self.timeout),
            ) as response:
                self._raise_for_status(response)
                for line in response.iter_lines():
                    # Fermer la connexion suffit : Ollama arrête alors de générer.
                    if preemptible and self.priority.chat_active():
                        raise Preempted("réponse du compagnon prioritaire")
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise LLMError(str(chunk["error"]))
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        return
        except (requests.RequestException, ValueError) as error:
            raise LLMError(str(error)) from error

    @staticmethod
    def _parse(text: str) -> dict:
        try:
            return json.loads(text)
        except ValueError as error:
            raise LLMError(f"JSON illisible : {text[:120]}") from error

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.status_code >= 400:
            raise LLMError(f"Ollama a répondu {response.status_code} : {response.text[:200]}")

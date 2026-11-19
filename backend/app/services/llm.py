"""Client Ollama : réponses en flux pour le chat, JSON structuré pour l'analyse."""
from __future__ import annotations

import json
from collections.abc import Iterator

import requests

from ..errors import LLMError

CONNECT_TIMEOUT = 5
KEEP_ALIVE = "30m"
CHAT_OPTIONS = {
    "temperature": 0.4,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "num_ctx": 4096,
    "num_predict": 160,
    # Une réponse tient en un paragraphe : on coupe si le modèle invente la suite du dialogue.
    "stop": ["\n\n", "[INST]", "\nTu :", "\nPersonne :", "\nJeune :", "\nToi :", "\nMoi :"],
}
JSON_OPTIONS = {"temperature": 0.1, "num_ctx": 4096, "num_predict": 800}


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": KEEP_ALIVE,
            "options": CHAT_OPTIONS,
        }
        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=(CONNECT_TIMEOUT, self.timeout),
            ) as response:
                self._raise_for_status(response)
                for line in response.iter_lines():
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

    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict,
        temperature: float | None = None,
        examples: list[dict] | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *(examples or []),
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "keep_alive": KEEP_ALIVE,
            "options": {**JSON_OPTIONS, **({} if temperature is None else {"temperature": temperature})},
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
            self._raise_for_status(response)
            return json.loads(response.json()["message"]["content"])
        except (requests.RequestException, ValueError, KeyError) as error:
            raise LLMError(str(error)) from error

    def status(self) -> dict:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=(2, 3))
            response.raise_for_status()
            names = [model.get("name", "") for model in response.json().get("models", [])]
        except (requests.RequestException, ValueError):
            return {"reachable": False, "model": self.model, "model_ready": False}
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return {"reachable": True, "model": self.model, "model_ready": wanted in names}

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.status_code >= 400:
            raise LLMError(f"Ollama a répondu {response.status_code} : {response.text[:200]}")

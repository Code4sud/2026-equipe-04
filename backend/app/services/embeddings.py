"""Embeddings locaux via Ollama (bge-m3 par défaut, multilingue) pour rapprocher un récit
du référentiel. Si le modèle manque, le repérage continue avec les indices et le modèle de
langage seuls."""
from __future__ import annotations

import logging
import math
import threading

import requests

from ..errors import LLMError

logger = logging.getLogger(__name__)
CONNECT_TIMEOUT = 5


def cosine(first: list[float], second: list[float]) -> float:
    dot = sum(a * b for a, b in zip(first, second))
    norm = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))
    return dot / norm if norm else 0.0


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts, "keep_alive": "2h"},
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
            if response.status_code >= 400:
                raise LLMError(f"Ollama a répondu {response.status_code} : {response.text[:200]}")
            vectors = response.json()["embeddings"]
        except (requests.RequestException, ValueError, KeyError) as error:
            raise LLMError(str(error)) from error
        if len(vectors) != len(texts):
            raise LLMError("Nombre d'embeddings inattendu")
        return vectors


class ReferentielIndex:
    """Vecteurs du référentiel, calculés une fois par version du fichier."""

    def __init__(self, embedder, referentiel):
        self.embedder = embedder
        self.referentiel = referentiel
        self._version: str | None = None
        self._vectors: list[tuple[str, list[float]]] = []
        self._lock = threading.Lock()

    def _ensure(self) -> list[tuple[str, list[float]]]:
        version = self.referentiel.version
        with self._lock:
            if version != self._version:
                owners, texts = [], []
                for entry in self.referentiel.entries:
                    for text in entry.embedding_texts:
                        owners.append(entry.id)
                        texts.append(text)
                vectors = self.embedder.embed(texts)
                self._vectors = list(zip(owners, vectors))
                self._version = version
            return self._vectors

    def rank(self, vectors: list[list[float]]) -> list[dict[str, float]]:
        """Pour chaque vecteur, la meilleure similarité avec chaque entrée."""
        index = self._ensure()
        ranked = []
        for vector in vectors:
            scores: dict[str, float] = {}
            for entry_id, reference in index:
                score = cosine(vector, reference)
                if score > scores.get(entry_id, -1.0):
                    scores[entry_id] = score
            ranked.append(scores)
        return ranked

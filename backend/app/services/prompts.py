"""Textes éditables du dossier prompts/ : relus dès qu'ils changent, sans redémarrage."""
from __future__ import annotations

import json
import threading
from pathlib import Path


class PromptLibrary:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self._cache: dict[str, tuple[int, str]] = {}
        self._lock = threading.Lock()

    def text(self, filename: str) -> str:
        path = self.directory / filename
        modified = path.stat().st_mtime_ns
        with self._lock:
            cached = self._cache.get(filename)
            if cached and cached[0] == modified:
                return cached[1]
        content = path.read_text(encoding="utf-8").strip()
        with self._lock:
            self._cache[filename] = (modified, content)
        return content

    def json(self, filename: str) -> dict:
        return json.loads(self.text(filename))

    @property
    def companion(self) -> str:
        return self.text("compagnon.md")

    @property
    def conversation(self) -> dict:
        return self.json("conversation.json")

    @property
    def greeting(self) -> str:
        return self.text("accueil.md")

    @property
    def extraction(self) -> str:
        return self.text("extraction.md")

    @property
    def question(self) -> str:
        return self.text("question.md")

    @property
    def question_examples(self) -> list[dict]:
        return self.json("question_exemples.json")

    @property
    def reveal(self) -> str:
        return self.text("revelation.md")

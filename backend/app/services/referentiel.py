"""Référentiel de compétences (sous-ensemble ROME/ESCO) et repérage lexical des indices.

Le fichier prompts/referentiel_competences.json se modifie sans redémarrage. Chaque entrée a
une catégorie du jeu (CATEGORIES), qui alimente l'XP et les curseurs.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from .guardrails import _compile, fold, name_key, words

CATEGORIES = (
    "savoir_faire",
    "organisation",
    "relationnel",
    "communication",
    "resolution_problemes",
    "autonomie",
    "creativite",
    "apprentissage",
)

MIN_CLAUSE_WORDS = 3
# Un récit à la première personne : « j'ai aidé », « je regarde », « on a réparé ».
_ACTOR_WORDS = frozenset({"je", "j", "on", "moi", "me", "m", "nous"})
# Envie, hypothèse ou négation : pas une preuve de ce que la personne a fait.
_NOT_EVIDENCE = re.compile(
    r"\b(?:j aimerais|je voudrais|je veux|j adorerais|je reve|je reverais|si je pouvais|"
    r"je sais pas|je ne sais pas|j ai jamais(?! (?:lache|abandonne|rate|manque))|"
    r"je n ai jamais(?! (?:lache|abandonne|rate|manque))|je fais jamais|je n arrive pas|"
    r"j arrive pas|je deteste)\b"
)
_SENTENCE = re.compile(r"(?<=[.!?…;])\s+|\n+")
_CLAUSE = re.compile(r",\s+|\s+(?:et|mais|puis|alors|du coup|parce que|car)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    category: str
    description: str
    source: str
    examples: tuple[str, ...]
    pattern: re.Pattern | None

    @property
    def embedding_texts(self) -> list[str]:
        return [f"{self.name}. {self.description}", *self.examples]


@dataclass(frozen=True)
class Clause:
    message_id: str
    text: str


def searchable(text: str) -> str:
    return " ".join(words(text))


def clauses(messages: list[dict]) -> list[Clause]:
    """Découpe chaque message en propositions courtes : la citation la plus courte possible."""
    found: list[Clause] = []
    for message in messages:
        for sentence in _SENTENCE.split(message["content"]):
            sentence = sentence.strip()
            if not sentence:
                continue
            parts = [part.strip(" .!?…;") for part in _CLAUSE.split(sentence)]
            short = [part for part in parts if len(words(part)) < MIN_CLAUSE_WORDS]
            if short or len(parts) == 1:
                # Une proposition trop courte perd son sens : on garde la phrase entière.
                found.append(Clause(message["id"], sentence.strip(" .!?…;")))
                parts = [part for part in parts if part not in short] if len(parts) > 1 else []
            found.extend(Clause(message["id"], part) for part in parts)
    seen: set[tuple[str, str]] = set()
    unique = []
    for clause in found:
        key = (clause.message_id, name_key(clause.text))
        if key not in seen and len(words(clause.text)) >= MIN_CLAUSE_WORDS:
            seen.add(key)
            unique.append(clause)
    return unique


def is_evidence(text: str, context: str = "") -> bool:
    """Une action racontée à la première personne, pas une envie ni une négation."""
    plain = searchable(text)
    if _NOT_EVIDENCE.search(plain):
        return False
    return bool(_ACTOR_WORDS & set(plain.split()) or _ACTOR_WORDS & set(searchable(context).split()))


class Referentiel:
    FILENAME = "referentiel_competences.json"

    def __init__(self, prompts):
        self.prompts = prompts
        self._source: str | None = None
        self._entries: tuple[Entry, ...] = ()
        self._lock = threading.Lock()

    @property
    def entries(self) -> tuple[Entry, ...]:
        source = self.prompts.text(self.FILENAME)
        with self._lock:
            if source != self._source:
                data = self.prompts.json(self.FILENAME)
                self._entries = tuple(
                    Entry(
                        id=item["id"],
                        name=item["nom"],
                        category=item["categorie"] if item["categorie"] in CATEGORIES else "savoir_faire",
                        description=item["description"],
                        source=item.get("source", ""),
                        examples=tuple(item.get("exemples", [])),
                        pattern=_compile(item.get("indices", [])),
                    )
                    for item in data["competences"]
                )
                self._source = source
            return self._entries

    @property
    def version(self) -> str:
        self.entries
        return str(hash(self._source))

    def get(self, entry_id: str) -> Entry | None:
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    def by_name(self, name: str) -> Entry | None:
        key = name_key(name)
        return next((entry for entry in self.entries if name_key(entry.name) == key), None)

    def lexical(self, text: str) -> list[tuple[Entry, int]]:
        """Entrées dont au moins un indice apparaît dans le texte, avec le nombre d'indices."""
        plain = searchable(text)
        hits = []
        for entry in self.entries:
            if entry.pattern is None:
                continue
            count = len(entry.pattern.findall(plain))
            if count:
                hits.append((entry, count))
        return sorted(hits, key=lambda hit: -hit[1])

    def labels(self) -> str:
        return "\n".join(f"- {entry.name} ({entry.category})" for entry in self.entries)


__all__ = ["CATEGORIES", "Clause", "Entry", "Referentiel", "clauses", "fold", "is_evidence"]

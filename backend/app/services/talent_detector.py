"""Repérage des talents en plusieurs passes, entièrement en local.

1. Indices : chaque message est découpé en propositions courtes. Les indices du référentiel
   (mots du métier ou du savoir-être) et une lecture libre par le modèle de langage proposent
   des candidats, chacun avec la citation exacte du jeune.
2. Rapprochement : les propositions et les lectures du modèle sont comparées au référentiel
   ROME/ESCO par embeddings (bge-m3 via Ollama). Un candidat prend alors le nom, la catégorie
   et la description de l'entrée du référentiel, ce qui évite les doublons.
3. Vérification : le modèle relit chaque paire (compétence, citation) et dit si la citation
   montre vraiment ce que le jeune a fait. Le code vérifie ensuite que la citation existe et
   applique les garde-fous.
Chaque passe peut échouer sans bloquer les autres : sans embeddings, on garde les indices et
la lecture libre ; sans réponse claire du vérificateur, on ne garde que les candidats appuyés
par au moins deux signaux.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..errors import LLMError
from .guardrails import find_quote, name_key, words
from .referentiel import CATEGORIES, Entry, clauses, is_evidence

logger = logging.getLogger(__name__)

MAX_PROPOSALS = 4
MAX_VERIFIED = 8
# Similarités cosinus bge-m3, calibrées sur backend/eval/conversations.json.
CLAUSE_STRONG = 0.80
CLAUSE_SECOND = 0.84
LEXICAL_SUPPORT = 0.62
PROPOSAL_MATCH = 0.70
LEXICAL_BONUS = 0.08
COPIED_NAME_RATIO = 0.9
# Un nom affiché au jeune : lettres, espaces, apostrophes et tirets seulement.
_CLEAN_NAME = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ'’ -]{3,80}")

PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "competences": {
            "type": "array",
            "maxItems": MAX_PROPOSALS,
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "categorie": {"type": "string", "enum": list(CATEGORIES)},
                    "description": {"type": "string"},
                    "citation": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["nom", "categorie", "description", "citation", "message"],
            },
        }
    },
    "required": ["competences"],
}

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "montre": {"type": "boolean"}},
                "required": ["id", "montre"],
            },
        }
    },
    "required": ["verdicts"],
}


@dataclass
class Candidate:
    name: str
    category: str
    description: str
    quote: str
    message_id: str
    entry: Entry | None = None
    signals: set[str] = field(default_factory=set)
    similarity: float = 0.0

    @property
    def key(self) -> str:
        return self.entry.id if self.entry else f"libre:{name_key(self.name)}"

    @property
    def score(self) -> float:
        return 1.5 * ("modele" in self.signals) + ("indice" in self.signals) + self.similarity


@dataclass(frozen=True)
class Finding:
    name: str
    category: str
    description: str
    quote: str
    message_id: str
    entry_id: str | None
    signals: tuple[str, ...]


class TalentDetector:
    def __init__(self, llm, prompts, guardrails, referentiel, index=None):
        self.llm = llm
        self.prompts = prompts
        self.guardrails = guardrails
        self.referentiel = referentiel
        self.index = index

    # -- point d'entrée -------------------------------------------------------------------
    def entry_for_name(self, name: str) -> Entry | None:
        """Entrée du référentiel qui correspond à un talent déjà enregistré."""
        entry = self.referentiel.by_name(name)
        if entry is None:
            hits = self.referentiel.lexical(name)
            entry = hits[0][0] if hits else None
        return entry

    def detect(self, messages: list[dict], known_names: list[str] | None = None) -> list[Finding]:
        """Messages du jeune (id, content) déjà filtrés → talents prouvés par une citation."""
        # Une citation courte peut cacher un contexte médical (« ... chez un kiné ») : le
        # message entier est relu avec les mots refusés pour les talents.
        messages = [m for m in messages if not self.guardrails.refused_for_talents(m["content"])]
        if not messages:
            return []
        candidates: dict[str, Candidate] = {}
        pieces = clauses(messages)
        context = {m["id"]: m["content"] for m in messages}

        for clause in pieces:
            if not is_evidence(clause.text, context[clause.message_id]):
                continue
            for entry, _ in self.referentiel.lexical(clause.text):
                self._add(candidates, entry, clause.text, clause.message_id, "indice")

        scores = self._clause_scores(pieces)
        for clause, ranked in zip(pieces, scores):
            if not is_evidence(clause.text, context[clause.message_id]):
                continue
            best = sorted(ranked.items(), key=lambda item: -item[1])[:2]
            for rank, (entry_id, similarity) in enumerate(best):
                if similarity >= (CLAUSE_STRONG if rank == 0 else CLAUSE_SECOND):
                    entry = self.referentiel.get(entry_id)
                    self._add(candidates, entry, clause.text, clause.message_id, "embedding", similarity)
            for candidate in candidates.values():
                if candidate.entry and candidate.quote == clause.text:
                    candidate.similarity = max(candidate.similarity, ranked.get(candidate.entry.id, 0.0))

        for proposal in self._proposals(messages, known_names or []):
            self._merge_proposal(candidates, proposal)

        known = {entry.id for entry in map(self.entry_for_name, known_names or []) if entry}
        pool = [c for c in candidates.values() if not (c.entry and c.entry.id in known)]
        if any(scores):
            # Avec les embeddings, un simple mot (« aide », « seul ») ne suffit plus s'il est loin du sens.
            pool = [c for c in pool if c.signals != {"indice"} or c.similarity >= LEXICAL_SUPPORT]
        return self._verify(pool)

    # -- passe 1 : indices et lecture libre -------------------------------------------------
    def _add(self, candidates, entry, quote, message_id, signal, similarity=0.0):
        current = candidates.get(entry.id)
        if current is None:
            current = Candidate(entry.name, entry.category, entry.description, quote, message_id, entry)
            candidates[entry.id] = current
        elif signal == "modele" or len(quote) < len(current.quote) and "modele" not in current.signals:
            current.quote, current.message_id = quote, message_id
        current.signals.add(signal)
        current.similarity = max(current.similarity, similarity)

    def _clause_scores(self, pieces) -> list[dict[str, float]]:
        if self.index is None or not pieces:
            return [{} for _ in pieces]
        try:
            vectors = self.index.embedder.embed([piece.text for piece in pieces])
            return self.index.rank(vectors)
        except LLMError as error:
            logger.warning("Embeddings indisponibles, repérage sans rapprochement : %s", error)
            return [{} for _ in pieces]

    def _proposals(self, messages, known_names) -> list[dict]:
        lines = [f"[m{index}] {m['content']}" for index, m in enumerate(messages, start=1)]
        aliases = {f"m{index}": m["id"] for index, m in enumerate(messages, start=1)}
        known = ", ".join(known_names) if known_names else "aucune"
        prompt = (
            "Messages écrits par le jeune :\n"
            + "\n".join(lines)
            + f"\n\nCompétences déjà repérées, à ne pas répéter : {known}"
            + "\n\nNoms du référentiel, à reprendre quand l'un d'eux convient :\n"
            + self.referentiel.labels()
        )
        answer = self.llm.generate_json(self.prompts.extraction, prompt, PROPOSAL_SCHEMA)
        proposals = answer.get("competences", []) if isinstance(answer, dict) else []
        found = []
        for proposal in proposals[:MAX_PROPOSALS]:
            if not isinstance(proposal, dict):
                continue
            name = str(proposal.get("nom", "")).strip()[:80]
            if len(name) < 3 or not name_key(name):
                continue
            match = find_quote(
                str(proposal.get("citation", "")), messages, aliases.get(str(proposal.get("message", "")))
            )
            if match is None:
                continue
            description = str(proposal.get("description", "")).strip()[:300]
            # Garde-fous sur la lecture brute du modèle, avant tout rapprochement : un talent
            # refusé ne doit pas revenir sous le nom propre d'une entrée du référentiel.
            if self.guardrails.review_talent(name, description, match.quote) is None:
                continue
            category = proposal.get("categorie")
            found.append(
                {
                    "name": name,
                    "category": category if category in CATEGORIES else "savoir_faire",
                    "description": description,
                    "quote": match.quote,
                    "message_id": match.message_id,
                }
            )
        return found

    # -- passe 2 : rapprochement avec le référentiel ---------------------------------------
    def _merge_proposal(self, candidates, proposal):
        name_ok = bool(_CLEAN_NAME.fullmatch(proposal["name"]))
        # Le modèle recopie souvent un nom du référentiel, parfois avec un accent abîmé.
        entry = self.referentiel.by_name(proposal["name"]) or self._copied_name(proposal["name"])
        similarity = 1.0 if entry else 0.0
        if entry is None and self.index is not None:
            try:
                vector = self.index.embedder.embed([f"{proposal['name']}. {proposal['description']}"])
                ranked = self.index.rank(vector)[0]
                # Un indice du métier dans le nom ou la citation départage deux sens proches
                # (« travailler sur un chantier » : bâtiment plutôt que travail en équipe).
                lexical = {e.id for e, _ in self.referentiel.lexical(f"{proposal['name']} {proposal['quote']}")}
                entry_id, _ = max(ranked.items(), key=lambda item: item[1] + LEXICAL_BONUS * (item[0] in lexical))
                similarity = ranked[entry_id]
                entry = self.referentiel.get(entry_id) if similarity >= PROPOSAL_MATCH else None
            except (LLMError, ValueError) as error:
                logger.warning("Rapprochement impossible : %s", error)
        if entry is None:
            hits = self.referentiel.lexical(f"{proposal['name']} {proposal['description']}")
            entry = hits[0][0] if hits else None
        if entry is not None:
            self._add(candidates, entry, proposal["quote"], proposal["message_id"], "modele", similarity)
            # Le nom du modèle colle au récit (« Diagnostiquer une panne ») : on le garde s'il
            # est propre et proche du sens de l'entrée. Sinon (« Faire des appels téléphoniques »
            # pour des calls de jeu), on prend le nom du référentiel, plus sûr.
            close = similarity >= PROPOSAL_MATCH or self.index is None
            if name_ok and close:
                candidate = candidates[entry.id]
                candidate.name, candidate.description = proposal["name"], proposal["description"]
            return
        key = f"libre:{name_key(proposal['name'])}"
        if name_ok and key not in candidates:
            candidates[key] = Candidate(
                proposal["name"], proposal["category"], proposal["description"],
                proposal["quote"], proposal["message_id"], None, {"modele"},
            )

    def _copied_name(self, name: str) -> Entry | None:
        wanted = name_key(name)
        best = max(
            self.referentiel.entries,
            key=lambda entry: SequenceMatcher(None, wanted, name_key(entry.name)).ratio(),
        )
        return best if SequenceMatcher(None, wanted, name_key(best.name)).ratio() >= COPIED_NAME_RATIO else None

    # -- passe 3 : vérification de la preuve ----------------------------------------------
    def _verify(self, candidates: list[Candidate]) -> list[Finding]:
        candidates = sorted(candidates, key=lambda c: -c.score)[:MAX_VERIFIED]
        if not candidates:
            return []
        verdicts: dict[str, bool] = {}
        lines = [
            f"[c{index}] compétence : {c.name} — citation : « {c.quote} »"
            for index, c in enumerate(candidates, start=1)
        ]
        try:
            answer = self.llm.generate_json(self.prompts.verification, "\n".join(lines), VERIFY_SCHEMA)
            for item in answer.get("verdicts", []) if isinstance(answer, dict) else []:
                if isinstance(item, dict) and isinstance(item.get("montre"), bool):
                    verdicts[str(item.get("id", "")).strip()] = item["montre"]
        except LLMError as error:
            logger.warning("Vérification indisponible : %s", error)

        findings = []
        for index, candidate in enumerate(candidates, start=1):
            verdict = verdicts.get(f"c{index}")
            if verdict is False:
                continue
            if verdict is None and not self._trusted_without_check(candidate):
                continue
            if len(words(candidate.quote)) < 3:
                continue
            description = self.guardrails.review_talent(
                candidate.name, candidate.description, candidate.quote
            )
            if description is None:
                continue
            findings.append(
                Finding(
                    name=candidate.name,
                    category=candidate.category,
                    description=description,
                    quote=candidate.quote,
                    message_id=candidate.message_id,
                    entry_id=candidate.entry.id if candidate.entry else None,
                    signals=tuple(sorted(candidate.signals)),
                )
            )
        return findings

    @staticmethod
    def _trusted_without_check(candidate: Candidate) -> bool:
        if "modele" in candidate.signals:
            return True
        return "indice" in candidate.signals and candidate.similarity >= CLAUSE_STRONG

"""Garde-fous déterministes : ils s'appliquent même si le modèle se trompe.

- repérage de messages de détresse (affiche des contacts d'aide au jeune) ;
- refus des compétences qui touchent à la santé, l'origine, la famille ou la religion ;
- vérification que chaque citation vient réellement des mots du jeune.
Les listes de termes se modifient dans prompts/garde_fous.json.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .prompts import PromptLibrary

MIN_QUOTE_WORDS = 3
MAX_QUOTE_CHARS = 300
FUZZY_QUOTE_RATIO = 0.82

_WORD = re.compile(r"\w+", re.UNICODE)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")


def fold(text: str) -> str:
    """Minuscules sans accents : « Mère » et « mere » deviennent identiques."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return plain.replace("œ", "oe").replace("æ", "ae")


def words(text: str) -> list[str]:
    return _WORD.findall(fold(text))


def name_key(name: str) -> str:
    return " ".join(words(name))[:80]


def _term_pattern(term: str) -> str:
    wildcard = term.endswith("*")
    tokens = words(term.rstrip("*"))
    body = r"\s+".join(re.escape(token) for token in tokens)
    return body + (r"\w*" if wildcard else "s?")


def _compile(terms: list[str]) -> re.Pattern | None:
    patterns = [_term_pattern(term) for term in terms if words(term.rstrip("*"))]
    if not patterns:
        return None
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b")


def _searchable(text: str) -> str:
    return " ".join(words(text))


def matches_any(text: str, terms: list[str]) -> bool:
    pattern = _compile(terms)
    return bool(pattern and pattern.search(_searchable(text)))


@dataclass(frozen=True)
class QuoteMatch:
    message_id: str
    quote: str


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(fold(m.group()), m.start(), m.end()) for m in _WORD.finditer(text)]


def _exact_span(candidate: list[str], text: str) -> str | None:
    spans = _token_spans(text)
    tokens = [span[0] for span in spans]
    size = len(candidate)
    for start in range(len(tokens) - size + 1):
        if tokens[start : start + size] == candidate:
            return text[spans[start][1] : spans[start + size - 1][2]]
    return None


def find_quote(candidate: str, messages: list[dict], preferred_id: str | None = None) -> QuoteMatch | None:
    """Retrouve la citation dans les messages et renvoie le texte exact du jeune.

    Le texte proposé par le modèle n'est jamais conservé : on garde l'extrait d'origine.
    S'il a légèrement reformulé, on retient la phrase source la plus proche.
    """
    wanted = words(candidate)
    if len(wanted) < MIN_QUOTE_WORDS:
        return None
    ordered = sorted(messages, key=lambda message: message["id"] != preferred_id)

    for message in ordered:
        span = _exact_span(wanted, message["content"])
        if span and len(span) <= MAX_QUOTE_CHARS:
            return QuoteMatch(message["id"], span)

    best: tuple[float, QuoteMatch] | None = None
    for message in ordered:
        for sentence in _SENTENCE_BREAK.split(message["content"]):
            sentence = sentence.strip()
            tokens = words(sentence)
            if len(tokens) < MIN_QUOTE_WORDS or len(sentence) > MAX_QUOTE_CHARS:
                continue
            ratio = SequenceMatcher(None, wanted, tokens, autojunk=False).ratio()
            if ratio >= FUZZY_QUOTE_RATIO and (best is None or ratio > best[0]):
                best = (ratio, QuoteMatch(message["id"], sentence))
    return best[1] if best else None


class Guardrails:
    def __init__(self, prompts: PromptLibrary):
        self.prompts = prompts
        self._source: str | None = None
        self._config: dict = {}
        self._crisis: re.Pattern | None = None
        self._quote_terms: re.Pattern | None = None
        self._family_terms: re.Pattern | None = None

    def _load(self) -> dict:
        source = self.prompts.text("garde_fous.json")
        if source != self._source:
            config = self.prompts.json("garde_fous.json")
            topics = config["sujets_sensibles"].values()
            self._crisis = _compile(config["detresse"]["termes"])
            self._quote_terms = _compile(
                [term for topic in topics if topic["bloque_citation"] for term in topic["termes"]]
            )
            self._family_terms = _compile(config["sujets_sensibles"]["famille"]["termes"])
            self._config = config
            self._source = source
        return self._config

    def is_crisis(self, text: str) -> bool:
        self._load()
        return bool(self._crisis and self._crisis.search(_searchable(text)))

    @property
    def crisis_instruction(self) -> str:
        return self._load()["detresse"]["consigne_modele"]

    @property
    def crisis_reply(self) -> str:
        return self._load()["detresse"]["reponse"]

    @property
    def crisis_card(self) -> dict:
        crisis = self._load()["detresse"]
        return {"message": crisis["message"], "resources": crisis["ressources"]}

    def sensitive_reply(self, text: str, turn: int) -> str | None:
        """Réponse relue si le message touche à la santé, l'origine ou la religion."""
        config = self._load()
        if not (self._quote_terms and self._quote_terms.search(_searchable(text))):
            return None
        replies = config["reponses_sujet_sensible"]
        return replies[turn % len(replies)]

    def is_sensitive(self, text: str) -> bool:
        """Le message touche à la santé, l'origine ou la religion : jamais analysé."""
        self._load()
        return bool(self._quote_terms and self._quote_terms.search(_searchable(text)))

    def refused_for_talents(self, text: str) -> bool:
        """Le texte parle de soins ou de médecine : aucun talent ne doit en sortir."""
        config = self._load()
        refused = _compile(config.get("talents_refuses", {}).get("termes", []))
        return bool(refused and refused.search(_searchable(text)))

    def review_talent(self, name: str, description: str, quote: str) -> str | None:
        """Comme review_skill, avec en plus les mots refusés pour les talents seulement.

        « Je veux devenir infirmière » reste une discussion normale, mais aucun talent ne doit
        parler de soins, de médecin ou de médicaments.
        """
        if self.refused_for_talents(f"{name} {description} {quote}"):
            return None
        return self.review_skill(name, description, quote)

    def family_instruction(self, text: str) -> str | None:
        config = self._load()
        if self._family_terms and self._family_terms.search(_searchable(text)):
            return config["consigne_famille"]
        return None

    def review_skill(self, name: str, description: str, quote: str) -> str | None:
        """Renvoie la description à conserver, ou None si la compétence est refusée.

        Garder ses petits frères est une vraie compétence : le récit peut évoquer un proche,
        mais ni le nom ni la description ne doivent en parler. Santé, origine et religion
        écartent la compétence entière.
        """
        self._load()
        blocked = self._quote_terms
        family = self._family_terms
        if blocked and blocked.search(_searchable(f"{name} {description} {quote}")):
            return None
        if family and family.search(_searchable(name)):
            return None
        if family and family.search(_searchable(description)):
            return ""
        return description

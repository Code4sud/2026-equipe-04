"""Garde-fou des sujets hors cadre, lu avant chaque réponse du compagnon.

Deux lectures se complètent :
- un lexique (prompts/garde_fous.json, « sujets_interdits » et « victime ») qui ne rate jamais
  les mots explicites et marche même sans modèle ;
- le modèle de langage, qui comprend le contexte : « j'ai tué le game » reste une discussion
  normale, « je fais le guetteur au four » ne l'est pas.

Catégories : ok, sexuel, illegal, violence, haine (sujets interdits : Truffe répond « Je ne
peux pas parler de ce sujet » et propose autre chose), victime (le jeune confie subir des
violences : il est orienté vers de l'aide, jamais renvoyé) et detresse (réponse de crise).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..errors import LLMError
from .guardrails import _compile, _searchable

logger = logging.getLogger(__name__)

OK = "ok"
VICTIM = "victime"
DISTRESS = "detresse"
FORBIDDEN = ("sexuel", "illegal", "violence", "haine")
CATEGORIES = (OK, *FORBIDDEN, VICTIM, DISTRESS)
SCHEMA = {
    "type": "object",
    "properties": {"categorie": {"type": "string", "enum": list(CATEGORIES)}},
    "required": ["categorie"],
}
CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {"confirme": {"type": "boolean"}},
    "required": ["confirme"],
}
MAX_CONTEXT_CHARS = 300


@dataclass(frozen=True)
class Verdict:
    category: str = OK
    source: str = ""

    @property
    def forbidden(self) -> bool:
        return self.category in FORBIDDEN

    @property
    def victim(self) -> bool:
        return self.category == VICTIM

    @property
    def distress(self) -> bool:
        return self.category == DISTRESS


class Moderator:
    def __init__(self, llm, prompts):
        self.llm = llm
        self.prompts = prompts
        self._source: str | None = None
        self._patterns: dict[str, object] = {}

    def _lexicon(self) -> dict:
        source = self.prompts.text("garde_fous.json")
        if source != self._source:
            config = self.prompts.json("garde_fous.json")
            patterns = {
                category: _compile(terms)
                for category, terms in config.get("sujets_interdits", {}).items()
                if category in FORBIDDEN
            }
            patterns[VICTIM] = _compile(config.get("victime", {}).get("termes", []))
            self._patterns = patterns
            self._source = source
        return self._patterns

    def lexical(self, text: str) -> str:
        plain = _searchable(text)
        patterns = self._lexicon()
        victim = patterns.get(VICTIM)
        if victim is not None and victim.search(plain):
            return VICTIM
        for category in FORBIDDEN:
            pattern = patterns.get(category)
            if pattern is not None and pattern.search(plain):
                return category
        return OK

    def check(self, text: str, previous_reply: str = "") -> Verdict:
        """Catégorie du message ; sans modèle disponible, le lexique décide seul."""
        lexical = self.lexical(text)
        user = self._user_prompt(text, previous_reply)
        model = self._model_category(user)
        if model is None:
            return Verdict(lexical, "lexique")
        # Une confidence de victime l'emporte toujours : on oriente plutôt que de renvoyer.
        if VICTIM in (lexical, model):
            return Verdict(VICTIM, "modele" if model == VICTIM else "lexique")
        if model == DISTRESS:
            return Verdict(DISTRESS, "modele")
        if lexical in FORBIDDEN:
            return Verdict(lexical, "lexique")
        # Refuser à tort un vrai récit (« le patron me laisse la caisse ») casserait la
        # confiance : une alerte du modèle seul est relue avant d'être suivie.
        if model in FORBIDDEN and self._confirmed(user, model):
            return Verdict(model, "modele")
        return Verdict(OK, "modele")

    @staticmethod
    def _user_prompt(text: str, previous_reply: str) -> str:
        context = previous_reply.strip()[:MAX_CONTEXT_CHARS]
        return (f"Dernière réplique de Truffe : {context}\n" if context else "") + f"Message du jeune : {text}"

    def _model_category(self, user: str) -> str | None:
        try:
            answer = self.llm.generate_json(
                self.prompts.text("moderation.md"), user, SCHEMA, temperature=0.0,
                options={"num_predict": 30},
            )
        except LLMError as error:
            logger.warning("Garde-fou sans modèle, lexique seul : %s", error)
            return None
        category = answer.get("categorie") if isinstance(answer, dict) else None
        return category if category in CATEGORIES else None

    def _confirmed(self, user: str, category: str) -> bool:
        try:
            answer = self.llm.generate_json(
                self.prompts.text("moderation_verification.md"),
                f"{user}\nCatégorie proposée : {category}",
                CONFIRM_SCHEMA,
                temperature=0.0,
                options={"num_predict": 20},
            )
        except LLMError as error:
            logger.warning("Alerte du garde-fou non relue, suivie par prudence : %s", error)
            return True
        return not (isinstance(answer, dict) and answer.get("confirme") is False)

"""Vérifie le contenu réellement livré : cohérence, sources et garde-fous.

Les textes du jeune sont lus exactement comme dans le chat (app/services/guardrails.py, termes
de prompts/garde_fous.json), avec en plus le vocabulaire interdit côté jeune.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.game.catalog import Catalog
# Les fonctions du garde-fou du chat elles-mêmes : le lint ne lit jamais un texte autrement.
from app.services.guardrails import Guardrails, _compile, _searchable, fold
from app.services.prompts import PromptLibrary

GUARDRAILS = Path(__file__).resolve().parents[1] / "prompts" / "garde_fous.json"
# Mots à ne jamais montrer au jeune, en plus des sujets du garde-fou du chat. Même syntaxe que
# garde_fous.json : le « s » du pluriel passe toujours et « mot* » couvre la suite du mot.
FORBIDDEN_FOR_YOUTH = [
    # Jugements (faible* couvre aussi faiblesse)
    "nul", "nulle", "mauvais*", "faible*", "anormal*", "deficit*",
    "associable", "asociab*", "insociab*", "asocial*", "antisocial*",
    # Mesures qu'on ne montre pas au jeune (« q i » lit aussi Q.I.)
    "qi", "q i", "quotient intellectuel", "mbti", "myers*", "briggs",
    # Licences existantes
    "harry potter", "hogwart*", "poudlard", "gryffondor", "serpentard", "serdaigle", "poufsouffle",
    "donjon*", "dragon*",
]
# Expressions courantes, sans jugement : masquées avant de chercher le vocabulaire interdit.
ALLOWED_FOR_YOUTH = ["nulle part", "match nul", "matchs nuls"]


class TermMatcher:
    """Des termes lus comme dans le chat : accents, majuscules, œ, apostrophes, tirets et « s »
    final ne changent rien. Comme `re.Pattern.search`, `search` prend le texte tel quel."""

    def __init__(self, terms: list[str], allowed: list[str] | None = None):
        self.pattern = _compile(terms)
        self.allowed = _compile(allowed or [])

    def search(self, text: str) -> re.Match | None:
        searchable = _searchable(text)
        if self.allowed:
            # Ni lettre ni espace à la place : les mots voisins ne forment pas un terme à eux deux.
            searchable = self.allowed.sub("·", searchable)
        return self.pattern.search(searchable) if self.pattern else None


def normalize(text: str) -> str:
    """Texte replié comme dans le chat, avec l'apostrophe droite : pour chercher une sous-chaîne."""
    return fold(text.replace("’", "'"))


def sensitive_patterns() -> list[tuple[str, TermMatcher]]:
    """Chaque sujet du garde-fou du chat, détresse comprise, puis le vocabulaire interdit au jeune."""
    data = json.loads(GUARDRAILS.read_text(encoding="utf-8"))
    topics = {"detresse": data["detresse"]["termes"]}
    topics |= {name: topic["termes"] for name, topic in data["sujets_sensibles"].items()}
    matchers = [(name, TermMatcher(terms)) for name, terms in topics.items()]
    return matchers + [("wording", TermMatcher(FORBIDDEN_FOR_YOUTH, ALLOWED_FOR_YOUTH))]


def guardrail_problems(texts) -> list[str]:
    """Textes qui touchent un sujet sensible, un mot interdit au jeune ou un tiret cadratin."""
    texts = list(texts)
    patterns = sensitive_patterns()
    problems = [
        f"{where} [{topic} : {match.group()}] {text}"
        for where, text in texts
        for topic, matcher in patterns
        if text and (match := matcher.search(text))
    ]
    return problems + [f"{where} [tiret cadratin] {text}" for where, text in texts if "—" in text]


def youth_texts(catalog: Catalog):
    for instrument in catalog.instruments.values():
        public = catalog.public_instrument(instrument)
        for field in ("title", "tagline", "intro", "outro", "source_note"):
            if public.get(field):
                yield instrument["id"], public[field]
        for chapter in public.get("chapters", []):
            yield instrument["id"], chapter.get("title", "")
            yield instrument["id"], chapter.get("intro", "")
        for item in public.get("items", []):
            yield f"{instrument['id']}/{item['id']}", item["prompt"]
            yield f"{instrument['id']}/{item['id']}", item.get("hint", "")
            for option in item.get("options", []):
                yield f"{instrument['id']}/{item['id']}", option["label"]
    for clan in catalog.clans:
        yield clan["id"], f"{clan['name']} {clan['motto']} {clan['description']}"
    for trait in catalog.traits.values():
        yield trait["id"], " ".join(str(v) for v in trait["youth"].values())
    for attribute in catalog.sheet["attributes"]:
        yield attribute["id"], f"{attribute['label']} {attribute['description']}"
    for badge in catalog.sheet["badges"]:
        yield badge["id"], f"{badge['label']} {badge['description']}"


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def test_youth_facing_text_respects_guardrails(catalog):
    problems = guardrail_problems(youth_texts(catalog))
    assert not problems, "\n".join(problems)


# Texte → sujets repérés : formes piégeuses du français, puis mots ordinaires à laisser passer.
TRICKY_TEXTS = {
    "Tes parents te demandent un service": {"famille"},
    "Ta sœur t’appelle": {"famille"},
    "TA SŒUR T'APPELLE": {"famille"},
    "Tes frères": {"famille"},
    "Tes grands-parents": {"famille"},
    "Tu prends des médicaments ?": {"sante"},
    "Les maladies": {"sante"},
    "Direction l’hôpital": {"sante"},
    "Direction l'HÔPITAL": {"sante"},
    "Les religions": {"religion"},
    "Tu es sans-papiers ?": {"origine"},
    "J’ai envie d’en finir": {"detresse"},
    "Tes faiblesses": {"wording"},
    "Ton point faible": {"wording"},
    "Plutôt asociable": {"wording"},
    "Un brin insociable": {"wording"},
    "Donjon et Dragon": {"wording"},
    "Comme dans Harry Potter": {"wording"},
    "Hogwarts Legacy": {"wording"},
    "Quotient intellectuel": {"wording"},
    "Ton Q.I. ?": {"wording"},
    "Ton QI": {"wording"},
    "Profil MBTI": {"wording"},
    "Myers-Briggs": {"wording"},
    "Maison Serpentard": {"wording"},
    "T’es nul": {"wording"},
    "C'est NULLE": {"wording"},
    "Des idées nulles": {"wording"},
    "Match nul, mais ta passe était nulle": {"wording"},
    "Mauvaise réponse": {"wording"},
    "Un résultat anormal": {"wording"},
    "Un déficit d’attention": {"wording"},
    "Tu ne vas nulle part sans ton casque": set(),
    "Un match nul, et alors ?": set(),
    "Deux matchs nuls d’affilée": set(),
    "Annuler la partie": set(),
    "Une parenthèse": set(),
    "Un écart apparent": set(),
    "Merci, la mer est calme": set(),
    "Un repère": set(),
    "Plutôt sociable": set(),
    "Qui veut jouer ?": set(),
    "Les origines du jeu": set(),
}


def flagged(text: str) -> set[str]:
    return {topic for topic, matcher in sensitive_patterns() if matcher.search(text)}


@pytest.mark.parametrize(("text", "topics"), TRICKY_TEXTS.items(), ids=list(TRICKY_TEXTS))
def test_lint_catches_tricky_forms_and_spares_ordinary_words(text, topics):
    assert flagged(text) == topics


def test_lint_reads_texts_like_the_chat_guardrail():
    rails = Guardrails(PromptLibrary(str(GUARDRAILS.parent)))
    data = json.loads(GUARDRAILS.read_text(encoding="utf-8"))
    blocking = {name for name, topic in data["sujets_sensibles"].items() if topic["bloque_citation"]}
    for text in TRICKY_TEXTS:
        topics = flagged(text)
        assert rails.is_crisis(text) == ("detresse" in topics), text
        assert (rails.sensitive_reply(text, 0) is not None) == bool(topics & blocking), text
        assert (rails.family_instruction(text) is not None) == ("famille" in topics), text


def test_every_scored_instrument_cites_a_real_source(catalog):
    for instrument in catalog.instruments.values():
        if instrument["tier"] == "custom":
            continue
        assert instrument["source_ids"], instrument["id"]
        for source_id in instrument["source_ids"]:
            source = catalog.sources[source_id]
            for field in ("title", "citation", "url", "licence", "adaptation"):
                assert source.get(field), f"{source_id} : {field}"


def test_validated_items_point_to_their_original(catalog):
    for instrument in catalog.instruments.values():
        if instrument["tier"] != "validated":
            continue
        for item in instrument["items"]:
            source = item.get("source") or {}
            assert source.get("ref") and source.get("original"), f"{instrument['id']}/{item['id']}"

"""Vérifie le contenu réellement livré : cohérence, sources et garde-fous."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pytest

from app.game.catalog import Catalog

GUARDRAILS = Path(__file__).resolve().parents[1] / "prompts" / "garde_fous.json"
# Mots à ne jamais montrer au jeune, en plus des sujets sensibles du compagnon.
FORBIDDEN_FOR_YOUTH = [
    "associable", "asocial*", "antisocial*", "nul", "nulle", "faible", "faibles", "mauvais*",
    "anormal*", "deficit*", "qi", "mbti", "myers*", "poudlard", "gryffondor", "serpentard",
    "serdaigle", "poufsouffle", "donjons", "dragons",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("’", "'")).lower()
    return "".join(c for c in text if not unicodedata.combining(c))


def pattern(term: str) -> re.Pattern:
    term = normalize(term)
    body = re.escape(term.rstrip("*")).replace(r"\ ", r"\s+")
    return re.compile(rf"\b{body}{'\\w*' if term.endswith('*') else r'\b'}")


def sensitive_patterns() -> list[tuple[str, re.Pattern]]:
    data = json.loads(GUARDRAILS.read_text(encoding="utf-8"))
    terms = [
        (name, term)
        for name, topic in data["sujets_sensibles"].items()
        for term in topic["termes"]
    ]
    terms += [("wording", term) for term in FORBIDDEN_FOR_YOUTH]
    return [(name, pattern(term)) for name, term in terms]


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
    patterns = sensitive_patterns()
    problems = [
        f"{where} [{topic}] : {text}"
        for where, text in youth_texts(catalog)
        for topic, regex in patterns
        if text and regex.search(normalize(text))
    ]
    assert not problems, "\n".join(problems)


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
    # Test validé, ou sa traduction maison : chaque item cite son original.
    checked = [i for i in catalog.instruments.values() if i["tier"] in {"validated", "translated"}]
    assert checked, "aucun instrument issu d'un test validé : ce test ne vérifierait rien"
    for instrument in checked:
        for item in instrument["items"]:
            source = item.get("source") or {}
            assert source.get("ref") and source.get("original"), f"{instrument['id']}/{item['id']}"

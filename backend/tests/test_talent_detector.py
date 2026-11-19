"""Moteur de repérage des talents en plusieurs passes, avec un faux modèle déterministe."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.guardrails import Guardrails
from app.services.prompts import PromptLibrary
from app.services.referentiel import Referentiel, clauses, is_evidence
from app.services.talent_detector import TalentDetector

PROMPTS = PromptLibrary(str(Path(__file__).resolve().parent.parent / "prompts"))
CAPTURE = [
    {"id": "a", "content": "j'ai aidé mon père à réparer la voiture"},
    {"id": "b", "content": "j'apprends pas mal de choses en mécanique à chaque fois"},
    {"id": "c", "content": "je regarde sur YouTube"},
]


class ScriptedLLM:
    """Lecture libre et verdicts écrits à l'avance ; verdicts absents = le vérificateur se tait."""

    def __init__(self, proposals=None, verdict=None):
        self.proposals = proposals or []
        self.verdict = verdict
        self.verify_inputs: list[str] = []

    def generate_json(self, system, user, schema, temperature=None, examples=None):
        if "verdicts" in schema["properties"]:
            self.verify_inputs.append(user)
            if self.verdict is None:
                return {}
            ids = [line.split("]")[0].lstrip("[") for line in user.splitlines()]
            return {"verdicts": [{"id": i, "montre": self.verdict(line)} for i, line in zip(ids, user.splitlines())]}
        return {"competences": self.proposals}


class KeywordEmbedder:
    """Faux embeddings : un axe par entrée du référentiel, activé par ses exemples."""

    def __init__(self, referentiel):
        self.referentiel = referentiel

    def embed(self, texts):
        entries = self.referentiel.entries
        vectors = []
        for text in texts:
            hits = {entry.id for entry, _ in self.referentiel.lexical(text)}
            vectors.append([1.0 if entry.id in hits else 0.01 for entry in entries])
        return vectors


def detector(llm, with_embeddings=False):
    referentiel = Referentiel(PROMPTS)
    index = None
    if with_embeddings:
        from app.services.embeddings import ReferentielIndex

        index = ReferentielIndex(KeywordEmbedder(referentiel), referentiel)
    return TalentDetector(llm, PROMPTS, Guardrails(PROMPTS), referentiel, index)


def test_referentiel_entries_are_safe_and_use_game_categories():
    guardrails = Guardrails(PROMPTS)
    referentiel = Referentiel(PROMPTS)
    assert len(referentiel.entries) >= 50
    assert len({entry.id for entry in referentiel.entries}) == len(referentiel.entries)
    for entry in referentiel.entries:
        assert guardrails.review_talent(entry.name, entry.description, "") == entry.description, entry.id
        assert entry.examples and entry.pattern is not None


def test_clauses_keep_the_shortest_meaningful_quote():
    texts = [c.text for c in clauses([{"id": "m", "content": "j'apprends à chaque fois, je regarde sur YouTube et je teste"}])]
    assert "je regarde sur YouTube" in texts
    assert all(len(t.split()) >= 3 for t in texts)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("j'ai aidé à réparer la voiture", True),
        ("on a refait la peinture", True),
        ("j'aimerais devenir mécanicien", False),
        ("je sais pas faire grand-chose", False),
        ("la voiture de mon voisin est rouge", False),
    ],
)
def test_evidence_is_an_action_told_in_first_person(text, expected):
    assert is_evidence(text) is expected


def test_capture_finds_trade_help_and_learning_when_verifier_agrees():
    llm = ScriptedLLM(verdict=lambda line: True)
    found = {f.entry_id: f for f in detector(llm).detect(CAPTURE)}
    assert {"mecanique", "entraide", "apprendre_experience", "apprendre_seul"} <= set(found)
    assert found["apprendre_seul"].quote == "je regarde sur YouTube"
    assert found["entraide"].category == "relationnel"
    # Le nom vient du référentiel et ne cite jamais le lien familial.
    assert "père" not in found["entraide"].name


def test_verifier_can_refuse_a_candidate():
    llm = ScriptedLLM(verdict=lambda line: "Bricoler" not in line)
    found = {f.entry_id for f in detector(llm).detect(CAPTURE)}
    assert "bricolage" not in found and "mecanique" in found


def test_silent_verifier_keeps_only_well_supported_candidates():
    llm = ScriptedLLM(verdict=None)
    assert detector(llm).detect(CAPTURE) == []
    found = {f.entry_id for f in detector(llm, with_embeddings=True).detect(CAPTURE)}
    assert "apprendre_seul" in found


def test_wishes_never_become_talents():
    llm = ScriptedLLM(verdict=lambda line: True)
    messages = [{"id": "a", "content": "j'aimerais bien devenir mécanicien plus tard"}]
    assert detector(llm).detect(messages) == []


def test_model_proposal_keeps_its_name_and_gets_the_referentiel_category():
    proposal = {
        "nom": "Diagnostiquer une panne",
        "categorie": "savoir_faire",
        "description": "Chercher l'origine d'un problème.",
        "citation": "je teste pièce par pièce jusqu'à trouver la panne",
        "message": "m1",
    }
    llm = ScriptedLLM([proposal], verdict=None)
    messages = [{"id": "a", "content": "Je répare les scooters et je teste pièce par pièce jusqu'à trouver la panne."}]
    found = detector(llm).detect(messages)
    assert [(f.name, f.category, f.entry_id) for f in found] == [
        ("Diagnostiquer une panne", "resolution_problemes", "diagnostic")
    ]


def test_already_known_talents_are_not_found_again():
    llm = ScriptedLLM(verdict=lambda line: True)
    found = detector(llm).detect(CAPTURE, ["Apprendre en autonomie", "Réparer une voiture"])
    ids = {f.entry_id for f in found}
    assert "apprendre_seul" not in ids and "mecanique" not in ids


def test_medical_words_are_refused_for_talents_only():
    guardrails = Guardrails(PROMPTS)
    assert guardrails.review_talent("Accueillir des patients", "", "j'ai aidé à l'accueil chez un kiné") is None
    assert guardrails.review_talent("Aider un médecin", "", "j'ai rangé les dossiers") is None
    assert not guardrails.is_sensitive("je veux devenir infirmière")
    assert guardrails.is_sensitive("je vais à l'hôpital pour ma maladie")


def test_sensitive_messages_are_never_analysed(client, youth, llm):
    from conftest import send

    conversation = client.post("/api/conversations", headers=youth).get_json()["conversation"]["id"]
    llm.proposals = [
        {
            "nom": "Gérer ses rendez-vous",
            "categorie": "organisation",
            "description": "S'organiser.",
            "citation": "je gère mes rendez-vous moi-même",
            "message": "m1",
        }
    ]
    send(client, youth, conversation, "Pour ma maladie je gère mes rendez-vous moi-même, sans aide.")
    client.post("/api/me/skills/refresh", headers=youth)
    assert client.get("/api/me/skills", headers=youth).get_json()["skills"] == []
    assert llm.json_calls == []


def test_revealed_talent_gets_a_real_category(app, client, youth):
    from app.extensions import db
    from app.models import Conversation
    from app.services.chat import RevealedTalent

    conversation_id = client.post("/api/conversations", headers=youth).get_json()["conversation"]["id"]
    with app.app_context():
        conversation = db.session.get(Conversation, __import__("uuid").UUID(conversation_id))
        extraction = app.extensions["extraction"]
        told = extraction.save_revealed(
            conversation, RevealedTalent("Transmettre à des débutants", "j'explique aux nouveaux", "x", "communication")
        )
        guessed = extraction.save_revealed(
            conversation, RevealedTalent("Apprendre avec des tutos", "je regarde des tutos", "y")
        )
        assert told.category == "communication"
        assert guessed.category == "apprentissage"

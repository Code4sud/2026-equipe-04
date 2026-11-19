"""Garde-fou des sujets hors cadre et priorité du compagnon sur le lecteur de talents."""
from __future__ import annotations

import threading
from pathlib import Path

from app.errors import LLMError
from app.services.llm import ChatPriority
from app.services.moderation import Moderator
from app.services.prompts import PromptLibrary

PROMPTS = PromptLibrary(str(Path(__file__).resolve().parent.parent / "prompts"))


class AnswerLLM:
    def __init__(self, category="ok", confirm=True, fail=False):
        self.category = category
        self.confirm = confirm
        self.fail = fail
        self.calls = []

    def generate_json(self, system, user, schema, temperature=None, examples=None, options=None):
        self.calls.append(user)
        if self.fail:
            raise LLMError("indisponible")
        if "confirme" in schema["properties"]:
            return {"confirme": self.confirm}
        return {"categorie": self.category}


def test_lexicon_only_holds_unambiguous_words():
    moderator = Moderator(AnswerLLM(), PROMPTS)
    for text in (
        "j'ai tué le game à l'oral",
        "on s'est fait défoncer au foot",
        "j'ai volé la vedette au concours",
        "je garde mes petits cousins",
        "je fais la caisse au marché",
        "je joue à GTA avec mes potes",
        "ça me touche beaucoup ce que tu dis",
    ):
        assert moderator.lexical(text) == "ok", text
    assert moderator.lexical("je regarde du porno") == "sexuel"
    assert moderator.lexical("tu sais où acheter de la beuh") == "illegal"
    assert moderator.lexical("je me fais harceler sur snap") == "victime"
    # Une agression sexuelle confiée n'est jamais un sujet interdit.
    assert moderator.lexical("j'ai subi une agression sexuelle") == "victime"


def test_victim_wins_over_a_forbidden_reading():
    verdict = Moderator(AnswerLLM("victime"), PROMPTS).check("un mec m'a forcée à faire des trucs sexuels")
    assert verdict.victim and not verdict.forbidden


def test_model_alert_is_followed_only_when_confirmed():
    assert Moderator(AnswerLLM("illegal", confirm=True), PROMPTS).check("je fais le guetteur").forbidden
    assert not Moderator(AnswerLLM("illegal", confirm=False), PROMPTS).check("le patron me laisse la caisse").forbidden


def test_without_the_model_the_lexicon_decides():
    moderator = Moderator(AnswerLLM(fail=True), PROMPTS)
    assert moderator.check("je regarde du porno").category == "sexuel"
    assert moderator.check("je répare des vélos").category == "ok"


def test_chat_takes_priority_over_the_reader(tmp_path):
    priority = ChatPriority(str(tmp_path / "priorite.lock"))
    assert not priority.chat_active()
    started, release = threading.Event(), threading.Event()

    def reply():
        with priority.chat():
            started.set()
            release.wait(5)

    worker = threading.Thread(target=reply)
    worker.start()
    started.wait(5)
    assert priority.chat_active()
    release.set()
    worker.join(5)
    assert not priority.chat_active()

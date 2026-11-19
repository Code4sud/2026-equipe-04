from __future__ import annotations

import pytest
from conftest import parse_sse, register, send
from sqlalchemy import select

from app.extensions import db
from app.models import Skill
from app.services.guardrails import Guardrails, find_quote
from app.services.prompts import PromptLibrary

STORY = "Je répare les scooters des potes et je teste pièce par pièce jusqu'à trouver la panne."
GOOD_PROPOSAL = {
    "nom": "Diagnostiquer une panne",
    "categorie": "resolution_problemes",
    "description": "Chercher l'origine d'un problème.",
    "citation": "je teste pièce par pièce jusqu'à trouver la panne",
    "message": "m1",
}


def open_conversation(client, headers) -> str:
    response = client.post("/api/conversations", headers=headers)
    assert response.status_code in {200, 201}
    return response.get_json()["conversation"]["id"]


def extract(client, headers, content=STORY):
    conversation_id = open_conversation(client, headers)
    send(client, headers, conversation_id, content)
    assert client.post("/api/me/skills/refresh", headers=headers).status_code == 200
    return conversation_id, client.get("/api/me/skills", headers=headers).get_json()["skills"]


def test_register_login_and_me(client):
    headers = register(client, "Léa")
    assert client.get("/api/auth/me", headers=headers).get_json()["user"]["role"] == "youth"
    bad = client.post("/api/auth/login", json={"email": "lea@example.org", "password": "non"})
    assert bad.status_code == 401
    good = client.post("/api/auth/login", json={"email": "LEA@example.org", "password": "motdepasse"})
    assert good.status_code == 200


def test_register_rejects_duplicates_and_weak_passwords(client):
    register(client, "Léa")
    duplicate = client.post(
        "/api/auth/register",
        json={"display_name": "Autre", "email": "lea@example.org", "password": "motdepasse", "accept_sharing": True},
    )
    assert duplicate.status_code == 409
    weak = client.post(
        "/api/auth/register",
        json={"display_name": "Autre", "email": "b@example.org", "password": "court"},
    )
    assert weak.status_code == 400


def test_routes_require_the_right_role(client, youth, psychologist):
    assert client.get("/api/conversations").status_code == 401
    assert client.get("/api/backoffice/youths", headers=youth).status_code == 403
    assert client.get("/api/me/skills", headers=psychologist).status_code == 403


def test_conversation_streams_reply_and_stores_text_outside_database(client, youth, store):
    first = client.post("/api/conversations", headers=youth)
    assert first.status_code == 201
    payload = first.get_json()
    assert payload["messages"][0]["role"] == "assistant"
    again = client.post("/api/conversations", headers=youth)
    assert again.status_code == 200
    assert again.get_json()["conversation"]["id"] == payload["conversation"]["id"]

    events = send(client, youth, payload["conversation"]["id"], "Je fais du vélo")
    names = [name for name, _ in events]
    assert names[:2] == ["start", "reply"] and names[-1] == "done" and "delta" in names
    assert events[1][1] == {"kind": "model"}
    assert events[-1][1]["assistant_message"]["content"] == "Bien joué !"

    stored = next(iter(store.objects.values()))
    assert [m["role"] for m in stored["messages"]] == ["assistant", "user", "assistant"]


def test_youth_cannot_read_another_conversation(client, youth):
    conversation_id = open_conversation(client, youth)
    other = register(client, "Tom")
    assert client.get(f"/api/conversations/{conversation_id}", headers=other).status_code == 404
    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "x"}, headers=other
    )
    assert response.status_code == 404


def test_llm_failure_can_be_retried_without_duplicating_the_message(client, youth, llm, store):
    conversation_id = open_conversation(client, youth)
    llm.fail = True
    events = send(client, youth, conversation_id, "Je fais du vélo")
    assert events[-1] == ("error", {"code": "llm_unavailable"})

    llm.fail = False
    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"retry": True}, headers=youth
    )
    assert parse_sse(response)[-1][0] == "done"
    stored = next(iter(store.objects.values()))
    assert [m["role"] for m in stored["messages"]] == ["assistant", "user", "assistant"]

    nothing = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"retry": True}, headers=youth
    )
    assert nothing.status_code == 409


def test_closed_conversation_refuses_messages_and_a_new_one_can_start(client, youth):
    conversation_id = open_conversation(client, youth)
    assert client.post(f"/api/conversations/{conversation_id}/close", headers=youth).status_code == 200
    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "x"}, headers=youth
    )
    assert response.status_code == 409
    assert open_conversation(client, youth) != conversation_id


def test_extraction_pins_the_talent_with_the_youth_exact_words(client, youth, llm):
    llm.proposals = [{**GOOD_PROPOSAL, "citation": "JE TESTE pièce par pièce jusqu'a trouver la panne"}]
    _, skills = extract(client, youth)
    assert len(skills) == 1
    assert skills[0]["status"] == "validated"
    assert skills[0]["quote"] == "je teste pièce par pièce jusqu'à trouver la panne"


def test_extraction_drops_invented_quotes(client, youth, llm):
    llm.proposals = [{**GOOD_PROPOSAL, "citation": "j'ai dirigé une équipe de vingt personnes"}]
    assert extract(client, youth)[1] == []


def test_extraction_only_reads_youth_messages(client, youth, llm):
    llm.tokens = ["Tu sais diriger une équipe de vingt personnes"]
    llm.proposals = [{**GOOD_PROPOSAL, "citation": "diriger une équipe de vingt personnes"}]
    assert extract(client, youth)[1] == []


def test_extraction_blocks_sensitive_inferences(client, youth, llm):
    llm.proposals = [
        {**GOOD_PROPOSAL, "nom": "Soutenir sa mère malade"},
        {**GOOD_PROPOSAL, "nom": "Résilience", "description": "Malgré sa dépression, il avance."},
    ]
    assert extract(client, youth)[1] == []


def test_extraction_blocks_quotes_about_health(client, youth, llm):
    story = "Je gère tous mes rendez-vous à l'hôpital pour ma maladie toute seule."
    llm.proposals = [
        {**GOOD_PROPOSAL, "nom": "Gérer un agenda", "citation": story, "description": "S'organiser."}
    ]
    assert extract(client, youth, story)[1] == []


def test_rejected_skill_is_not_proposed_again(client, youth, llm):
    llm.proposals = [GOOD_PROPOSAL]
    conversation_id, skills = extract(client, youth)
    client.patch(f"/api/me/skills/{skills[0]['id']}", json={"status": "rejected"}, headers=youth)
    send(client, youth, conversation_id, "Je teste pièce par pièce, toujours pareil, ça marche bien.")
    client.post("/api/me/skills/refresh", headers=youth)
    skills = client.get("/api/me/skills", headers=youth).get_json()["skills"]
    assert [skill["status"] for skill in skills] == ["rejected"]


def test_failed_extraction_is_retried(client, youth, llm):
    llm.proposals = [GOOD_PROPOSAL]
    llm.fail = True
    conversation_id = open_conversation(client, youth)
    llm.fail = False
    send(client, youth, conversation_id, STORY)
    llm.fail = True
    client.post("/api/me/skills/refresh", headers=youth)
    llm.fail = False
    client.post("/api/me/skills/refresh", headers=youth)
    assert len(client.get("/api/me/skills", headers=youth).get_json()["skills"]) == 1


def test_youth_can_rename_and_cannot_touch_another_skill(client, youth, llm):
    llm.proposals = [GOOD_PROPOSAL]
    _, skills = extract(client, youth)
    url = f"/api/me/skills/{skills[0]['id']}"
    renamed = client.patch(url, json={"name": "Trouver une panne", "status": "validated"}, headers=youth)
    assert renamed.get_json()["skill"]["name"] == "Trouver une panne"
    assert renamed.get_json()["skill"]["status"] == "validated"
    assert client.patch(url, json={"status": "pending"}, headers=youth).status_code == 400
    other = register(client, "Tom")
    assert client.patch(url, json={"status": "rejected"}, headers=other).status_code == 404




def test_distress_shows_help_and_is_never_analysed(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    llm.proposals = [
        {**GOOD_PROPOSAL, "citation": "plus envie de vivre en ce moment, je tiens plus"}
    ]
    events = send(client, youth, conversation_id, "J'ai plus envie de vivre en ce moment, je tiens plus.")
    assert [name for name, _ in events][:3] == ["start", "safety", "reply"]
    assert events[2][1] == {"kind": "crisis"}
    assert any(item["contact"] == "3114" for item in events[1][1]["resources"])
    # La réponse à la détresse est un texte relu : le modèle n'est pas appelé.
    assert llm.chat_calls == []
    assert "3114" in events[-1][1]["assistant_message"]["content"]

    client.post("/api/me/skills/refresh", headers=youth)
    assert llm.json_calls == []
    reloaded = client.get(f"/api/conversations/{conversation_id}", headers=youth).get_json()
    assert reloaded["safety"]["resources"]

    short = send(client, youth, conversation_id, "Oui ça va, je suis chez moi.")
    assert llm.chat_calls == []
    assert "3114" in short[-1][1]["assistant_message"]["content"]
    send(client, youth, conversation_id, "Oui ça va, je suis chez moi, je regarde une série tranquille.")
    assert "ATTENTION" in llm.chat_calls[-1][0]["content"]


def test_model_history_starts_with_the_youth(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "Je fais du vélo tous les jours")
    messages = llm.chat_calls[-1]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "On part explorer" not in " ".join(message["content"] for message in messages)


def test_sensitive_topics_get_a_reviewed_reply_without_the_model(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    events = send(client, youth, conversation_id, "Je vais à la mosquée et ma santé est fragile.")
    assert llm.chat_calls == []
    assert dict(events)["reply"] == {"kind": "sensitive"}
    assert "Merci" in events[-1][1]["assistant_message"]["content"] or "entends" in events[-1][1]["assistant_message"]["content"]


def test_short_answers_get_an_easy_prompt_without_the_model(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    opening = send(client, youth, conversation_id, "JSP")
    assert dict(opening)["reply"] == {"kind": "relaunch"}
    first = opening[-1][1]["assistant_message"]["content"]
    second = send(client, youth, conversation_id, "bof...")[-1][1]["assistant_message"]["content"]
    assert llm.chat_calls == []
    assert first != second


def test_family_mentions_add_a_restraint_for_the_model(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "Je garde mon petit frère et je l'aide pour ses devoirs.")
    assert "sans poser aucune question sur lui" in llm.chat_calls[-1][0]["content"]


REVEAL_TURNS = (
    "Je fais du vélo",
    "Je répare les roues",
    "Je gonfle aussi les pneus",
    "Je règle aussi les freins de tous les copains",
)


def reveal_reply(client, youth) -> str:
    conversation_id = open_conversation(client, youth)
    events = [send(client, youth, conversation_id, text) for text in REVEAL_TURNS]
    return events[-1][-1][1]["assistant_message"]["content"]


def test_skill_is_revealed_every_fourth_turn_with_the_youth_exact_words(client, youth, llm):
    llm.reveal = {"citation": "RÈGLE aussi les freins", "savoir_faire": "Entretenir un vélo."}
    reply = reveal_reply(client, youth)
    assert reply == (
        "Attends, je crois que j’ai trouvé un talent. Quand tu dis « règle aussi les freins », "
        "je vois quelqu’un qui sait entretenir un vélo. Tu te reconnais là-dedans ?"
    )
    assert len(llm.reveal_calls) == 1


def test_reveal_turn_is_announced_to_the_interface(client, youth, llm):
    llm.reveal = {"citation": "règle aussi les freins", "savoir_faire": "entretenir un vélo"}
    conversation_id = open_conversation(client, youth)
    kinds = [dict(send(client, youth, conversation_id, text))["reply"]["kind"] for text in REVEAL_TURNS]
    assert kinds == ["model", "model", "model", "reveal"]


@pytest.mark.parametrize(
    "answer",
    [
        {"citation": "j'ai dirigé une équipe entière", "savoir_faire": "diriger une équipe"},
        {"citation": "...", "savoir_faire": "entretenir un vélo"},
        {"citation": "règle aussi les freins", "savoir_faire": "aider sa mère"},
        {"citation": "règle aussi les freins", "savoir_faire": "mécanique de vélo"},
        {"citation": "", "savoir_faire": ""},
    ],
)
def test_unsafe_reveal_falls_back_to_listening(client, youth, llm, answer):
    llm.reveal = answer
    assert "talent" not in reveal_reply(client, youth)
    # Le quatrième tour revient au modèle, qui écrit une réponse libre.
    assert len(llm.reveal_calls) == 1 and len(llm.chat_calls) >= 4


def test_same_quote_is_not_revealed_twice(client, youth, llm):
    llm.reveal = {"citation": "règle aussi les freins", "savoir_faire": "entretenir un vélo"}
    conversation_id = open_conversation(client, youth)
    for text in REVEAL_TURNS:
        send(client, youth, conversation_id, text)
    later = ("Je gonfle les pneus", "Je nettoie la chaîne", "Je change les patins", "Je règle aussi les freins de la voisine le soir")
    for text in later:
        last = send(client, youth, conversation_id, text)
    assert len(llm.reveal_calls) == 2
    assert dict(last)["reply"] == {"kind": "model"}


def test_companion_always_says_it_is_an_ai(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    events = send(client, youth, conversation_id, "t'es un vrai humain ou quoi ?")
    assert llm.chat_calls == []
    assert "intelligence artificielle" in events[-1][1]["assistant_message"]["content"]


def test_follow_up_on_a_sensitive_topic_is_not_sent_to_the_model(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "Je suis malade depuis longtemps.")
    send(client, youth, conversation_id, "Tu crois que c'est pour ça ?")
    assert llm.chat_calls == []


def test_ordinary_words_do_not_trigger_guardrails(app):
    rails = Guardrails(PromptLibrary(app.config["PROMPTS_DIR"]))
    assert not rails.is_crisis("Je coopère avec l'équipe et j'ai fini le tournoi")
    assert rails.is_crisis("J'ai envie d'en finir")
    assert rails.is_crisis("je veux ME SUICIDER")
    review = rails.review_skill
    kept = review("Trouver l'origine d'une panne", "À chaque fois, avec méthode", "je cherche ce qui bloque")
    assert kept == "À chaque fois, avec méthode"
    assert review("Coopérer en équipe", "Opérer une machine", "je garde mon petit frère le soir")
    assert review("Coopérer en équipe", "Opérer une machine", "je répare le toit du temple") is None
    assert review("Aider sa sœur", "", "je donne un coup de main") is None


def test_family_story_gives_a_skill_without_naming_relatives(client, youth, llm):
    story = "Le soir je garde mes petits frères et je vérifie leurs devoirs."
    llm.proposals = [
        {
            "nom": "Garder des enfants",
            "categorie": "relationnel",
            "description": "Prendre soin de ses petits frères.",
            "citation": "je garde mes petits frères",
            "message": "m1",
        }
    ]
    skills = extract(client, youth, story)[1]
    assert [skill["name"] for skill in skills] == ["Garder des enfants"]
    assert skills[0]["description"] == ""
    assert skills[0]["quote"] == "je garde mes petits frères"




def test_demo_data_respects_the_rules(app, store):
    app.config.update(SEED_PSY_PASSWORD="motdepasse", SEED_YOUTH_PASSWORD="motdepasse")
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert len(store.objects) == 2
    rails = app.extensions["guardrails"]
    with app.app_context():
        skills = db.session.scalars(select(Skill)).all()
        assert len(skills) == 6
        for skill in skills:
            assert rails.review_skill(skill.name, skill.description, skill.source_quote) == skill.description


def test_find_quote_returns_original_text():
    messages = [{"id": "a", "content": "Hier, J’ai réparé UN moteur. Puis j'ai rangé."}]
    assert find_quote("j'ai réparé un moteur", messages).quote == "J’ai réparé UN moteur"
    assert find_quote("trop court", messages) is None


def test_storage_failure_returns_a_clear_error(client, youth, store):
    store.fail = True
    response = client.post("/api/conversations", headers=youth)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "storage_unavailable"


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    assert client.get("/api/health/services").get_json()["status"] == "ok"


def test_greeting_and_short_answers_do_not_reach_the_model(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    replies = []
    for text in ("Salut", "Salut", "oui", "ouais", "non pas vraiment"):
        replies.append(send(client, youth, conversation_id, text)[-1][1]["assistant_message"]["content"])
    assert llm.chat_calls == []
    assert len(set(replies)) == len(replies)


def test_repeated_model_reply_is_retried_then_replaced(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    llm.tokens = ["Des vélos le soir, la classe. Comment tu t'y prends ?"]
    first = send(client, youth, conversation_id, "Je répare des vélos le soir")
    assert first[-1][1]["assistant_message"]["content"] == llm.tokens[0]
    second = send(client, youth, conversation_id, "Je change aussi les pneus crevés")
    reply = second[-1][1]["assistant_message"]["content"]
    assert len(llm.chat_calls) == 4
    assert "Comment tu t'y prends" not in reply


def test_repeated_lines_are_removed_from_model_history(client, youth, llm, store):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "Je répare des vélos le soir")
    transcript = next(iter(store.objects.values()))
    transcript["messages"].extend(
        [
            {"id": "a", "role": "assistant", "content": "Comment tu t'y prends ?", "flags": []},
            {"id": "b", "role": "user", "content": "Je regarde des tutos", "flags": []},
            {"id": "c", "role": "assistant", "content": "Comment tu t'y prends ?", "flags": []},
        ]
    )
    send(client, youth, conversation_id, "Je demande aussi aux voisins")
    sent = [m["content"] for m in llm.chat_calls[-1]]
    assert sent.count("Comment tu t'y prends ?") == 1


def test_companion_replies_freely_with_a_varied_turn_instruction(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    events = send(client, youth, conversation_id, "J'ai beaucoup conduit ma voiture cette semaine pour aller bosser")
    assert events[-1][1]["assistant_message"]["content"] == "Bien joué !"
    system = llm.chat_calls[-1][0]["content"]
    assert "Pour ta prochaine réponse" in system
    assert llm.moderation_calls == ["Message du jeune : J'ai beaucoup conduit ma voiture cette semaine pour aller bosser"]


@pytest.mark.parametrize(
    "bad",
    [
        "Tu conduis souvent ? Tu vas où ?",
        "Bonjour ! Ta voiture, tu la prends pour aller où ?",
        "Tu as un vrai talent pour la conduite.",
        "Et ta mère, elle conduit aussi ?",
        "Tu choisis-tu ta route le matin ?",
        "C'est quoi le trajet qui te occupe le plus ?",
        "Il conduit beaucoup, on dirait.",
    ],
)
def test_badly_formed_or_sensitive_replies_are_never_shown(client, youth, llm, bad):
    conversation_id = open_conversation(client, youth)
    llm.tokens = [bad]
    reply = send(client, youth, conversation_id, "J'ai beaucoup conduit ma voiture")[-1][1]
    assert reply["assistant_message"]["content"] != bad
    assert len(llm.chat_calls) == 3


def test_passive_answers_get_a_relaunch_instead_of_a_mocking_question(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    events = send(client, youth, conversation_id, "je sais que dormir")
    assert dict(events)["reply"] == {"kind": "relaunch"}
    assert llm.chat_calls == []


def test_a_failure_is_never_revealed_as_a_talent(client, youth, llm):
    llm.reveal = {"citation": "j'ai raté une fournée", "savoir_faire": "préparer une fournée"}
    conversation_id = open_conversation(client, youth)
    for text in ("Je fais du vélo", "Je répare les roues", "Je gonfle les pneus", "La semaine dernière j'ai raté une fournée de gâteaux"):
        reply = send(client, youth, conversation_id, text)
    assert dict(reply)["reply"] == {"kind": "model"}


def test_self_doubt_gets_encouragement_based_on_the_story(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "J'ai beaucoup conduit ma voiture")
    events = send(client, youth, conversation_id, "Je sais pas je n'ai pas vraiment de compétences")
    reply = events[-1][1]["assistant_message"]["content"]
    assert dict(events)["reply"] == {"kind": "encourage"}
    assert "J'ai beaucoup conduit ma voiture" in reply
    assert len(llm.chat_calls) <= 4


def test_model_can_never_say_the_youth_has_no_skills(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    llm.tokens = ["Tu n'as pas de compétences pour l'instant. Et ta voiture ?"]
    reply = send(client, youth, conversation_id, "J'ai beaucoup conduit ma voiture")[-1][1]
    assert "compétences" not in reply["assistant_message"]["content"]


def test_sharing_with_the_centre_is_required_at_registration(client):
    refused = client.post(
        "/api/auth/register",
        json={"display_name": "Lou", "email": "lou@example.org", "password": "motdepasse"},
    )
    assert refused.status_code == 400
    assert refused.get_json()["error"]["code"] == "consent_required"
    headers = register(client, "Lou")
    privacy = client.get("/api/me/privacy", headers=headers).get_json()
    assert privacy["share_transcripts"] is True and privacy["consent_at"]
    assert client.post("/api/conversations", headers=headers).get_json()["share_transcripts"] is True


def test_psychologist_sees_every_talent_with_the_youth_choices(client, youth, psychologist, llm):
    llm.proposals = [
        GOOD_PROPOSAL,
        {**GOOD_PROPOSAL, "nom": "Organiser sa soirée", "citation": "Je répare les scooters des potes"},
    ]
    conversation_id, skills = extract(client, youth)
    by_name = {skill["name"]: skill for skill in skills}
    kept = by_name["Diagnostiquer une panne"]["id"]
    dropped = by_name["Organiser sa soirée"]["id"]
    client.patch(f"/api/me/skills/{kept}", json={"name": "Trouver une panne", "status": "validated"}, headers=youth)
    client.patch(f"/api/me/skills/{dropped}", json={"status": "rejected"}, headers=youth)
    added = client.post("/api/me/skills", json={"name": "Cuisiner pour les potes"}, headers=youth)
    assert added.status_code == 201 and added.get_json()["skill"]["origin"] == "youth"

    youths = client.get("/api/backoffice/youths", headers=psychologist).get_json()["youths"]
    assert youths[0]["skills_to_discuss"] == 3
    assert youths[0]["rejected_skills"] == 1
    detail = client.get(f"/api/backoffice/youths/{youths[0]['id']}", headers=psychologist).get_json()
    seen = {skill["name"]: skill for skill in detail["skills"]}
    assert seen["Organiser sa soirée"]["status"] == "rejected"
    assert [e["action"] for e in seen["Organiser sa soirée"]["history"]] == ["proposed", "rejected"]
    assert [e["actor"] for e in seen["Organiser sa soirée"]["history"]] == ["ai", "youth"]
    renamed = [e for e in seen["Trouver une panne"]["history"] if e["action"] == "renamed"]
    assert renamed[0]["previous_name"] == "Diagnostiquer une panne"
    assert seen["Cuisiner pour les potes"]["history"][0]["action"] == "added"
    assert all(skill["to_discuss"] for skill in detail["skills"])

    transcript = client.get(
        f"/api/backoffice/youths/{youths[0]['id']}/conversations/{conversation_id}", headers=psychologist
    )
    assert transcript.status_code == 200


def test_youth_cannot_add_a_duplicate_talent(client, youth):
    assert client.post("/api/me/skills", json={"name": "Cuisiner"}, headers=youth).status_code == 201
    assert client.post("/api/me/skills", json={"name": "cuisiner"}, headers=youth).status_code == 409


def test_revealed_talent_is_pinned_right_away_and_shown_to_the_psychologist(client, youth, psychologist, llm):
    llm.reveal = {"citation": "règle aussi les freins", "savoir_faire": "entretenir un vélo"}
    conversation_id = open_conversation(client, youth)
    events = [send(client, youth, conversation_id, text) for text in REVEAL_TURNS]
    talent = dict(events[-1])["done"]["talent"]
    assert talent["name"] == "Entretenir un vélo"
    assert talent["status"] == "validated"
    assert talent["origin"] == "ai"
    assert "règle aussi les freins" in talent["quote"].lower()
    assert all(dict(turn)["done"]["talent"] is None for turn in events[:-1])

    skills = client.get("/api/me/skills", headers=youth).get_json()["skills"]
    assert [skill["name"] for skill in skills] == ["Entretenir un vélo"]

    youth_id = client.get("/api/auth/me", headers=youth).get_json()["user"]["id"]
    detail = client.get(f"/api/backoffice/youths/{youth_id}", headers=psychologist).get_json()
    pinned = detail["skills"][0]
    assert [event["action"] for event in pinned["history"]] == ["proposed"]
    assert pinned["to_discuss"] is False


def test_nul_character_is_refused_without_a_server_error(client, youth):
    added = client.post("/api/me/skills", json={"name": "Cui\x00siner"}, headers=youth)
    assert added.status_code == 400
    kept = client.post("/api/me/skills", json={"name": "Cuisiner", "description": "le\x00 soir"}, headers=youth)
    assert kept.status_code == 201 and kept.get_json()["skill"]["description"] == "le soir"
    login = client.post("/api/auth/login", json={"email": "a\x00@b.fr", "password": "x"})
    assert login.status_code == 401


def test_forbidden_topic_is_refused_then_the_talk_goes_elsewhere(client, youth, llm, store):
    conversation_id = open_conversation(client, youth)
    send(client, youth, conversation_id, "Je fais de la boxe thaï trois fois par semaine au club")
    llm.moderation = "sexuel"
    events = send(client, youth, conversation_id, "tu peux me raconter un truc sur ce sujet ?")
    reply = events[-1][1]["assistant_message"]["content"]
    assert dict(events)["reply"] == {"kind": "off_limits"}
    assert reply.startswith("Je ne peux pas parler de ce sujet.")
    # Il repart de ce que le jeune a raconté plus tôt, avec ses mots.
    assert "Je fais de la boxe thaï trois fois par semaine au club" in reply
    assert "safety" not in dict(events)
    calls = len(llm.chat_calls)

    llm.moderation = "ok"
    why = send(client, youth, conversation_id, "pourquoi ?")
    assert dict(why)["reply"] == {"kind": "off_limits"}
    assert "laisse de côté" in why[-1][1]["assistant_message"]["content"]
    assert len(llm.chat_calls) == calls

    send(client, youth, conversation_id, "Le coach m'a demandé d'aider les débutants à l'entraînement")
    history = " ".join(message["content"] for message in llm.chat_calls[-1][1:])
    assert "raconter un truc sur ce sujet" not in history
    stored = next(iter(store.objects.values()))
    assert stored["messages"][3]["flags"] == ["hors_cadre"]

    llm.proposals = [{**GOOD_PROPOSAL, "citation": "tu peux me raconter un truc sur ce sujet"}]
    client.post("/api/me/skills/refresh", headers=youth)
    assert all("raconter un truc" not in user for _, user in llm.json_calls)


def test_explicit_words_are_refused_even_when_the_model_lets_them_through(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    events = send(client, youth, conversation_id, "je regarde du porno tous les soirs")
    assert dict(events)["reply"] == {"kind": "off_limits"}
    assert llm.chat_calls == []


def test_a_model_alert_is_double_checked_before_refusing(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    llm.moderation = "illegal"
    llm.confirm = False
    events = send(client, youth, conversation_id, "maintenant je calcule de tête, le patron me laisse la caisse")
    assert dict(events)["reply"]["kind"] != "off_limits"


def test_a_young_victim_is_oriented_towards_help_not_refused(client, youth, llm):
    conversation_id = open_conversation(client, youth)
    llm.moderation = "victime"
    events = send(client, youth, conversation_id, "je me fais embêter tous les jours par des gens de ma classe")
    names = [name for name, _ in events]
    assert names[:3] == ["start", "safety", "reply"]
    assert dict(events)["reply"] == {"kind": "victim"}
    assert {item["contact"] for item in dict(events)["safety"]["resources"]} >= {"119", "116006", "17"}
    reply = events[-1][1]["assistant_message"]["content"]
    assert "ce n'est pas de ta faute" in reply and "116 006" in reply
    assert llm.chat_calls == []

    llm.moderation = "ok"
    thanks = send(client, youth, conversation_id, "merci")
    assert dict(thanks)["reply"] == {"kind": "sensitive"}
    assert llm.chat_calls == []
    reloaded = client.get(f"/api/conversations/{conversation_id}", headers=youth).get_json()
    assert reloaded["safety"]["resources"][0]["contact"] == "119"


def test_a_short_yes_after_a_revealed_talent_is_celebrated(client, youth, llm, store):
    llm.reveal = {"citation": "règle aussi les freins", "savoir_faire": "entretenir un vélo"}
    conversation_id = open_conversation(client, youth)
    for text in REVEAL_TURNS:
        send(client, youth, conversation_id, text)
    stored = next(iter(store.objects.values()))
    assert stored["messages"][-1]["flags"] == ["revelation"]
    events = send(client, youth, conversation_id, "ouais grave")
    assert dict(events)["reply"] == {"kind": "reveal_answer"}
    assert "carte" in events[-1][1]["assistant_message"]["content"]

"""Vérifie le contenu réellement livré : cohérence, sources et garde-fous.

Les textes du jeune sont lus exactement comme dans le chat (app/services/guardrails.py, termes
de prompts/garde_fous.json), avec en plus le vocabulaire interdit côté jeune.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from app.game.catalog import Catalog
# Les fonctions du garde-fou du chat elles-mêmes : le lint ne lit jamais un texte autrement.
from app.services.guardrails import Guardrails, _compile, _searchable, fold
from app.services.prompts import PromptLibrary

GUARDRAILS = Path(__file__).resolve().parents[1] / "prompts" / "garde_fous.json"
GAME_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "game"
# Écrans de la psychologue : ils nomment ce que le jeune ne voit jamais (QI, MBTI, santé…).
PSY_FRONT = GAME_FRONT / "backoffice"
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


def strings(value, where: str):
    """Chaque texte d'une valeur JSON avec son chemin : un champ ajouté plus tard est relu d'office."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            name = child.get("id", index) if isinstance(child, dict) else index
            yield from strings(child, f"{where}[{name}]")


def youth_fields(entry: dict) -> dict:
    """Champs youth… d'un curseur ou d'un groupe de curseurs : le reste est pour la psychologue."""
    return {key: value for key, value in entry.items() if key.startswith("youth")}


def youth_texts(catalog: Catalog):
    """Tout le contenu que reçoit le jeune : parties, libellés de ses détails, curseurs, clans, fiche."""
    for instrument in catalog.instruments.values():
        name = instrument["id"]
        yield from strings(catalog.public_instrument(instrument), name)
        for item in instrument.get("items", []):
            if "fact_label" in item:
                yield f"{name}.items[{item['id']}].fact_label", item["fact_label"]
    for group in catalog.trait_groups:
        yield from strings(youth_fields(group), f"groupe {group['id']}")
    for trait in catalog.traits.values():
        yield from strings(youth_fields(trait), f"curseur {trait['id']}")
    yield from strings(catalog.clans, "clans")
    yield from strings(catalog.sheet, "fiche")


# Lecture d'un fichier TypeScript : seules les chaînes comptent, mais il faut sauter les
# commentaires et les /expressions régulières/ pour ne pas lire l'apostrophe de /'/g comme le début
# d'une chaîne. Un / ouvre une expression régulière après un opérateur, une ouvrante, => ou un mot
# comme return ; après un nom, un nombre ou une fermante, c'est une division. Un gabarit `…` donne
# son texte, chaque ${…} remplacé par « ${…} », et son expression est relue comme du code : ses
# chaînes et ses gabarits imbriqués sont contrôlés à part.
TS_ESCAPE = re.compile(r"\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.S)
TS_CONTROL = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
TS_WORD = re.compile(r"[A-Za-z0-9_$]+")
TS_REGEX_AFTER_WORD = {
    "return", "typeof", "case", "in", "of", "void", "delete", "throw", "new", "yield", "await",
    "else", "do", "instanceof",
}
TS_HOLE = "${…}"


def _unescape(match: re.Match) -> str:
    code = match[1]
    return TS_CONTROL.get(code, code) if len(code) == 1 else chr(int(code.strip("ux{}"), 16))


def _quoted_end(source: str, i: int) -> int:
    """Position du guillemet fermant (ou de la fin de ligne) d'une chaîne qui commence en i."""
    quote, j = source[i], i + 1
    while j < len(source) and source[j] not in (quote, "\n"):
        j += 2 if source[j] == "\\" else 1
    return min(j, len(source))


def _regex_end(source: str, i: int) -> int:
    """Position juste après /…/drapeaux, en tenant compte des classes [...]."""
    j, in_class = i + 1, False
    while j < len(source) and source[j] != "\n":
        char = source[j]
        if char == "\\":
            j += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            j += 1
            while j < len(source) and source[j].isalpha():
                j += 1
            return j
        j += 1
    return j


def _template(source: str, i: int, found: list) -> int:
    """Lit `…` à partir du backtick ouvrant ; renvoie la position qui suit le backtick fermant."""
    j, start, parts = i + 1, i + 1, []
    while j < len(source):
        if source[j] == "\\":
            j += 2
            continue
        if source[j] == "`":
            break
        if source.startswith("${", j):
            parts.append(source[start:j])
            j = _code(source, j + 2, found, in_hole=True) + 1
            start = j
            continue
        j += 1
    parts.append(source[start:j])
    found.append((i, TS_HOLE.join(parts)))
    return j + 1


def _code(source: str, i: int, found: list, in_hole: bool = False) -> int:
    """Lit du code à partir de i, jusqu'à la fin ou jusqu'à l'accolade qui ferme un ${…}."""
    depth, regex_allowed = 0, True
    while i < len(source):
        char = source[i]
        if source.startswith("//", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = len(source) if end < 0 else end + 2
        elif char in "'\"":
            end = _quoted_end(source, i)
            found.append((i, source[i + 1 : end]))
            i, regex_allowed = end + 1, False
        elif char == "`":
            i, regex_allowed = _template(source, i, found), False
        elif char == "/" and regex_allowed:
            i, regex_allowed = _regex_end(source, i), False
        elif char.isspace():
            i += 1
        elif TS_WORD.match(source, i):
            word = TS_WORD.match(source, i)
            i, regex_allowed = word.end(), word[0] in TS_REGEX_AFTER_WORD
        else:
            if char == "{":
                depth += 1
            elif char == "}":
                if in_hole and depth == 0:
                    return i
                depth -= 1
            i, regex_allowed = i + 1, char not in ")]"
    return i


def string_literals(source: str) -> list[tuple[int, str]]:
    """Chaînes d'un fichier TypeScript, échappements décodés, avec leur numéro de ligne."""
    found: list[tuple[int, str]] = []
    _code(source, 0, found)
    return [
        (source.count("\n", 0, start) + 1, TS_ESCAPE.sub(_unescape, text))
        for start, text in sorted(found)
    ]


def front_youth_texts() -> list[tuple[str, str]]:
    """Textes des fichiers *.fr.ts du jeu, hors écrans de la psychologue."""
    return [
        (f"{path.relative_to(GAME_FRONT).as_posix()}:{line}", text)
        for path in sorted(GAME_FRONT.rglob("*.fr.ts"))
        if PSY_FRONT not in path.parents
        for line, text in string_literals(path.read_text(encoding="utf-8"))
    ]


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def test_youth_facing_text_respects_guardrails(catalog):
    texts = list(youth_texts(catalog))
    problems = guardrail_problems(texts)
    # Même convention que l'interface : apostrophe typographique dans tout ce que lit le jeune.
    problems += [f"{where} [apostrophe droite] {text}" for where, text in texts if "'" in text]
    assert not problems, "\n".join(problems)


def test_lint_reads_every_field_sent_to_the_youth(catalog):
    stroop = copy.deepcopy(catalog.instruments["stroop"])
    stroop["performance"]["tips"] = [{"text": "Demande à tes parents"}]
    assert guardrail_problems(strings(catalog.public_instrument(stroop), "stroop")) == [
        "stroop.performance.tips[0].text [famille : parents] Demande à tes parents"
    ]
    paths = [where for where, _ in youth_texts(catalog)]
    for field in (
        ".prompt", ".hint", ".placeholder", ".options[", ".scale.labels[", ".chapters[", ".outro",
        ".source_note", ".performance.", ".fact_label", ".youth.", ".youth_label", "clans[",
        "fiche.attributes[", "fiche.level_titles[", "fiche.badges[",
    ):
        assert any(field in path for path in paths), field


def test_front_youth_texts_respect_guardrails():
    texts = front_youth_texts()
    files = {where.split(":")[0] for where, _ in texts}
    assert len(files) >= 5 and len(texts) > 300, "textes du front introuvables"
    problems = guardrail_problems(texts)
    # Convention de l'interface : apostrophe typographique, hors expressions ${…} des gabarits.
    problems += [
        f"{where} [apostrophe droite] {text}"
        for where, text in texts
        if "'" in re.sub(r"\$\{[^}]*\}", "", text)
    ]
    assert not problems, "\n".join(problems)


def test_string_literals_skip_comments_and_regular_expressions():
    source = "\n".join([
        "/** Textes de l'écran. */",
        "// l'autre commentaire, 'pas une chaîne'",
        "export const fr = {",
        "  a: 'C’est \\u00e0 toi\\u00a0!',",
        '  b: "Entre \\"guillemets\\"",',
        "  c: (n: number) => `${n} ${plural(n, 'jeu', 'jeux')}`,",
        "  d: (text: string) => text.replace(/'/g, '’'),",
        "  e: (ms: number) => ms / 1000 / 60,",
        "};",
    ])
    assert string_literals(source) == [
        (4, "C’est à toi\u00a0!"),
        (5, 'Entre "guillemets"'),
        (6, "${…} ${…}"),
        (6, "jeu"),
        (6, "jeux"),
        (7, "’"),
    ]


def test_string_literals_read_nested_templates_and_regexes_after_arrows():
    source = "\n".join([
        "export const fr = {",
        "  a: (n: number) => `${n > 1 ? `Tes parents sont fiers` : `Bravo`} !`,",
        "  b: (v: number | null) => `${v === null ? 'À découvrir' : `${v} sur 20`} pour toi`,",
        "  c: (c: string) => /'/.test(c) ? 'Tes parents' : 'ok',",
        "  d(c: string) { return /'/.test(c) ? 'Ta sœur' : `${{ a: 1 }.a}`; },",
        "};",
    ])
    assert string_literals(source) == [
        (2, "${…} !"),
        (2, "Tes parents sont fiers"),
        (2, "Bravo"),
        (3, "${…} pour toi"),
        (3, "À découvrir"),
        (3, "${…} sur 20"),
        (4, "Tes parents"),
        (4, "ok"),
        (5, "Ta sœur"),
        (5, "${…}"),
    ]
    problems = guardrail_problems((f"fr.ts:{line}", text) for line, text in string_literals(source))
    assert [problem.split(" ")[1] for problem in problems] == ["[famille", "[famille", "[famille"]


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
    # Test validé, ou sa traduction maison : chaque item cite son original.
    checked = [i for i in catalog.instruments.values() if i["tier"] in {"validated", "translated"}]
    assert checked, "aucun instrument issu d'un test validé : ce test ne vérifierait rien"
    for instrument in checked:
        for item in instrument["items"]:
            source = item.get("source") or {}
            assert source.get("ref") and source.get("original"), f"{instrument['id']}/{item['id']}"

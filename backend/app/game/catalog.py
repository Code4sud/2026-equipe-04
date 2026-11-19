"""Charge et vérifie le contenu du jeu (fichiers JSON de app/game/content/)."""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent / "content"

KINDS = {"quiz", "questionnaire", "performance"}
TIERS = {"validated", "translated", "adapted", "custom", "performance"}
# Solidité de la preuve : un signal peut afficher un niveau plus faible que son instrument, jamais
# plus fort (sinon une question maison pourrait se dire « Test validé »).
TIER_STRENGTH = {"validated": 3, "performance": 3, "translated": 2, "adapted": 1, "custom": 0}
ITEM_TYPES = {"likert", "choice", "text"}
PUBLIC_ITEM_FIELDS = (
    "id", "type", "chapter", "prompt", "hint", "illustration",
    "max_choices", "allow_text", "placeholder", "scale",
)
PUBLIC_OPTION_FIELDS = ("id", "label", "emoji", "color")
PUBLIC_INSTRUMENT_FIELDS = (
    "id", "version", "kind", "title", "tagline", "icon", "duration_min", "xp", "intro", "outro",
    "source_note", "scale", "chapters", "min_answers",
)
# Clé d'un détail de la fiche (couleur_preferee...) : elle arrive aussi dans l'URL de correction.
FACT_KEY = re.compile(r"[a-z][a-z0-9_]{0,59}")


class ContentError(ValueError):
    """Le contenu du jeu est incohérent : l'application refuse de démarrer avec."""


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContentError(f"{path}: {error}") from error


def _files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


class Catalog:
    """`overlays` ajoute des dossiers de contenu, pour les tests et le serveur de dev."""

    def __init__(self, content_dir: Path | str = DEFAULT_CONTENT_DIR, overlays=(), overlays_win=True):
        root = Path(content_dir)
        self.trait_groups: list[dict] = []
        self.traits: dict[str, dict] = {}
        for path in _files(root / "traits"):
            data = _read(path)
            group = data["group"]
            self.trait_groups.append({**group, "trait_ids": [t["id"] for t in data["traits"]]})
            for trait in data["traits"]:
                if trait["id"] in self.traits:
                    raise ContentError(f"Curseur en double : {trait['id']}")
                self.traits[trait["id"]] = {**trait, "group": group["id"]}
        self.trait_groups.sort(key=lambda group: group.get("order", 100))

        self.skill_signals: dict[str, list[dict]] = _read(root / "skill_signals.json")
        self.clans: list[dict] = _read(root / "clans.json")["clans"]
        self.sheet: dict = _read(root / "sheet.json")

        roots = [*overlays, root] if not overlays_win else [root, *overlays]
        self.sources: dict[str, dict] = {}
        self.instruments: dict[str, dict] = {}
        for folder in map(Path, roots):
            for path in _files(folder / "sources"):
                for source in _read(path)["sources"]:
                    self.sources[source["id"]] = source
            for path in _files(folder / "instruments"):
                instrument = _read(path)
                self.instruments[instrument["id"]] = instrument
        self.validate()

    def ordered_instruments(self) -> list[dict]:
        return sorted(self.instruments.values(), key=lambda i: (i.get("order", 100), i["id"]))

    def item(self, instrument: dict, item_id: str) -> dict | None:
        return next((item for item in instrument.get("items", []) if item["id"] == item_id), None)

    def validate(self) -> None:
        for category, signals in self.skill_signals.items():
            self._check_signals(signals, f"talents/{category}")
        for clan in self.clans:
            self._check_trait(clan["trait"], f"clan {clan['id']}")
        for attribute in self.sheet["attributes"]:
            for part in attribute["traits"]:
                self._check_trait(part["trait"], f"attribut {attribute['id']}")
        for instrument in self.instruments.values():
            self._check_instrument(instrument)

    def _check_trait(self, trait_id: str, where: str) -> None:
        if trait_id not in self.traits:
            raise ContentError(f"{where} : curseur inconnu « {trait_id} »")

    def _check_signals(self, signals: list[dict], where: str, ceiling: str | None = None) -> None:
        for signal in signals:
            self._check_trait(signal["trait"], where)
            if not 0 <= signal["value"] <= 100:
                raise ContentError(f"{where} : valeur hors de 0-100")
            self._check_signal_tier(signal, where, ceiling)

    def _check_signal_tier(self, signal: dict, where: str, ceiling: str | None) -> None:
        """Un signal peut porter son propre niveau de preuve, qui remplace celui de l'instrument
        (`ceiling`) à condition d'être moins solide ou aussi solide que lui."""
        if "tier" not in signal:
            return
        tier = signal["tier"]
        if tier not in TIERS:
            raise ContentError(f"{where} : niveau de preuve inconnu « {tier} »")
        if ceiling is not None and TIER_STRENGTH[tier] > TIER_STRENGTH[ceiling]:
            raise ContentError(
                f"{where} : niveau « {tier} » plus solide que celui de l'instrument (« {ceiling} »)"
            )

    def _check_source(self, source_id: str, where: str) -> None:
        if source_id not in self.sources:
            raise ContentError(f"{where} : source inconnue « {source_id} »")

    def _check_instrument(self, instrument: dict) -> None:
        name = instrument["id"]
        if instrument["kind"] not in KINDS:
            raise ContentError(f"{name} : kind invalide")
        if instrument["tier"] not in TIERS:
            raise ContentError(f"{name} : tier invalide")
        for field in ("title", "tagline", "icon", "duration_min", "xp", "version"):
            if field not in instrument:
                raise ContentError(f"{name} : champ manquant « {field} »")
        source_ids = instrument.get("source_ids", [])
        if instrument["tier"] != "custom" and not source_ids:
            raise ContentError(f"{name} : source_ids obligatoire pour ce niveau de preuve")
        for source_id in source_ids:
            self._check_source(source_id, name)

        if instrument["kind"] == "performance":
            from .performance import SCORERS

            settings = instrument.get("performance", {})
            if settings.get("scorer") not in SCORERS:
                raise ContentError(f"{name} : scorer inconnu")
            self._check_trait(settings.get("trait", ""), name)
            return

        items = instrument.get("items", [])
        if not items:
            raise ContentError(f"{name} : aucune question")
        chapters = {chapter["id"] for chapter in instrument.get("chapters", [])}
        seen: set[str] = set()
        for item in items:
            where = f"{name}/{item['id']}"
            if item["id"] in seen:
                raise ContentError(f"{where} : identifiant en double")
            seen.add(item["id"])
            if item["type"] not in ITEM_TYPES:
                raise ContentError(f"{where} : type invalide")
            if item.get("chapter") and item["chapter"] not in chapters:
                raise ContentError(f"{where} : chapitre inconnu")
            if item.get("source"):
                self._check_source(item["source"]["source_id"], where)
            if "fact" in item and "fact_label" not in item:
                raise ContentError(f"{where} : fact_label manquant")
            if "fact" in item and not FACT_KEY.fullmatch(str(item["fact"])):
                raise ContentError(f"{where} : clé de détail invalide (minuscules, chiffres, _)")
            if item["type"] == "likert":
                if "scale" not in item and "scale" not in instrument:
                    raise ContentError(f"{where} : échelle manquante")
                for part in likert_parts(item):
                    self._check_trait(part["trait"], where)
                    if part.get("keyed", "+") not in {"+", "-"}:
                        raise ContentError(f"{where} : keyed invalide")
                    self._check_signal_tier(part, where, instrument["tier"])
            elif item["type"] == "choice":
                options = item.get("options", [])
                if len(options) < 2 or len({o["id"] for o in options}) != len(options):
                    raise ContentError(f"{where} : options invalides")
                for option in options:
                    self._check_signals(option.get("signals", []), where, instrument["tier"])
            elif "fact" not in item:
                raise ContentError(f"{where} : une question libre alimente forcément un détail")

    def public_instrument(self, instrument: dict) -> dict:
        """Ce que voit le jeune : jamais les clés de cotation ni les curseurs visés."""
        public = {k: instrument[k] for k in PUBLIC_INSTRUMENT_FIELDS if k in instrument}
        if instrument["kind"] == "performance":
            settings = instrument["performance"]
            public["performance"] = {k: v for k, v in settings.items() if k not in {"trait", "weight"}}
            return public
        public["items"] = [
            {
                **{k: item[k] for k in PUBLIC_ITEM_FIELDS if k in item},
                **(
                    {"options": [
                        {k: o[k] for k in PUBLIC_OPTION_FIELDS if k in o} for o in item["options"]
                    ]}
                    if "options" in item
                    else {}
                ),
            }
            for item in instrument["items"]
        ]
        return public


def likert_parts(item: dict) -> list[dict]:
    """Une question Likert alimente un curseur (`trait`) ou plusieurs (`traits`)."""
    if "traits" in item:
        return item["traits"]
    if "trait" in item:
        part = {"trait": item["trait"], "keyed": item.get("keyed", "+"), "weight": item.get("weight", 1)}
        if "tier" in item:
            part["tier"] = item["tier"]
        return [part]
    return []

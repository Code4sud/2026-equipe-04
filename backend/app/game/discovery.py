"""Quel jeu peut révéler un attribut encore inconnu de la fiche du jeune."""
from __future__ import annotations

from .catalog import Catalog, likert_parts


def instrument_traits(instrument: dict) -> set[str]:
    """Curseurs qu'un instrument peut nourrir, d'après son contenu."""
    if instrument["kind"] == "performance":
        settings = instrument.get("performance", {})
        traits = {settings["trait"]} if settings.get("trait") else set()
        return traits | {part["trait"] for part in settings.get("traits", [])}
    traits: set[str] = set()
    for item in instrument.get("items", []):
        traits.update(part["trait"] for part in likert_parts(item))
        for option in item.get("options", []):
            traits.update(row["trait"] for row in option.get("signals", []))
    return traits


def reveal_with(catalog: Catalog, trait_ids: set[str], completed: set[str]) -> dict | None:
    """Premier jeu, dans l'ordre du catalogue, qui nourrit l'un de ces curseurs et reste jouable.

    Un jeu pas encore terminé passe avant un jeu terminé qu'on peut rejouer.
    """
    replay = None
    for instrument in catalog.ordered_instruments():
        if not trait_ids & instrument_traits(instrument):
            continue
        done = instrument["id"] in completed
        if done and not instrument.get("replayable", True):
            continue
        hint = {"id": instrument["id"], "title": instrument["title"], "kind": instrument["kind"]}
        if not done:
            return hint
        replay = replay or hint
    return replay

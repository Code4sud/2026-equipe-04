"""Fiche d'aventurier : badges et titres de niveau."""
from __future__ import annotations

import unicodedata

from app.game.catalog import KINDS, Catalog

BADGE_RULES = {"completed", "completed_count", "talents", "facts", "level"}


def test_every_badge_can_be_earned():
    catalog = Catalog()
    for badge in catalog.sheet["badges"]:
        rule = badge["rule"]
        assert rule["type"] in BADGE_RULES, badge["id"]
        if rule["type"] == "completed_count" and "kind" in rule:
            assert rule["kind"] in KINDS, badge["id"]
        if rule["type"] != "completed":
            assert rule["count"] >= 1, badge["id"]


def test_level_titles_are_unique_and_never_a_clan_name():
    def plain(text: str) -> str:
        text = unicodedata.normalize("NFKD", text).lower()
        return "".join(c for c in text if c.isalpha())

    catalog = Catalog()
    titles = [plain(title) for title in catalog.sheet["level_titles"]]
    assert len(set(titles)) == len(titles)
    clan_roots = {plain(clan["name"].split()[-1])[:-2] for clan in catalog.clans}
    assert not [t for t in titles for root in clan_roots if root in t]

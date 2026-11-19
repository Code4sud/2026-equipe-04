"""Ce que le backoffice psychologue lit en plus du contrat de base du jeu."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.game.catalog import Catalog

FIXTURES = Path(__file__).parent / "fixtures" / "game"


@pytest.fixture(autouse=True)
def fixture_catalog(app):
    catalog = Catalog(overlays=[FIXTURES])
    keep = {"onboarding", "fixture_questionnaire", "fixture_span"}
    catalog.instruments = {k: v for k, v in catalog.instruments.items() if k in keep}
    app.extensions["game_catalog"] = catalog


def test_instrument_info_gives_chapter_titles(client, psychologist):
    response = client.get("/api/backoffice/game/catalog", headers=psychologist)
    assert response.status_code == 200
    instruments = {item["id"]: item for item in response.get_json()["instruments"]}
    assert instruments["onboarding"]["chapters"] == [
        {"id": "matin", "title": "Le matin"},
        {"id": "soir", "title": "Le soir"},
    ]
    assert instruments["fixture_span"]["chapters"] == []


def test_catalog_is_reserved_to_staff(client, youth):
    assert client.get("/api/backoffice/game/catalog", headers=youth).status_code == 403

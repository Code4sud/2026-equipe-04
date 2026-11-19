from __future__ import annotations

from flask import request

from ..errors import ApiError


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Le corps de la requête doit être un objet JSON.")
    return data


def text_field(data: dict, name: str, label: str, minimum: int = 1, maximum: int = 255) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise ApiError(400, "invalid_field", f"{label} est requis.")
    # PostgreSQL refuse le caractère NUL dans un texte : on l'arrête avant la base.
    if "\x00" in value:
        raise ApiError(400, "invalid_field", f"{label} contient un caractère non autorisé.")
    value = value.strip()
    if len(value) < minimum:
        raise ApiError(400, "invalid_field", f"{label} est trop court.")
    if len(value) > maximum:
        raise ApiError(400, "invalid_field", f"{label} est trop long.")
    return value

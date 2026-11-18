from flask import current_app


def service(name: str):
    """Accès aux services créés dans create_app (remplaçables dans les tests)."""
    return current_app.extensions[name]

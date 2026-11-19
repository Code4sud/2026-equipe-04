"""Historique des modifications du jeune, pour la psychologue seulement.

Le jeune accepte à l'inscription que la psychologue voie ses réponses et ce qu'il en fait :
chaque détail corrigé, masqué ou remontré, chaque verdict donné, changé ou retiré, chaque
réponse modifiée ou retirée est gardé ici pour qu'elle puisse lui en parler. Rien de ceci
n'est renvoyé au jeune.

`subject` désigne ce qui a changé : « fact:<clé> », « trait:<curseur> » ou
« answer:<partie>/<question> ». `before` et `after` gardent l'état avant et après.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from ..extensions import db
from ..models import GameEvent, utcnow

FACT_EDITED = "fact_edited"
FACT_HIDDEN = "fact_hidden"
FACT_SHOWN = "fact_shown"
VERDICT_SET = "verdict_set"
VERDICT_CHANGED = "verdict_changed"
VERDICT_WITHDRAWN = "verdict_withdrawn"
ANSWER_CHANGED = "answer_changed"
ANSWER_RETRACTED = "answer_retracted"
KINDS = (
    FACT_EDITED,
    FACT_HIDDEN,
    FACT_SHOWN,
    VERDICT_SET,
    VERDICT_CHANGED,
    VERDICT_WITHDRAWN,
    ANSWER_CHANGED,
    ANSWER_RETRACTED,
)
PSY_LIMIT = 200


def fact_subject(key: str) -> str:
    return f"fact:{key}"


def trait_subject(trait_id: str) -> str:
    return f"trait:{trait_id}"


def answer_subject(run_id: uuid.UUID, item_id: str) -> str:
    return f"answer:{run_id}/{item_id}"


def parse_subject(subject: str) -> tuple[str, str]:
    """« fact:passion » donne (« fact », « passion »)."""
    kind, _, ref = subject.partition(":")
    return kind, ref


def log(youth_id: uuid.UUID, kind: str, subject: str, before: dict | None, after: dict | None) -> None:
    """Ajoute l'événement à la transaction en cours : il n'existe que si la modification est validée."""
    if kind not in KINDS:
        raise ValueError(f"Événement inconnu : {kind}")
    db.session.add(
        GameEvent(
            youth_id=youth_id,
            kind=kind,
            subject=subject,
            before=before,
            after=after,
            created_at=utcnow(),
        )
    )


def recent(youth_id: uuid.UUID, limit: int = PSY_LIMIT) -> list[GameEvent]:
    """Les derniers événements, du plus récent au plus ancien."""
    return list(
        db.session.scalars(
            select(GameEvent)
            .where(GameEvent.youth_id == youth_id)
            .order_by(GameEvent.created_at.desc(), GameEvent.id.desc())
            .limit(limit)
        )
    )

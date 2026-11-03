"""
Calificación de los retos con estrellas.

El jugador califica un reto después de resolverlo. El promedio solo lo ven
profesores y admin: mostrarlo a los estudiantes influiría en sus votos. Los
retos personales (`owner_id`) no entran en el resumen: los ve una sola persona.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.models.rating import ChallengeRating
from app.models.submission import Solve
from app.models.user import User

MIN_STARS = 1
MAX_STARS = 5


def rate(db: DbSession, user: User, challenge_id: str, raw_stars) -> dict:
    """Guarda la nota del jugador; calificar otra vez reemplaza la anterior."""
    # bool es un int en Python: sin esta revisión, True valdría 1 estrella.
    if isinstance(raw_stars, bool) or not isinstance(raw_stars, int) or not MIN_STARS <= raw_stars <= MAX_STARS:
        return {"ok": False, "status": 400, "error": "Elige de 1 a 5 estrellas."}
    if db.get(Solve, (user.id, challenge_id)) is None:
        return {"ok": False, "status": 403, "error": "Resuelve el reto para poder calificarlo."}
    rating = db.get(ChallengeRating, (user.id, challenge_id))
    if rating is None:
        db.add(ChallengeRating(user_id=user.id, challenge_id=challenge_id, stars=raw_stars))
    else:
        rating.stars = raw_stars
    db.commit()
    return {"ok": True, "challengeId": challenge_id, "stars": raw_stars}


def ratings_of_player(db: DbSession, user_id: int) -> dict[str, int]:
    rows = db.execute(
        select(ChallengeRating.challenge_id, ChallengeRating.stars).where(ChallengeRating.user_id == user_id)
    )
    return {challenge_id: stars for challenge_id, stars in rows}


def summary(db: DbSession) -> list[dict]:
    """Promedio y votos por reto, de mejor a peor calificado."""
    average = func.avg(ChallengeRating.stars)
    votes = func.count(ChallengeRating.user_id)
    rows = db.execute(
        select(Challenge.id, Challenge.title, Challenge.category, average, votes)
        .join(ChallengeRating, ChallengeRating.challenge_id == Challenge.id)
        .where(Challenge.owner_id.is_(None))
        .group_by(Challenge.id, Challenge.title, Challenge.category)
        .order_by(average.desc(), votes.desc(), Challenge.title)
    )
    return [
        {"id": row[0], "title": row[1], "category": row[2], "average": round(float(row[3]), 1), "votes": row[4]}
        for row in rows
    ]

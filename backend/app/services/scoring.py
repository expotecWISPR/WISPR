"""
Envíos de flags, puntos, racha y ranking.

Migrado 1:1 de `wispr_terminal_professional/server.js`:
  - `submit_flag`     ← `verifySubmission` + `recordSubmission`
  - `current_streak`  ← `currentStreak`
  - `player_progress` ← las llaves solved/attempts/submissions de `publicPlayer`
  - `ranking`         ← la ruta `GET /api/ranking`

Las respuestas conservan la forma exacta del prototipo (llaves en
camelCase, tiempos en milisegundos desde 1970 como `Date.now()`) porque el
frontend terminado las lee tal cual.

Diferencia a propósito con el prototipo: al resolver un reto, el prototipo
generaba en ese momento un reto "de continuación" (`createFollowUpChallenge`).
Acá `nextChallenge` se devuelve siempre en `None` por ahora — conectar eso
con el pipeline de IA (`ai_advisor.py`) es un paso aparte; la llave se deja
para no romper al frontend.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import as_utc
from app.models.challenge import Challenge
from app.models.submission import Solve, Submission
from app.models.user import User
from app.services import flag_validator

CHALLENGE_NOT_FOUND = "El reto no existe o ya no está disponible."
# El prototipo guardaba solo los últimos 100 envíos por jugador, así que la
# racha nunca pasaba de 100. Se mantiene el tope para que el número sea el
# mismo y la consulta quede acotada.
STREAK_WINDOW = 100
RANKING_LIMIT = 100


def _ms(value) -> int:
    return int(as_utc(value).timestamp() * 1000)


def submit_flag(db: DbSession, user: User, challenge_id: str, flag: str, source: str = "web") -> dict:
    challenge = db.get(Challenge, str(challenge_id or ""))
    if challenge is None or not challenge.is_active:
        return {"ok": False, "error": CHALLENGE_NOT_FOUND}

    submitted = str(flag or "").strip()
    # Igual que el prototipo: un formato inválido no cuenta como intento.
    if not flag_validator.is_valid_format(submitted):
        return {"ok": False, "error": flag_validator.FORMAT_ERROR, "challengeId": challenge.id}

    correct = flag_validator.check_flag(db, user.id, challenge, submitted)
    db.add(Submission(user_id=user.id, challenge_id=challenge.id, correct=correct, source=source))

    if not correct:
        db.commit()
        return {"ok": False, "challengeId": challenge.id}

    if db.get(Solve, (user.id, challenge.id)) is not None:
        db.commit()
        return {"ok": True, "duplicate": True, "challengeId": challenge.id, "points": challenge.points}

    # Si llegan dos envíos correctos a la vez (dos pestañas, web + terminal),
    # los dos pueden pasar el chequeo de arriba. La clave primaria de `solves`
    # hace que solo uno se inserte; el otro cae en IntegrityError y se trata
    # como duplicado, en vez de sumar los puntos dos veces. El SAVEPOINT
    # (begin_nested) permite deshacer solo el solve y conservar el Submission.
    try:
        with db.begin_nested():
            db.add(Solve(user_id=user.id, challenge_id=challenge.id, points=challenge.points))
    except IntegrityError:
        db.commit()
        return {"ok": True, "duplicate": True, "challengeId": challenge.id, "points": challenge.points}

    db.commit()
    return {
        "ok": True,
        "challengeId": challenge.id,
        "points": challenge.points,
        "nextChallenge": None,
        "generationError": "",
    }


def current_streak(db: DbSession, user_id: int) -> int:
    """Aciertos consecutivos más recientes (se corta en el primer fallo)."""
    recent = db.scalars(
        select(Submission.correct)
        .where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(STREAK_WINDOW)
    )
    streak = 0
    for correct in recent:
        if not correct:
            break
        streak += 1
    return streak


def player_progress(db: DbSession, user_id: int) -> dict:
    """`solved`, `attempts` y `submissions` con la forma de `publicPlayer()`."""
    solved = {
        solve.challenge_id: {"time": _ms(solve.solved_at), "points": solve.points}
        for solve in db.scalars(select(Solve).where(Solve.user_id == user_id))
    }
    attempts = dict(
        db.execute(
            select(Submission.challenge_id, func.count())
            .where(Submission.user_id == user_id)
            .group_by(Submission.challenge_id)
        ).all()
    )
    recent = db.execute(
        select(Submission, Challenge.title)
        .join(Challenge, Challenge.id == Submission.challenge_id)
        .where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(50)
    ).all()
    submissions = [
        {"id": sub.challenge_id, "title": title, "ok": sub.correct, "time": _ms(sub.created_at), "source": sub.source}
        for sub, title in recent
    ]
    return {"solved": solved, "attempts": attempts, "submissions": submissions}


def ranking(db: DbSession, current_user_id: int | None) -> list[dict]:
    """
    Solo estudiantes, máximo 100, SIN ids ni correos (contrato de
    BACKEND-PENDIENTE.md). Orden: puntaje, luego cantidad de retos
    resueltos, luego nombre.
    """
    totals = (
        select(
            Solve.user_id,
            func.coalesce(func.sum(Solve.points), 0).label("score"),
            func.count().label("solves"),
        )
        .group_by(Solve.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User, totals.c.score, totals.c.solves)
        .outerjoin(totals, totals.c.user_id == User.id)
        .where(User.role == "estudiante")
    ).all()

    entries = [
        {
            "name": user.full_name,
            "handle": user.username,
            "score": int(score or 0),
            "solves": int(solves or 0),
            "streak": current_streak(db, user.id),
            "current": user.id == current_user_id,
        }
        for user, score, solves in rows
    ]
    entries.sort(key=lambda e: (-e["score"], -e["solves"], e["name"].casefold()))
    return entries[:RANKING_LIMIT]

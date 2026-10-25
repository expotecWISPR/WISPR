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

Al resolver un reto, igual que `createFollowUpChallenge` del prototipo, la
respuesta trae `nextChallenge`: el siguiente reto según el motor adaptativo
(difficulty.py), que puede ser uno nuevo con historia de la IA. El frontend
ya lo agrega a la cola del jugador.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import as_utc
from app.models.challenge import Challenge
from app.models.submission import Solve, Submission
from app.models.user import User
from app.services import bonus, challenges, difficulty, flag_validator, hints

log = logging.getLogger(__name__)

CHALLENGE_NOT_FOUND = "El reto no existe o ya no está disponible."
NEXT_FAILED = "Resolviste el reto, pero no se pudo preparar el siguiente. Intenta de nuevo más tarde."
TEMPLATE_STORY = "La historia de este reto es de plantilla: la IA no estaba disponible."
# El prototipo guardaba solo los últimos 100 envíos por jugador, así que la
# racha nunca pasaba de 100. Se mantiene el tope para que el número sea el
# mismo y la consulta quede acotada.
STREAK_WINDOW = 100
RANKING_LIMIT = 100


def _ms(value) -> int:
    return int(as_utc(value).timestamp() * 1000)


def _next_challenge(db: DbSession, user: User, solved: Challenge) -> dict:
    """
    Las llaves `nextChallenge`/`generationError` de la respuesta. El acierto
    ya quedó guardado: si esto falla, el jugador igual tiene sus puntos.
    """
    try:
        recommended, reason, ai_error = difficulty.next_challenge(db, user, solved)
    except Exception:
        log.exception("No se pudo preparar el siguiente reto de %s", solved.id)
        db.rollback()
        return {"nextChallenge": None, "generationError": NEXT_FAILED}
    if recommended is None:
        return {"nextChallenge": None, "generationError": ""}
    return {
        "nextChallenge": {**challenges.public_challenge(recommended), "reason": reason},
        "generationError": TEMPLATE_STORY if ai_error else "",
    }


def submit_flag(db: DbSession, user: User, challenge_id: str, flag: str, source: str = "web") -> dict:
    challenge = challenges.get_active(db, challenge_id, user.id)
    if challenge is None:
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

    existing = db.get(Solve, (user.id, challenge.id))
    if existing is not None:
        db.commit()
        return {"ok": True, "duplicate": True, "challengeId": challenge.id, "points": existing.points,
                "breakdown": existing.breakdown}

    # Pistas, intentos fallidos, velocidad y racha limpia (app/services/bonus.py).
    # Se calcula antes de crear el Solve: la racha mira los aciertos anteriores.
    detail = bonus.breakdown(db, user.id, challenge)
    points = detail["total"]

    # Si llegan dos envíos correctos a la vez (dos pestañas, web + terminal),
    # los dos pueden pasar el chequeo de arriba. La clave primaria de `solves`
    # hace que solo uno se inserte; el otro cae en IntegrityError y se trata
    # como duplicado, en vez de sumar los puntos dos veces. El SAVEPOINT
    # (begin_nested) permite deshacer solo el solve y conservar el Submission.
    try:
        with db.begin_nested():
            db.add(Solve(user_id=user.id, challenge_id=challenge.id, points=points,
                         clean=detail["clean"], breakdown=detail))
    except IntegrityError:
        db.commit()
        winner = db.get(Solve, (user.id, challenge.id))
        return {"ok": True, "duplicate": True, "challengeId": challenge.id,
                "points": winner.points if winner else points, "breakdown": winner.breakdown if winner else detail}

    db.commit()
    return {
        "ok": True,
        "challengeId": challenge.id,
        "points": points,
        "breakdown": detail,
        "cleanStreak": bonus.clean_streak(db, user.id),
        **_next_challenge(db, user, challenge),
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
    """`solved`, `attempts`, `submissions` y `hints` con la forma de `publicPlayer()`."""
    solved = {
        solve.challenge_id: {"time": _ms(solve.solved_at), "points": solve.points, "breakdown": solve.breakdown}
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
    # Pistas abiertas por reto, con la forma de `app.hints` del frontend; la
    # racha limpia y los cronómetros alimentan el panel de puntos del reto.
    return {"solved": solved, "attempts": attempts, "submissions": submissions,
            "hints": hints.unlocked_by_challenge(db, user_id),
            "cleanStreak": bonus.clean_streak(db, user_id),
            "timers": bonus.timers_by_challenge(db, user_id)}


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
            "avatar": user.avatar,
            "score": int(score or 0),
            "solves": int(solves or 0),
            "streak": current_streak(db, user.id),
            "current": user.id == current_user_id,
        }
        for user, score, solves in rows
    ]
    entries.sort(key=lambda e: (-e["score"], -e["solves"], e["name"].casefold()))
    return entries[:RANKING_LIMIT]

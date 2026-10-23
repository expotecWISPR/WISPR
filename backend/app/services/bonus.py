"""
Puntos de un acierto: penalizaciones, bonos y el cronómetro del reto (22 oct).

Una sola regla para la web, la terminal y las pistas. Todos los porcentajes se
aplican sobre los puntos del reto (para un reto de práctica, sobre sus puntos
ya reducidos por challenge_factory.PRACTICE_DECAY):

    Penalizaciones
      cada pista abierta antes de resolver   −15 %
      cada intento fallido                   −5 %   (máximo −25 %)
    Bonos
      resolverlo en menos de 10 minutos      +15 %
      racha limpia                           +5 % por cada reto LIMPIO que ya
                                             llevas seguido (máximo +25 %)

    total = base + suma de cada línea (redondeada), nunca menos de 0

"Limpio" = resuelto sin pistas y sin intentos fallidos. La racha premia la
constancia: el 1.º limpio no tiene bono todavía; si el siguiente también sale
limpio, ese gana +5 %; el siguiente +10 %, y así hasta +25 %. Un acierto que
no es limpio la corta. Los retos de 0 puntos (práctica repetida) no la suman
ni la cortan: si sumaran, se podría inflar la racha con retos sin valor.

El cronómetro empieza la primera vez que el jugador abre el reto
(POST /api/challenges/{id}/start) y lo guarda el servidor. Sin esa hora, no hay
bono de velocidad.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import as_utc
from app.models.challenge import Challenge
from app.models.hint import HintUnlock
from app.models.submission import Solve, Submission
from app.models.timer import ChallengeTimer

HINT_PCT = 15
WRONG_PCT = 5
WRONG_MAX_PCT = 25
SPEED_PCT = 15
SPEED_SECONDS = 10 * 60
STREAK_PCT = 5
STREAK_MAX_PCT = 25
STREAK_WINDOW = 50  # aciertos recientes que se revisan para contar la racha

# Lo que el frontend necesita para mostrar las reglas y estimar en vivo.
RULES = {
    "hintPct": HINT_PCT,
    "wrongPct": WRONG_PCT,
    "wrongMaxPct": WRONG_MAX_PCT,
    "speedPct": SPEED_PCT,
    "speedSeconds": SPEED_SECONDS,
    "streakPct": STREAK_PCT,
    "streakMaxPct": STREAK_MAX_PCT,
}


def to_ms(value: datetime) -> int:
    return int(as_utc(value).timestamp() * 1000)


def now_ms() -> int:
    return to_ms(datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Cronómetro
# ---------------------------------------------------------------------------


def start_timer(db: DbSession, user_id: int, challenge: Challenge) -> datetime:
    """Hora en que el jugador abrió el reto por primera vez (la crea si no existe)."""
    timer = db.get(ChallengeTimer, (user_id, challenge.id))
    if timer is not None:
        return timer.started_at
    try:
        with db.begin_nested():  # dos pestañas a la vez: gana la primera
            db.add(ChallengeTimer(user_id=user_id, challenge_id=challenge.id))
        db.commit()
    except IntegrityError:
        db.commit()
    return db.get(ChallengeTimer, (user_id, challenge.id)).started_at


def timers_by_challenge(db: DbSession, user_id: int | None) -> dict[str, int]:
    """{reto: hora de inicio en ms} de un jugador."""
    if user_id is None:
        return {}
    return {
        challenge_id: to_ms(started)
        for challenge_id, started in db.execute(
            select(ChallengeTimer.challenge_id, ChallengeTimer.started_at).where(ChallengeTimer.user_id == user_id)
        ).all()
    }


# ---------------------------------------------------------------------------
# Racha limpia
# ---------------------------------------------------------------------------


def clean_streak(db: DbSession, user_id: int) -> int:
    """Retos limpios seguidos más recientes (sin contar los de 0 puntos)."""
    streak = 0
    for solve in db.scalars(
        select(Solve).where(Solve.user_id == user_id).order_by(Solve.solved_at.desc()).limit(STREAK_WINDOW)
    ):
        base = (solve.breakdown or {}).get("base", solve.points)
        if not base:
            continue  # práctica sin puntos: ni suma ni corta
        if not solve.clean:
            break
        streak += 1
    return streak


# ---------------------------------------------------------------------------
# Desglose de un acierto
# ---------------------------------------------------------------------------


def _hints_used(db: DbSession, user_id: int, challenge_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(HintUnlock)
        .where(HintUnlock.user_id == user_id, HintUnlock.challenge_id == challenge_id)
    ) or 0


def _wrong_attempts(db: DbSession, user_id: int, challenge_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Submission)
        .where(Submission.user_id == user_id, Submission.challenge_id == challenge_id, Submission.correct.is_(False))
    ) or 0


def _line(base: int, count: int, pct: int) -> dict:
    return {"count": count, "pct": pct, "points": round(base * pct / 100)}


def breakdown(db: DbSession, user_id: int, challenge: Challenge, at: datetime | None = None) -> dict:
    """
    Desglose de los puntos que ganaría (o ganó) el jugador si resuelve el reto
    en el instante `at` (por defecto, ahora). Se llama ANTES de crear el Solve.
    """
    at = as_utc(at or datetime.now(timezone.utc))
    base = challenge.points or 0
    hints = _hints_used(db, user_id, challenge.id)
    wrong = _wrong_attempts(db, user_id, challenge.id)
    timer = db.get(ChallengeTimer, (user_id, challenge.id))
    seconds = int((at - as_utc(timer.started_at)).total_seconds()) if timer is not None else None
    fast = seconds is not None and 0 <= seconds < SPEED_SECONDS
    clean = hints == 0 and wrong == 0
    previous_streak = clean_streak(db, user_id) if clean and base else 0

    lines = {
        "hints": _line(base, hints, -HINT_PCT * hints),
        "wrong": _line(base, wrong, -min(WRONG_PCT * wrong, WRONG_MAX_PCT)),
        "speed": {**_line(base, 1 if fast else 0, SPEED_PCT if fast else 0), "seconds": seconds},
        "streak": _line(base, previous_streak, min(STREAK_PCT * previous_streak, STREAK_MAX_PCT)),
    }
    total = max(0, base + sum(line["points"] for line in lines.values()))
    return {"base": base, **lines, "clean": clean, "total": total}

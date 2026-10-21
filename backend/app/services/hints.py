"""
Pistas de los retos: se entregan de a una y cuestan puntos.

Regla (20 oct, pendiente 7e(a)), una sola para la web y la terminal:
  * Cada pista abierta ANTES de resolver el reto resta HINT_PENALTY_RATE de
    sus puntos al resolverlo (10 %: un reto de 200 pts con 2 pistas da 160).
  * Abrirlas DESPUÉS de resolverlo es gratis (repaso), y los retos de práctica
    (0 pts) no tienen nada que descontar.
  * Los puntos nunca bajan de 0, y la misma pista no se cobra dos veces.
  * Para la dificultad adaptativa, cada pista usada antes de resolver cuenta
    como un intento más (ver difficulty.recommend_level).

El texto de una pista cerrada NUNCA sale por la API: `public_challenge` la
manda vacía, así no se puede leer gratis desde el navegador ni desde
`/workspace/active.json` en la terminal.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.models.hint import HintUnlock
from app.models.submission import Solve

HINT_PENALTY_RATE = 0.10
HINT_NOT_FOUND = "Esa pista no existe."


def cost_per_hint(challenge: Challenge) -> int:
    return round((challenge.points or 0) * HINT_PENALTY_RATE)


def unlocked_by_challenge(db: DbSession, user_id: int | None) -> dict[str, list[int]]:
    """{reto: [índices abiertos]} de un jugador — misma forma que `app.hints` del frontend."""
    if user_id is None:
        return {}
    result: dict[str, list[int]] = {}
    for challenge_id, index in db.execute(
        select(HintUnlock.challenge_id, HintUnlock.hint_index)
        .where(HintUnlock.user_id == user_id)
        .order_by(HintUnlock.challenge_id, HintUnlock.hint_index)
    ).all():
        result.setdefault(challenge_id, []).append(index)
    return result


def hints_before_solve(db: DbSession, user_id: int, challenge: Challenge) -> int:
    """Pistas que el jugador abrió mientras el reto seguía sin resolver."""
    query = select(func.count()).select_from(HintUnlock).where(
        HintUnlock.user_id == user_id, HintUnlock.challenge_id == challenge.id
    )
    solve = db.get(Solve, (user_id, challenge.id))
    if solve is not None:
        query = query.where(HintUnlock.unlocked_at <= solve.solved_at)
    return db.scalar(query) or 0


def points_after_hints(db: DbSession, user_id: int, challenge: Challenge) -> int:
    """Puntos que gana al resolver el reto ahora (se llama antes de crear el Solve)."""
    used = hints_before_solve(db, user_id, challenge)
    return max(0, (challenge.points or 0) - used * cost_per_hint(challenge))


def unlock(db: DbSession, user_id: int, challenge: Challenge, raw_index) -> dict:
    hints = list(challenge.hints or [])
    text = str(raw_index if raw_index is not None else "").strip()
    if not text.isdigit() or int(text) >= len(hints):
        return {"ok": False, "status": 404, "error": HINT_NOT_FOUND}
    index = int(text)

    solved = db.get(Solve, (user_id, challenge.id)) is not None
    already = db.get(HintUnlock, (user_id, challenge.id, index)) is not None
    if not already:
        db.add(HintUnlock(user_id=user_id, challenge_id=challenge.id, hint_index=index))
        db.commit()
    used = hints_before_solve(db, user_id, challenge)
    return {
        "ok": True,
        "challengeId": challenge.id,
        "index": index,
        "hint": hints[index],
        "alreadyUnlocked": already,
        # Lo que costó ESTA pista (0 si ya estaba abierta o el reto ya estaba resuelto).
        "cost": 0 if already or solved else cost_per_hint(challenge),
        "hintsUsed": used,
        # Lo que daría el reto si lo resuelve ahora (o lo que ganó, si ya lo resolvió).
        "pointsIfSolved": max(0, (challenge.points or 0) - used * cost_per_hint(challenge)),
    }

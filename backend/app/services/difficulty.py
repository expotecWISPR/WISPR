"""
Dificultad adaptativa (guía del ingeniero, fase 4): al resolver un reto, el
sistema elige el siguiente con un nivel ajustado a cómo le fue al jugador.

Reglas simples a propósito — se pueden explicar ante el profesor y
demostrar en vivo. Scikit-learn (CLAUDE.md) queda para cuando haya datos
reales de uso; para el MVP alcanza con esta tabla.

    Situación en el último reto                     Siguiente nivel
    ----------------------------------------------  ----------------
    Lo resolvió en el 1.er o 2.º intento             sube un nivel
    Lo resolvió con 3 a 6 intentos                   se mantiene
    Más de 5 intentos fallidos (resuelto o no)       baja un nivel
    Ya está en el nivel más alto o más bajo          se queda ahí

"Intentos fallidos" sale de la tabla `submissions`, y desde el 20 oct cada
pista abierta antes de resolver (`hint_unlocks`) cuenta como un intento más.
Diferencia con la guía, anotada en CLAUDE.md: el nivel no se
guarda en una tabla aparte: se calcula por categoría a partir del historial
(`player_levels`), así nunca queda desincronizado de lo que pasó de verdad.

Qué reto se recomienda (`next_challenge`):
  * Si el reto resuelto es de una técnica con generador (XOR, WEP), se CREA
    uno nuevo de esa técnica en el nivel calculado, con historia de la IA
    (challenge_factory.py). Si ya tiene uno pendiente igual, se reusa.
  * Si no (retos Wi-Fi del catálogo), un reto sin resolver: primero de la
    misma categoría, lo más cerca posible del nivel calculado; si no queda
    ninguno, de otra categoría. Si ya resolvió todo, se crea uno nuevo.
  * Nunca se recomienda un reto ya resuelto.
"""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.models.submission import Solve, Submission
from app.models.user import User
from app.services import challenge_factory, challenges, hints
from app.services.technique_info import TECHNIQUES

LEVELS = ["Foundation", "Medium", "Hard", "Expert"]
# Las técnicas con generador llegan hasta hard (technique_info.LEVEL_TO_SPEC).
MAX_GENERATED_LEVEL = "Hard"
STUCK_FAILS = 6  # "más de 5 intentos fallidos"


def _index(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def failed_attempts(db: DbSession, user_id: int, challenge_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Submission)
        .where(Submission.user_id == user_id, Submission.challenge_id == challenge_id, Submission.correct.is_(False))
    ) or 0


def recommend_level(db: DbSession, user_id: int, challenge: Challenge, solved: bool = True) -> tuple[str, str]:
    """(nivel siguiente, explicación en español) según la tabla de reglas."""
    fails = failed_attempts(db, user_id, challenge.id)
    # Cada pista abierta antes de resolver cuenta como un intento más (20 oct):
    # resolver "al primer intento" con dos pistas no es lo mismo que sin ayuda.
    used = hints.hints_before_solve(db, user_id, challenge)
    effective = fails + used
    with_hints = f" y {used} pista{'s' if used != 1 else ''}" if used else ""
    current = _index(challenge.difficulty)
    if effective >= STUCK_FAILS:
        delta, why = -1, f"necesitaste {fails} intentos fallidos{with_hints} en «{challenge.title}»"
    elif not solved:
        delta, why = 0, f"todavía estás trabajando en «{challenge.title}»"
    elif effective <= 1 and not used:
        delta, why = 1, f"resolviste «{challenge.title}» al {'primer' if fails == 0 else 'segundo'} intento"
    elif effective <= 1:
        delta, why = 1, f"resolviste «{challenge.title}» al primer intento con 1 pista"
    else:
        delta, why = 0, f"resolviste «{challenge.title}» con {fails + 1} intento{'s' if fails else ''}{with_hints}"

    target = min(max(current + delta, 0), len(LEVELS) - 1)
    level = LEVELS[target]
    if target == current and delta != 0:
        return level, f"Te quedas en {level} (ya es el nivel {'más alto' if delta > 0 else 'más bajo'}): {why}."
    verb = {1: "Subes a", 0: "Sigues en", -1: "Bajas a"}[target - current]
    return level, f"{verb} {level}: {why}."


def player_levels(db: DbSession, user_id: int) -> dict[str, dict]:
    """
    Nivel actual por categoría: la regla aplicada al último reto que el
    jugador intentó en esa categoría. Alguien puede estar en Hard en
    criptografía y empezando en WPA/WPA2.
    """
    last_by_category: dict[str, Challenge] = {}
    rows = db.execute(
        select(Challenge, func.max(Submission.created_at).label("last"))
        .join(Submission, Submission.challenge_id == Challenge.id)
        .where(Submission.user_id == user_id)
        .group_by(Challenge.id)
        .order_by(func.max(Submission.created_at))
    ).all()
    for challenge, _last in rows:
        last_by_category[challenge.category] = challenge  # el más reciente pisa al anterior
    solved = set(db.scalars(select(Solve.challenge_id).where(Solve.user_id == user_id)))
    result = {}
    for category, challenge in last_by_category.items():
        level, reason = recommend_level(db, user_id, challenge, solved=challenge.id in solved)
        result[category] = {"level": level, "reason": reason}
    return result


def _pick_from_catalog(db: DbSession, user: User, solved: Challenge, level: str) -> Challenge | None:
    solved_ids = set(db.scalars(select(Solve.challenge_id).where(Solve.user_id == user.id)))
    candidates = [c for c in challenges.list_active(db, user.id) if c.id not in solved_ids]
    if not candidates:
        return None
    target = _index(level)
    return min(candidates, key=lambda c: (c.category != solved.category, abs(_index(c.difficulty) - target),
                                          _index(c.difficulty) < target, c.points))


def next_challenge(db: DbSession, user: User, solved: Challenge) -> tuple[Challenge | None, str, str]:
    """
    (reto recomendado, explicación, motivo si la IA no se pudo usar). Se
    llama justo después de registrar un acierto nuevo.
    """
    level, reason = recommend_level(db, user.id, solved)

    technique = solved.kind if solved.kind in TECHNIQUES else None
    if technique is None:
        pick = _pick_from_catalog(db, user, solved, level)
        if pick is not None:
            return pick, reason, ""
        technique = random.choice(list(TECHNIQUES))  # ya resolvió todo: uno nuevo

    gen_level = level if _index(level) <= _index(MAX_GENERATED_LEVEL) else MAX_GENERATED_LEVEL
    pending = db.scalars(
        select(Challenge)
        .outerjoin(Solve, (Solve.challenge_id == Challenge.id) & (Solve.user_id == user.id))
        .where(Challenge.owner_id == user.id, Challenge.kind == technique, Challenge.difficulty == gen_level,
               Challenge.is_active.is_(True), Solve.challenge_id.is_(None),
               Challenge.points > 0)  # los de práctica (pedidos por el jugador) no cuentan como siguiente
        .limit(1)
    ).first()
    if pending is not None:
        return pending, reason, ""
    created, ai_error = challenge_factory.create_challenge(db, user, technique, gen_level)
    return created, reason, ai_error

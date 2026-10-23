"""
Crea retos NUEVOS con historia de la IA. Tres usos (`purpose`):

  - "adaptive": el "laboratorio de continuación" que el frontend agrega a la
    cola al resolver un reto (`nextChallenge`). Lo elige el motor adaptativo.
    Solo para ese jugador, con puntos normales.
  - "practice": un estudiante lo pide eligiendo técnica, dificultad y
    escenario (POST /api/challenges/generate). Solo para él. Desde el 22 oct
    da puntos con RENDIMIENTO DECRECIENTE por técnica + nivel (ver
    PRACTICE_DECAY): el primero vale el 100 %, el segundo el 50 %, el tercero
    el 25 % y desde el cuarto 0. Así no se puede subir en el ranking pidiendo
    retos fáciles sin parar, y conviene probar técnicas y niveles nuevos.
    Cuentan también los pedidos sin resolver: pedir 5 de golpe no los cobra
    todos al 100 %.
  - "class": un profesor/admin lo pide con los mismos parámetros. Lo ven TODOS
    los estudiantes, con puntos normales, y cada uno recibe su propio archivo
    y su propia flag la primera vez que lo abre (instances.py). (Los grupos
    todavía viven solo en el prototipo Node; cuando se migren, se podrá
    publicar para un grupo.)

Quién decide qué (guía del ingeniero, 13 oct):
  - técnica y nivel  -> el motor adaptativo (difficulty.py), es decir, el código
  - parámetros       -> challenge_generator.py (XOR_LEVELS / WEP_LEVELS)
  - flag             -> challenge_generator.generate_flag (`secrets`)
  - título, historia y una pista -> la IA (ai_advisor.py), o una plantilla
  - objetivo técnico, pista técnica y solución -> technique_info.py

Antes de generar el archivo, todo pasa por ChallengeSpec (regla del
pipeline: nada llega al generador sin validar).
"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.models.submission import Solve, Submission
from app.models.user import User
from app.schemas.challenge import ChallengeSpec
from app.services import ai_advisor, challenges, instances
from app.services.challenge_generator import generate_flag
from app.services.challenges import DIFFICULTY_POINTS, SPEC_DIFFICULTY
from app.services.technique_info import LEVEL_TO_SPEC, TECHNIQUES, technique_level


def recent_titles(db: DbSession, user_id: int, limit: int = 15) -> list[str]:
    """Títulos que el jugador ya vio: sus retos generados y los que intentó hace poco."""
    owned = db.scalars(
        select(Challenge.title).where(Challenge.owner_id == user_id).order_by(Challenge.created_at.desc()).limit(limit)
    )
    tried = db.scalars(
        select(Challenge.title).join(Submission, Submission.challenge_id == Challenge.id)
        .where(Submission.user_id == user_id).order_by(Submission.created_at.desc()).limit(limit)
    )
    return list(dict.fromkeys([*owned, *tried]))[:limit]


PURPOSES = ("adaptive", "practice", "class")
# Fracción de los puntos del nivel que da el 1.º, 2.º y 3.º reto de práctica de
# la misma técnica y nivel; desde el 4.º, 0 (sigue sirviendo para practicar).
PRACTICE_DECAY = (1.0, 0.5, 0.25)
# Niveles que se pueden pedir: las técnicas llegan hasta hard.
REQUESTABLE_LEVELS = ("Foundation", "Medium", "Hard")
# Retos por resolver que puede tener un estudiante a la vez, contando el
# catálogo (23 oct): cada reto que resuelve libera un espacio. Así su lista de
# retos no se satura (y tampoco el disco ni la base de datos). Los que publica
# un profesor no se frenan: son tarea de clase.
MAX_PENDING = 15
PENDING_ERROR = (f"Ya tienes {MAX_PENDING} retos por resolver. "
                 "Resuelve uno para liberar un espacio y pedir otro.")


def options(db: DbSession | None = None, user: User | None = None) -> dict:
    """
    Lo que se puede elegir al pedir un reto (el formulario del frontend lo lee
    de acá). Con la sesión de un estudiante incluye `practicePoints`: cuánto
    valdría su próximo reto de cada técnica y nivel, para que vea la regla de
    rendimiento decreciente antes de pedirlo.
    """
    result = {
        "techniques": [{"id": key, "name": info["name"], "category": info["label"]} for key, info in TECHNIQUES.items()],
        "levels": list(REQUESTABLE_LEVELS),
        "themes": [short for short, _ in ai_advisor.THEMES],
    }
    if db is not None and user is not None and user.role not in ("profesor", "admin"):
        result["practicePoints"] = {
            technique: {level: practice_points(db, user.id, technique, level) for level in REQUESTABLE_LEVELS}
            for technique in TECHNIQUES
        }
        result["fullPoints"] = {level: DIFFICULTY_POINTS[level] for level in REQUESTABLE_LEVELS}
        result["pending"] = pending_count(db, user.id)
        result["maxPending"] = MAX_PENDING
    return result


def pending_count(db: DbSession, user_id: int) -> int:
    """Retos que el jugador ve y todavía no resolvió (catálogo + los suyos)."""
    solved = set(db.scalars(select(Solve.challenge_id).where(Solve.user_id == user_id)))
    return sum(1 for challenge in challenges.list_active(db, user_id) if challenge.id not in solved)


def practice_points(db: DbSession, user_id: int, technique: str, label: str) -> int:
    """Puntos del próximo reto de práctica de esa técnica y nivel (PRACTICE_DECAY)."""
    previous = db.scalar(
        select(func.count()).select_from(Challenge)
        .where(Challenge.owner_id == user_id, Challenge.purpose == "practice",
               Challenge.kind == technique, Challenge.difficulty == label)
    ) or 0
    factor = PRACTICE_DECAY[previous] if previous < len(PRACTICE_DECAY) else 0.0
    return round(DIFFICULTY_POINTS[label] * factor)


def request_challenge(db: DbSession, user: User, body: dict) -> dict:
    """
    POST /api/challenges/generate: el usuario elige técnica, dificultad y
    (opcional) escenario. Solo opciones de listas fijas, salvo el escenario,
    que es texto corto validado. El estudiante recibe un reto de práctica; el
    profesor/admin publica uno para todos (ver `purpose` arriba).
    """
    technique = str(body.get("technique") or "")
    level = str(body.get("difficulty") or "")
    if technique not in TECHNIQUES:
        return {"ok": False, "error": "Elige una técnica de la lista."}
    if level not in REQUESTABLE_LEVELS:
        return {"ok": False, "error": "Elige una dificultad de la lista."}
    try:
        theme = ai_advisor.resolve_theme(body.get("theme"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    purpose = "class" if user.role in ("profesor", "admin") else "practice"
    if purpose == "practice" and pending_count(db, user.id) >= MAX_PENDING:
        return {"ok": False, "error": PENDING_ERROR}
    challenge, ai_error = create_challenge(db, user, technique, level, purpose=purpose, theme=theme)
    return {"ok": True, "challenge": challenge, "purpose": purpose, "aiError": ai_error}


def create_challenge(
    db: DbSession,
    user: User,
    technique: str,
    level: str,
    purpose: str = "adaptive",
    theme: tuple[str, str] | None = None,
) -> tuple[Challenge, str]:
    """
    Crea el reto y, si es de un solo jugador, su instancia con archivo y flag
    propios. `level` en el vocabulario del frontend (Foundation/Medium/Hard;
    Expert se genera como Hard). `user` es quien lo pide. Devuelve (reto,
    motivo si la IA no se pudo usar).
    """
    if purpose not in PURPOSES:
        raise ValueError(f"purpose inválido: {purpose}")
    difficulty = LEVEL_TO_SPEC[level]
    label = SPEC_DIFFICULTY[difficulty]
    info, texts = TECHNIQUES[technique], technique_level(technique, difficulty)
    owner_id = None if purpose == "class" else user.id
    points = practice_points(db, user.id, technique, label) if purpose == "practice" else DIFFICULTY_POINTS[label]
    narrative, source, ai_error = ai_advisor.generate_narrative(
        technique, difficulty, avoid_titles=recent_titles(db, user.id), player_key=str(user.id), theme=theme
    )

    challenge_id = f"ai-{info['flag_prefix']}-{difficulty}-{secrets.token_hex(4)}"
    spec = ChallengeSpec(
        id=challenge_id,
        difficulty=difficulty,
        category=info["spec_category"],
        description=narrative.description,
        technique=technique,
        flag=generate_flag(technique),
        hint=narrative.hint,
        solution=texts["solution"],
    )
    challenge = Challenge(
        id=spec.id,
        title=narrative.title,
        category=info["label"],
        kind=spec.technique,
        difficulty=label,
        points=points,
        purpose=purpose,
        description=spec.description,
        objective=texts["objective"],
        flag="",  # la flag vive solo en la instancia del dueño
        solution=spec.solution,
        tools=list(info["tools"]),
        hints=[spec.hint, texts["hint"]],
        files=[{"name": f"{spec.id}.{texts['ext']}", "type": texts["ext"], "desc": texts["file_desc"]}],
        generated=True,
        generator=source,  # "ai" o "template": queda registrado de dónde salió la historia
        owner_id=owner_id,
    )
    db.add(challenge)
    db.flush()
    if owner_id is not None:
        # Su único jugador ya tiene archivo y flag. En "class" no: el profesor
        # no juega, y cada estudiante recibe la suya al abrirlo.
        instances.create(db, owner_id, challenge, spec)
    db.commit()
    return challenge, ai_error

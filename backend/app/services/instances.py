"""
Instancias por jugador: cada jugador recibe SU archivo con SU flag (guía del
ingeniero, fase 3). Así no puede pasarle la flag a un compañero, y dos
jugadores que abren el mismo reto ven archivos distintos.

Aplica a los retos cuya técnica tiene generador (`technique_info.TECHNIQUES`:
XOR y WEP). Los retos Wi-Fi siguen con archivo fijo (CLAUDE.md, punto 7c).

¿Cuándo se crea? La primera vez que el jugador pide el archivo
(`GET /api/challenges/{id}/files/{nombre}`), y no en `POST /challenges/active`
como sugería la guía: desde el 12 oct nginx manda esa ruta a Node (terminal
Kali), así que FastAPI no la ve. La descarga, en cambio, siempre pasa por acá
— desde la web y desde Node, que la pide con el token del jugador para
armarle el workspace —, así que web y terminal reciben el MISMO archivo.
"""

from __future__ import annotations

import secrets
from pathlib import Path, PurePosixPath

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge, ChallengeInstance
from app.schemas.challenge import ChallengeSpec
from app.services import challenge_generator
from app.services.technique_info import LEVEL_TO_SPEC, TECHNIQUES


def is_per_player(challenge: Challenge) -> bool:
    return challenge.kind in TECHNIQUES


def spec_for(challenge: Challenge, flag: str) -> ChallengeSpec:
    """El ChallengeSpec de un reto del catálogo con la flag de un jugador. Valida igual que siempre."""
    hints = [h for h in (challenge.hints or []) if h]
    return ChallengeSpec(
        id=challenge.id,
        difficulty=LEVEL_TO_SPEC.get(challenge.difficulty, "easy"),
        category=TECHNIQUES[challenge.kind]["spec_category"],
        description=challenge.description or challenge.title,
        technique=challenge.kind,
        flag=flag,
        hint=hints[0] if hints else "-",
        solution=challenge.solution or "-",
    )


def _file_name(challenge: Challenge, spec: ChallengeSpec) -> str:
    files = challenge.files or []
    if files:
        return files[0]["name"]
    return f"{challenge.id}.{TECHNIQUES[spec.technique]['levels'][spec.difficulty]['ext']}"


def artifact_file(instance: ChallengeInstance | None) -> Path | None:
    if instance is None or not instance.artifact:
        return None
    return challenge_generator.GENERATED_DIR / PurePosixPath(instance.artifact)


def _materialize(user_id: int, challenge: Challenge, spec: ChallengeSpec) -> str:
    """
    Genera el archivo en una carpeta con nombre al azar: si llegan dos
    pedidos a la vez (web + terminal), cada uno escribe en la suya y nunca se
    pisan; el que pierde la carrera borra la suya (ver get_or_create).
    """
    relative = PurePosixPath("instances", str(user_id), challenge.id, secrets.token_hex(8), _file_name(challenge, spec))
    challenge_generator.materialize_challenge(spec, challenge_generator.GENERATED_DIR / relative)
    return relative.as_posix()


def create(db: DbSession, user_id: int, challenge: Challenge, spec: ChallengeSpec) -> ChallengeInstance:
    """Instancia con un spec ya armado (lo usa challenge_factory al crear un reto nuevo). No hace commit."""
    instance = ChallengeInstance(user_id=user_id, challenge_id=challenge.id, flag=spec.flag,
                                 artifact=_materialize(user_id, challenge, spec))
    db.add(instance)
    return instance


def get_or_create(db: DbSession, user_id: int, challenge: Challenge) -> ChallengeInstance | None:
    """
    La instancia del jugador, creándola si no existe. None si el reto no es
    por jugador. Si la fila existe pero el archivo no está en este disco
    (otra computadora apuntando a la misma Supabase), se genera de nuevo,
    con flag nueva: la vieja solo servía para un archivo que ya no existe.
    """
    if not is_per_player(challenge):
        return None
    instance = db.get(ChallengeInstance, (user_id, challenge.id))
    current = artifact_file(instance)
    if current is not None and current.is_file():
        return instance

    spec = spec_for(challenge, challenge_generator.generate_flag(challenge.kind))
    relative = _materialize(user_id, challenge, spec)
    if instance is not None:
        instance.flag, instance.artifact = spec.flag, relative
        db.commit()
        return instance
    try:
        with db.begin_nested():
            db.add(ChallengeInstance(user_id=user_id, challenge_id=challenge.id, flag=spec.flag, artifact=relative))
        db.commit()
    except IntegrityError:
        # Otro pedido la creó primero: se usa la suya y se borra este archivo.
        (challenge_generator.GENERATED_DIR / PurePosixPath(relative)).unlink(missing_ok=True)
        db.commit()
    return db.get(ChallengeInstance, (user_id, challenge.id))

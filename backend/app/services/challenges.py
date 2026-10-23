"""
Catálogo de retos: forma pública, carga desde `challenges/catalog/catalog.json`
y archivos descargables.

`public_challenge` es la ÚNICA forma en que un reto sale por la API — igual
que `publicChallenge()` en `wispr_terminal_professional/challenge-engine.js`.
Nunca incluye `flag` ni `solution`.

Visibilidad (13 oct): los retos del catálogo (`owner_id` NULL) los ve
cualquiera; los que crea el motor adaptativo para un jugador
(challenge_factory.py) solo los ve y los juega su dueño.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.schemas.challenge import ChallengeSpec
from app.services import hints, instances
from app.services.technique_info import TECHNIQUES, technique_level

CHALLENGES_DIR = Path(__file__).resolve().parents[3] / "challenges"
CATALOG_FILE = CHALLENGES_DIR / "catalog" / "catalog.json"
# Archivos fijos de los retos Wi-Fi (uno por reto, iguales para todos los
# jugadores), generados con challenges/static/generar_wifi.js. Solución
# temporal hasta tener archivos por jugador — ver ese script.
STATIC_DIR = CHALLENGES_DIR / "static"

# Mismos puntos por dificultad que el prototipo (`difficultyPoints`).
DIFFICULTY_POINTS = {"Foundation": 120, "Medium": 200, "Hard": 340, "Expert": 500}
# ChallengeSpec usa easy/medium/hard; el frontend, el vocabulario del prototipo.
SPEC_DIFFICULTY = {"easy": "Foundation", "medium": "Medium", "hard": "Hard"}


def public_challenge(challenge: Challenge, unlocked_hints: list[int] | None = None, started_at: int | None = None) -> dict:
    """
    `unlocked_hints`: índices de las pistas que el jugador ya abrió. Las demás
    salen como "" (el frontend muestra "Pista N bloqueada"): su texto solo se
    entrega con POST /api/challenges/{id}/hints/{n}, que cobra la pista
    (ver app/services/hints.py).
    """
    unlocked = set(unlocked_hints or [])
    return {
        "id": challenge.id,
        "title": challenge.title,
        "category": challenge.category,
        "kind": challenge.kind,
        "difficulty": challenge.difficulty,
        "points": challenge.points,
        "description": challenge.description,
        "objective": challenge.objective,
        "tools": list(challenge.tools or []),
        "hints": [text if index in unlocked else "" for index, text in enumerate(challenge.hints or [])],
        "unlockedHints": sorted(i for i in unlocked if i < len(challenge.hints or [])),
        # Puntos que resta cada pista abierta antes de resolver el reto.
        "hintCost": hints.cost_per_hint(challenge),
        # Cuándo abrió el jugador este reto (ms), para su cronómetro; None si nunca.
        "startedAt": started_at,
        "files": [{"name": f["name"], "type": f.get("type"), "desc": f.get("desc")} for f in challenge.files or []],
        "generated": bool(challenge.generated),
        "generator": challenge.generator or "curriculum",
        # Archivo y flag propios de cada jugador (Node lo usa para `ctf show`).
        "perPlayer": instances.is_per_player(challenge),
    }


def _visible_to(user_id: int | None):
    if user_id is None:
        return Challenge.owner_id.is_(None)
    return or_(Challenge.owner_id.is_(None), Challenge.owner_id == user_id)


def list_active(db: DbSession, user_id: int | None = None) -> list[Challenge]:
    # Orden estable: primero por puntos (de Foundation a Expert), como el
    # catálogo del prototipo; los retos generados quedan entre los de su nivel.
    return list(db.scalars(
        select(Challenge)
        .where(Challenge.is_active.is_(True), _visible_to(user_id))
        .order_by(Challenge.points, Challenge.created_at, Challenge.id)
    ))


def get_active(db: DbSession, challenge_id: str, user_id: int | None = None) -> Challenge | None:
    challenge = db.get(Challenge, str(challenge_id or ""))
    if challenge is None or not challenge.is_active:
        return None
    if challenge.owner_id is not None and challenge.owner_id != user_id:
        return None  # reto de otro jugador: para este, no existe
    return challenge


def artifact_path(db: DbSession, user_id: int, challenge: Challenge, file_name: str) -> Path | None:
    """
    Ruta del archivo descargable, o None si no existe. Solo se sirven
    nombres declarados en `challenge.files` (nunca una ruta armada con lo que
    manda el usuario), así que no hay forma de pedir `../../.env`. En los
    retos por jugador se sirve SOLO el archivo de la instancia de quien lo
    pide (creándola la primera vez).
    """
    if file_name not in {f["name"] for f in challenge.files or []}:
        return None
    if instances.is_per_player(challenge):
        path = instances.artifact_file(instances.get_or_create(db, user_id, challenge))
    else:
        path = STATIC_DIR / challenge.id / file_name
    return path if path is not None and path.is_file() else None


# --- Sembrado del catálogo -------------------------------------------------

def _row_from_entry(entry: dict) -> dict:
    if "template" not in entry:
        return {
            "id": entry["id"], "title": entry["title"], "category": entry["category"],
            "kind": entry.get("kind"), "difficulty": entry["difficulty"], "points": entry["points"],
            "description": entry["description"], "objective": entry.get("objective", ""),
            "flag": entry["flag"], "solution": None,
            "tools": entry.get("tools", []), "hints": entry.get("hints", []), "files": entry.get("files", []),
            "generated": False, "generator": "curriculum",
        }

    # Reto del pipeline: la historia sale de la plantilla (validada por
    # ChallengeSpec, igual que todo lo que llega al generador) y la parte
    # técnica (objetivo, pista técnica, solución) de technique_info.py, la
    # misma que usan los retos que genera el motor adaptativo. Ya no se
    # genera ningún archivo acá: cada jugador recibe el suyo (instances.py).
    spec = ChallengeSpec.model_validate_json((CHALLENGES_DIR / entry["template"]).read_text(encoding="utf-8"))
    if spec.id != entry["id"]:
        raise ValueError(f"El id del catálogo ({entry['id']}) no coincide con el de su plantilla ({spec.id}).")
    level = technique_level(spec.technique, spec.difficulty)
    difficulty = SPEC_DIFFICULTY[spec.difficulty]
    return {
        "id": spec.id, "title": entry["title"], "category": entry["category"],
        "kind": spec.technique, "difficulty": difficulty, "points": DIFFICULTY_POINTS[difficulty],
        "description": spec.description, "objective": level["objective"],
        # La flag de la plantilla está en el repo: nunca se acepta (ver
        # flag_validator.expected_flag). Se guarda solo como referencia.
        "flag": spec.flag, "solution": level["solution"],
        "tools": TECHNIQUES[spec.technique]["tools"], "hints": [spec.hint, level["hint"]],
        "files": entry.get("files", []),
        "generated": False, "generator": "template",
    }


def seed_catalog(db: DbSession, catalog_file: Path = CATALOG_FILE) -> list[str]:
    """
    Inserta o actualiza cada reto del catálogo (se puede correr cuantas
    veces haga falta). No desactiva ni borra retos que ya no estén en el
    archivo, ni toca los retos generados para cada jugador.
    """
    entries = json.loads(catalog_file.read_text(encoding="utf-8"))["challenges"]
    seeded = []
    for entry in entries:
        row = _row_from_entry(entry)
        db.merge(Challenge(**row))
        seeded.append(row["id"])
    db.commit()
    return seeded

"""
Catálogo de retos: forma pública, carga desde `challenges/catalog/catalog.json`
y archivos descargables.

`public_challenge` es la ÚNICA forma en que un reto sale por la API — igual
que `publicChallenge()` en `wispr_terminal_professional/challenge-engine.js`.
Nunca incluye `flag` ni `solution`.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge
from app.schemas.challenge import ChallengeSpec
from app.services.challenge_generator import GENERATED_DIR, materialize_challenge

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


def public_challenge(challenge: Challenge) -> dict:
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
        "hints": list(challenge.hints or []),
        "files": [{"name": f["name"], "type": f.get("type"), "desc": f.get("desc")} for f in challenge.files or []],
        "generated": bool(challenge.generated),
        "generator": challenge.generator or "curriculum",
    }


def list_active(db: DbSession) -> list[Challenge]:
    # Orden estable: primero por puntos (de Foundation a Expert), como el
    # catálogo del prototipo.
    return list(db.scalars(
        select(Challenge).where(Challenge.is_active.is_(True)).order_by(Challenge.points, Challenge.id)
    ))


def get_active(db: DbSession, challenge_id: str) -> Challenge | None:
    challenge = db.get(Challenge, str(challenge_id or ""))
    return challenge if challenge is not None and challenge.is_active else None


def artifact_path(challenge: Challenge, file_name: str) -> Path | None:
    """
    Ruta del archivo descargable, o None si no existe. Solo se sirven
    nombres declarados en `challenge.files` (nunca una ruta armada con lo que
    manda el usuario), así que no hay forma de pedir `../../.env`.
    """
    if file_name not in {f["name"] for f in challenge.files or []}:
        return None
    for path in (STATIC_DIR / challenge.id / file_name, GENERATED_DIR / file_name):
        if path.is_file():
            return path
    return None


# --- Sembrado del catálogo -------------------------------------------------

def _row_from_entry(entry: dict) -> tuple[dict, ChallengeSpec | None]:
    if "template" not in entry:
        return {
            "id": entry["id"], "title": entry["title"], "category": entry["category"],
            "kind": entry.get("kind"), "difficulty": entry["difficulty"], "points": entry["points"],
            "description": entry["description"], "objective": entry.get("objective", ""),
            "flag": entry["flag"], "solution": None,
            "tools": entry.get("tools", []), "hints": entry.get("hints", []), "files": entry.get("files", []),
            "generated": False, "generator": "curriculum",
        }, None

    # Reto del pipeline: el contenido sale del ChallengeSpec (validado por
    # Pydantic igual que si lo hubiera generado la IA); el catálogo solo
    # agrega lo que el frontend necesita y el spec no tiene (título, etc.).
    spec = ChallengeSpec.model_validate_json((CHALLENGES_DIR / entry["template"]).read_text(encoding="utf-8"))
    if spec.id != entry["id"]:
        raise ValueError(f"El id del catálogo ({entry['id']}) no coincide con el de su plantilla ({spec.id}).")
    difficulty = SPEC_DIFFICULTY[spec.difficulty]
    return {
        "id": spec.id, "title": entry["title"], "category": entry["category"],
        "kind": spec.technique, "difficulty": difficulty, "points": DIFFICULTY_POINTS[difficulty],
        "description": spec.description, "objective": entry.get("objective", ""),
        "flag": spec.flag, "solution": spec.solution,
        "tools": entry.get("tools", []), "hints": [spec.hint], "files": entry.get("files", []),
        "generated": False, "generator": "template",
    }, spec


def seed_catalog(db: DbSession, catalog_file: Path = CATALOG_FILE) -> list[str]:
    """
    Inserta o actualiza cada reto del catálogo (se puede correr cuantas
    veces haga falta) y genera los archivos de los retos del pipeline.
    No desactiva ni borra retos que ya no estén en el archivo.
    """
    entries = json.loads(catalog_file.read_text(encoding="utf-8"))["challenges"]
    seeded = []
    for entry in entries:
        row, spec = _row_from_entry(entry)
        db.merge(Challenge(**row))
        if spec is not None:
            materialize_challenge(spec)
        seeded.append(row["id"])
    db.commit()
    return seeded

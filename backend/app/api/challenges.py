"""
Rutas de retos, envíos, ranking y progreso de lecciones.

Montadas en `/api` (sin `/v1`), igual que `app/api/players.py`, para calzar
exacto con el contrato que ya usa el frontend terminado
(`wispr_terminal_professional/docs/BACKEND-PENDIENTE.md`). Las respuestas son
dict planos con `ok: true|false` y errores en español, por la misma razón
que en players.py.

El frontend todavía manda `playerId` en el cuerpo o la URL: se ignora a
propósito. El jugador sale SIEMPRE de la sesión (`get_current_player`), así
nadie puede enviar flags o ver datos a nombre de otro.

Fuera de alcance por ahora (decidido 7 oct): la terminal Kali. Por eso
`/challenges/active` no arranca contenedores y `/platform/status` informa
Docker como no disponible.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.players import _json_body, get_current_player
from app.db.session import get_db
from app.models.user import User
from app.services import challenges, lessons, scoring

router = APIRouter(tags=["challenges"])

TERMINAL_UNAVAILABLE = "La terminal Kali todavía no está disponible en este backend."


@router.get("/challenges")
def list_challenges(db: Session = Depends(get_db)):
    """Pública (sin sesión), como en el prototipo: es solo el catálogo."""
    return {"ok": True, "challenges": [challenges.public_challenge(c) for c in challenges.list_active(db)]}


@router.get("/platform/status")
def platform_status():
    """Pública. El frontend la usa para mostrar si Docker/Kali está listo."""
    return {"ok": True, "docker": {"ready": False, "error": TERMINAL_UNAVAILABLE}}


@router.post("/challenges/active")
async def activate_challenge(
    request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)
):
    body = await _json_body(request)
    challenge = challenges.get_active(db, body.get("challengeId"))
    if challenge is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Reto o sesión inválidos."})
    # El prototipo acá preparaba el workspace del jugador y su contenedor Kali.
    # Sin terminal todavía, solo se confirma el reto; los archivos se bajan
    # desde la web (`/challenges/{id}/files/{name}`).
    return {
        "ok": True,
        "challenge": {**challenges.public_challenge(challenge), "directory": "/workspace/challenge"},
        "lab": {"ok": False, "error": TERMINAL_UNAVAILABLE},
        "target": {"ok": False, "optional": True},
    }


@router.get("/challenges/{challenge_id}/files/{file_name}")
def download_file(
    challenge_id: str, file_name: str, db: Session = Depends(get_db), player: User = Depends(get_current_player)
):
    challenge = challenges.get_active(db, challenge_id)
    path = challenges.artifact_path(challenge, file_name) if challenge else None
    if path is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Archivo no encontrado."})
    media_type = "application/vnd.tcpdump.pcap" if path.suffix == ".pcap" else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"Cache-Control": "no-store"})


@router.post("/submissions")
async def submit(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    return scoring.submit_flag(db, player, body.get("challengeId"), body.get("flag"), source="web")


@router.get("/submissions")
def terminal_submissions(player: User = Depends(get_current_player)):
    """
    En el prototipo devuelve los envíos hechos desde la terminal Kali
    (`ctf submit`) para que la web los muestre. Sin terminal todavía, no hay
    ninguno.
    """
    return {"ok": True, "submissions": [], "cursor": 0}


@router.get("/ranking")
def get_ranking(db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    return {"ok": True, "ranking": scoring.ranking(db, player.id)}


@router.post("/progress")
async def save_progress(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    result = lessons.merge_lesson_progress(db, player.id, body.get("lessonId"), body)
    if not result["ok"]:
        return JSONResponse(status_code=400, content=result)
    return {"ok": True, "lessonProgress": lessons.lesson_progress(db, player.id)}

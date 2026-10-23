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

La terminal Kali la atiende el servidor Node del prototipo en "modo
conectado" (12 oct): nginx le manda `/ws/terminal`, `/api/kali/*`,
`/challenges/active` y `/platform/status`. Node pregunta a este backend de
quién es cada token (`/api/players/me`) y le reenvía los `ctf submit` a
`POST /submissions` con `source: "terminal"`. Las versiones de
`/challenges/active` y `/platform/status` de acá solo se usan si no hay Node
(sin terminal): no arrancan contenedores e informan Docker como no disponible.
Configuración en docs/arquitectura_mvp.md (CONFIG AWS) y deploy/nginx/.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.players import _json_body, get_current_player, get_optional_player
from app.core import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.services import bonus, challenge_factory, challenges, hints, instances, lessons, scoring

router = APIRouter(tags=["challenges"])

TERMINAL_UNAVAILABLE = "La terminal Kali todavía no está disponible en este backend."


@router.get("/challenges")
def list_challenges(db: Session = Depends(get_db), player: User | None = Depends(get_optional_player)):
    """
    Pública (sin sesión), como en el prototipo: es el catálogo. Con sesión,
    incluye además los retos que el motor adaptativo creó para ese jugador.
    """
    visible = challenges.list_active(db, player.id if player else None)
    # Con sesión, las pistas que ese jugador ya abrió vienen con su texto (así
    # Node las deja en active.json y `ctf hint` no las vuelve a pedir).
    unlocked = hints.unlocked_by_challenge(db, player.id if player else None)
    timers = bonus.timers_by_challenge(db, player.id if player else None)
    return {
        "ok": True,
        "challenges": [challenges.public_challenge(c, unlocked.get(c.id), timers.get(c.id)) for c in visible],
        # Reglas de bonos y penalizaciones (bonus.py) y la hora del servidor:
        # el cronómetro del navegador se sincroniza con ella.
        "scoring": bonus.RULES,
        "serverNow": bonus.now_ms(),
    }


@router.post("/challenges/{challenge_id}/start")
def start_challenge(challenge_id: str, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    """
    Arranca el cronómetro del reto (la primera vez; después devuelve la misma
    hora). Lo llama el frontend al abrir el detalle de un reto o su terminal.
    """
    challenge = challenges.get_active(db, challenge_id, player.id)
    if challenge is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": scoring.CHALLENGE_NOT_FOUND})
    started = bonus.start_timer(db, player.id, challenge)
    return {"ok": True, "challengeId": challenge.id, "startedAt": bonus.to_ms(started), "serverNow": bonus.now_ms()}


@router.post("/challenges/{challenge_id}/hints/{index}")
def unlock_hint(challenge_id: str, index: str, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    """
    Entrega una pista y la anota: si el reto no está resuelto, le resta puntos
    al resolverlo (regla en app/services/hints.py). La usan el botón "Mostrar"
    de la web y `ctf hint` de la terminal (vía Node). Pedirla de nuevo no la
    cobra otra vez.
    """
    challenge = challenges.get_active(db, challenge_id, player.id)
    if challenge is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": scoring.CHALLENGE_NOT_FOUND})
    result = hints.unlock(db, player.id, challenge, index)
    status = result.pop("status", 200)
    return result if result["ok"] else JSONResponse(status_code=status, content=result)


@router.get("/challenges/options")
def generation_options(db: Session = Depends(get_db), player: User | None = Depends(get_optional_player)):
    """Pública. Técnicas, niveles y escenarios que se pueden elegir al pedir un
    reto; con sesión de estudiante, también cuánto valdría cada uno."""
    return {"ok": True, **challenge_factory.options(db, player)}


@router.post("/challenges/generate")
async def generate_challenge(
    request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)
):
    """
    Pide un reto nuevo eligiendo técnica, dificultad y escenario. La IA escribe
    la historia; la flag y el archivo los genera el backend. Estudiante: reto de
    práctica solo para él (con puntos decrecientes al repetir la misma técnica
    y nivel, ver challenge_factory.PRACTICE_DECAY). Profesor/admin: reto para todos los
    estudiantes. Ver app/services/challenge_factory.py.
    """
    # Cada pedido puede llamar a la IA (cuesta) y genera un archivo: 6 cada
    # 10 minutos por persona alcanzan de sobra para practicar.
    rate_limit.check("generate", str(player.id), limit=6, window_seconds=600)
    result = challenge_factory.request_challenge(db, player, await _json_body(request))
    if not result["ok"]:
        return JSONResponse(status_code=400, content=result)
    return {
        "ok": True,
        "challenge": challenges.public_challenge(result["challenge"]),
        "visibleTo": "everyone" if result["purpose"] == "class" else "me",
        "generationError": scoring.TEMPLATE_STORY if result["aiError"] else "",
    }


@router.get("/platform/status")
def platform_status():
    """Pública. El frontend la usa para mostrar si Docker/Kali está listo."""
    return {"ok": True, "docker": {"ready": False, "error": TERMINAL_UNAVAILABLE}}


@router.post("/challenges/active")
async def activate_challenge(
    request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)
):
    body = await _json_body(request)
    challenge = challenges.get_active(db, body.get("challengeId"), player.id)
    if challenge is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Reto o sesión inválidos."})
    # El prototipo acá preparaba el workspace del jugador y su contenedor Kali.
    # Sin terminal todavía, solo se confirma el reto (y se deja lista su
    # instancia, si es por jugador); los archivos se bajan desde la web
    # (`/challenges/{id}/files/{name}`).
    instances.get_or_create(db, player.id, challenge)
    return {
        "ok": True,
        "challenge": {
            **challenges.public_challenge(challenge, hints.unlocked_by_challenge(db, player.id).get(challenge.id)),
            "directory": "/workspace/challenge",
        },
        "lab": {"ok": False, "error": TERMINAL_UNAVAILABLE},
        "target": {"ok": False, "optional": True},
    }


@router.get("/challenges/{challenge_id}/files/{file_name}")
def download_file(
    challenge_id: str, file_name: str, db: Session = Depends(get_db), player: User = Depends(get_current_player)
):
    challenge = challenges.get_active(db, challenge_id, player.id)
    path = challenges.artifact_path(db, player.id, challenge, file_name) if challenge else None
    if path is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Archivo no encontrado."})
    media_type = {".pcap": "application/vnd.tcpdump.pcap", ".txt": "text/plain; charset=utf-8"}.get(
        path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"Cache-Control": "no-store"})


@router.post("/submissions")
async def submit(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    # Por jugador (no por IP): 30 envíos por minuto sobran para una persona
    # y frenan a un script que pruebe flags en masa.
    rate_limit.check("submissions", str(player.id), limit=30, window_seconds=60)
    body = await _json_body(request)
    # "terminal" lo manda Node al reenviar un `ctf submit`. Es solo una
    # etiqueta para el historial: no cambia la validación ni los puntos, así
    # que no importa que un cliente la pueda poner a mano.
    source = "terminal" if body.get("source") == "terminal" else "web"
    return scoring.submit_flag(db, player, body.get("challengeId"), body.get("flag"), source=source)


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

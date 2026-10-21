"""
Rutas del panel admin: `/api/admin/players*` y `/api/admin/groups`.

Montadas en `/api/admin` con el contrato exacto del prototipo
(`WISPR-frontend/server.js`), para que el panel admin del frontend funcione
sin cambiar una línea. Como en el resto de la API, el `playerId` que manda
el frontend se ignora: el admin sale SIEMPRE de la sesión.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.players import _json_body, get_current_player
from app.db.session import get_db
from app.models.user import User
from app.services import admin, auth_flow, groups

router = APIRouter(tags=["admin"])


def respond(result: dict):
    """Resultado de un servicio → respuesta HTTP. En error, el servicio
    indica el código en `status` (no va en el JSON que ve el frontend)."""
    status = result.pop("status", 400)
    return result if result["ok"] else JSONResponse(status_code=status, content=result)


def forbidden(message: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"ok": False, "error": message})


def get_admin(player: User = Depends(get_current_player)) -> User | None:
    """El jugador de la sesión si es admin; None si no (la ruta responde 403)."""
    return player if auth_flow.is_admin_player(player) else None


@router.get("/players")
def list_players(db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    return {"ok": True, "players": admin.list_players(db)}


@router.delete("/players")
async def delete_player(request: Request, db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    body = await _json_body(request)
    return respond(admin.delete_account(db, admin_user, body.get("targetId")))


@router.delete("/players/bulk")
async def bulk_delete(request: Request, db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    body = await _json_body(request)
    return respond(admin.bulk_delete(db, admin_user, body.get("targetIds")))


@router.post("/players/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    body = await _json_body(request)
    return respond(admin.reset_password(db, body.get("targetId")))


@router.post("/players/lock")
async def lock_player(request: Request, db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    body = await _json_body(request)
    # Por defecto, bloquear (igual que el prototipo): solo `locked: false` desbloquea.
    return respond(admin.set_lock(db, admin_user, body.get("targetId"), body.get("locked") is not False, body.get("reason")))


@router.get("/groups")
def list_all_groups(db: Session = Depends(get_db), admin_user: User | None = Depends(get_admin)):
    if admin_user is None:
        return forbidden(admin.ADMIN_ONLY)
    return {"ok": True, "groups": groups.all_groups(db)}

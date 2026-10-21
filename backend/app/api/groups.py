"""
Rutas de grupos de clase: `/api/groups*`.

Contrato exacto del prototipo (`WISPR-frontend/server.js`). Quién pide la
acción sale de la sesión; el `playerId` del cuerpo o la URL se ignora.
Permisos en app/services/groups.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.admin import forbidden, respond
from app.api.players import _json_body, get_current_player
from app.db.session import get_db
from app.models.user import User
from app.services import auth_flow, groups

router = APIRouter(tags=["groups"])


def _managed_group(db: Session, player: User, raw_group_id, denied: str):
    """(grupo, None) si el jugador puede modificarlo; (None, respuesta de error) si no."""
    group = groups.find_group(db, raw_group_id)
    if group is None:
        return None, respond({"ok": False, "status": 404, "error": groups.GROUP_NOT_FOUND})
    if not groups.can_manage(group, player):
        return None, forbidden(denied)
    return group, None


@router.post("")
async def create_group(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    if not groups.is_professor(player):
        return forbidden("Solo las cuentas de profesor pueden crear grupos.")
    body = await _json_body(request)
    return respond(groups.create_group(db, player, body.get("name")))


@router.get("/mine")
def my_groups(db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    if not groups.is_professor(player):
        return forbidden("Solo las cuentas de profesor tienen grupos.")
    return {"ok": True, "groups": groups.groups_of(db, player)}


@router.delete("")
async def delete_group(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes eliminar este grupo.")
    return error or respond(groups.delete_group(db, group))


@router.post("/members")
async def add_member(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes modificar este grupo.")
    return error or respond(groups.add_member(db, group, body.get("student")))


@router.delete("/members")
async def remove_member(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes modificar este grupo.")
    return error or respond(groups.remove_member(db, group, body.get("studentId")))


@router.post("/tasks")
async def add_task(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes modificar este grupo.")
    return error or respond(groups.add_task(db, group, body))


@router.delete("/tasks")
async def delete_task(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes modificar este grupo.")
    return error or respond(groups.delete_task(db, group, body.get("taskId")))


@router.post("/tasks/toggle")
async def toggle_task(request: Request, db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    body = await _json_body(request)
    group, error = _managed_group(db, player, body.get("groupId"), "No puedes modificar este grupo.")
    return error or respond(groups.toggle_task(db, group, body.get("taskId")))


@router.get("/student")
def student_detail(studentId: str = "", db: Session = Depends(get_db), player: User = Depends(get_current_player)):  # noqa: N803 — nombre del contrato
    student = db.get(User, int(studentId)) if studentId.strip().isdigit() else None
    if student is None:
        return respond({"ok": False, "status": 404, "error": "Ese estudiante no existe."})
    if not groups.can_view_student(db, player, student.id):
        return forbidden("No puedes ver el progreso de este estudiante.")
    return {"ok": True, "student": auth_flow.public_player(student, db)}


@router.get("/available-students")
def available_students(db: Session = Depends(get_db), player: User = Depends(get_current_player)):
    if not (groups.is_professor(player) or auth_flow.is_admin_player(player)):
        return forbidden("Acceso solo para profesores o administradores.")
    return {"ok": True, "students": groups.available_students(db)}

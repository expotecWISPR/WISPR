"""
Grupos de clase: un profesor arma los suyos, agrega estudiantes ya
registrados y les asigna tareas; un admin puede ver y gestionar todos.

Migrado (20 oct) de las rutas `/api/groups*` y `/api/admin/groups` de
`WISPR-frontend/server.js`. Las respuestas conservan la forma exacta de
`publicGroup()` / `publicGroupMember()` del prototipo (el frontend las lee
tal cual) y los mensajes de error son los mismos.

Reglas de permisos (iguales al prototipo):
- Crear grupos y listar "mis grupos": solo cuentas `profesor`.
- Modificar o borrar un grupo: su profesor dueño, o cualquier admin.
- Ver el progreso de un estudiante: un admin, o un profesor que lo tenga en
  alguno de SUS grupos.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import as_utc
from app.models.challenge import Challenge
from app.models.group import Group, GroupMember, GroupTask
from app.models.submission import Solve
from app.models.user import User
from app.services import auth_flow

GROUP_NOT_FOUND = "Ese grupo no existe."
TASK_NOT_FOUND = "Esa tarea no existe."
# Nombre de grupo: lista de caracteres PERMITIDOS (como el nombre de jugador
# en auth_flow), así nunca llega marcado HTML al frontend. Alcanza para
# nombres como "11-1 Ciber (mañana)" o "Sección #2".
_GROUP_NAME_RE = re.compile(r"^[\w .,'()#:/+-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ms(value) -> int:
    return int(as_utc(value).timestamp() * 1000)


def is_professor(user: User | None) -> bool:
    return user is not None and user.role == "profesor"


def can_manage(group: Group, user: User | None) -> bool:
    if user is None:
        return False
    return auth_flow.is_admin_player(user) or (is_professor(user) and group.owner_id == user.id)


def can_view_student(db: DbSession, requester: User, student_id: int) -> bool:
    if auth_flow.is_admin_player(requester):
        return True
    if not is_professor(requester):
        return False
    owned_membership = (
        select(GroupMember.user_id)
        .join(Group, Group.id == GroupMember.group_id)
        .where(Group.owner_id == requester.id, GroupMember.user_id == student_id)
        .limit(1)
    )
    return db.execute(owned_membership).first() is not None


# ---------------------------------------------------------------------------
# Forma pública (la del prototipo)
# ---------------------------------------------------------------------------


def _solved_by_user(db: DbSession, user_ids: list[int]) -> dict[int, dict]:
    """{user_id: {challenge_id: {time, points}}} en UNA consulta para todos."""
    solved: dict[int, dict] = {uid: {} for uid in user_ids}
    if user_ids:
        for solve in db.scalars(select(Solve).where(Solve.user_id.in_(user_ids))):
            solved[solve.user_id][solve.challenge_id] = {"time": _ms(solve.solved_at), "points": solve.points}
    return solved


def public_member(user: User, solved: dict) -> dict:
    return {
        "playerId": str(user.id),
        "name": user.full_name,
        "handle": user.username,
        "email": user.email or "",
        "solves": len(solved),
        "score": sum(entry["points"] for entry in solved.values()),
        # Con las fechas (no solo el total): el profesor arma un gráfico de
        # actividad sin pedir el detalle de cada estudiante.
        "solved": solved,
    }


def _public_task(task: GroupTask) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "dueDate": task.due_date.isoformat() if task.due_date else "",
        "challengeId": task.challenge_id or "",
        "createdAt": as_utc(task.created_at).isoformat(),
        "done": bool(task.done),
    }


def public_groups(db: DbSession, groups: list[Group]) -> list[dict]:
    """Varios grupos con sus miembros, tareas y dueño, en pocas consultas."""
    if not groups:
        return []
    group_ids = [group.id for group in groups]
    members_by_group: dict[str, list[User]] = {gid: [] for gid in group_ids}
    for group_id, user in db.execute(
        select(GroupMember.group_id, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id.in_(group_ids))
        .order_by(GroupMember.added_at, User.id)
    ).all():
        members_by_group[group_id].append(user)
    tasks_by_group: dict[str, list[GroupTask]] = {gid: [] for gid in group_ids}
    for task in db.scalars(select(GroupTask).where(GroupTask.group_id.in_(group_ids))):
        tasks_by_group[task.group_id].append(task)
    owner_ids = {group.owner_id for group in groups if group.owner_id is not None}
    owners = {user.id: user for user in db.scalars(select(User).where(User.id.in_(owner_ids)))} if owner_ids else {}
    solved = _solved_by_user(db, list({user.id for users in members_by_group.values() for user in users}))

    result = []
    for group in groups:
        owner = owners.get(group.owner_id)
        # Sin fecha al final; a igual fecha, la más vieja primero (como el prototipo).
        tasks = sorted(tasks_by_group[group.id], key=lambda t: (t.due_date or date.max, as_utc(t.created_at)))
        result.append(
            {
                "id": group.id,
                "name": group.name,
                "createdAt": as_utc(group.created_at).isoformat(),
                "ownerId": str(group.owner_id) if group.owner_id is not None else "",
                "ownerName": owner.full_name if owner else "(profesor eliminado)",
                "ownerHandle": owner.username if owner else "",
                "members": [public_member(user, solved[user.id]) for user in members_by_group[group.id]],
                "tasks": [_public_task(task) for task in tasks],
            }
        )
    return result


def public_group(db: DbSession, group: Group) -> dict:
    return public_groups(db, [group])[0]


def _newest_first(statement):
    return statement.order_by(Group.created_at.desc(), Group.id)


def groups_of(db: DbSession, professor: User) -> list[dict]:
    return public_groups(db, list(db.scalars(_newest_first(select(Group).where(Group.owner_id == professor.id)))))


def all_groups(db: DbSession) -> list[dict]:
    return public_groups(db, list(db.scalars(_newest_first(select(Group)))))


def available_students(db: DbSession) -> list[dict]:
    students = list(db.scalars(select(User).where(User.role == "estudiante")))
    solved = _solved_by_user(db, [user.id for user in students])
    members = [public_member(user, solved[user.id]) for user in students]
    return sorted(members, key=lambda m: m["name"].casefold())


# ---------------------------------------------------------------------------
# Cambios (cada uno devuelve {"ok": ...}; en error, "status" para la ruta)
# ---------------------------------------------------------------------------


def find_group(db: DbSession, raw_id) -> Group | None:
    group_id = str(raw_id or "").strip()
    return db.get(Group, group_id) if group_id and len(group_id) <= 36 else None


def create_group(db: DbSession, owner: User, raw_name) -> dict:
    name = " ".join(str(raw_name or "").split())[:64]
    if not name:
        return {"ok": False, "status": 400, "error": "Escribe un nombre para el grupo."}
    if not _GROUP_NAME_RE.match(name):
        return {"ok": False, "status": 400, "error": "El nombre del grupo solo puede tener letras, números, espacios y . , ' ( ) # : / + -"}
    group = Group(id=str(uuid.uuid4()), name=name, owner_id=owner.id)
    db.add(group)
    db.commit()
    return {"ok": True, "group": public_group(db, group)}


def delete_group(db: DbSession, group: Group) -> dict:
    db.delete(group)
    db.commit()
    return {"ok": True}


def add_member(db: DbSession, group: Group, raw_query) -> dict:
    query = str(raw_query or "").strip().lower()
    if not query:
        return {"ok": False, "status": 400, "error": "Escribe el usuario o correo del estudiante."}
    student = db.execute(
        select(User).where(or_(User.email == query, User.username == auth_flow.normalize_handle(query)))
    ).scalars().first()
    if student is None:
        return {"ok": False, "status": 404, "error": "No se encontró ningún estudiante con ese usuario o correo."}
    if student.role != "estudiante":
        return {"ok": False, "status": 400, "error": "Solo puedes agregar cuentas de estudiante."}
    if db.get(GroupMember, (group.id, student.id)) is None:
        db.add(GroupMember(group_id=group.id, user_id=student.id))
        db.commit()
    return {"ok": True, "group": public_group(db, group)}


def remove_member(db: DbSession, group: Group, raw_student_id) -> dict:
    text = str(raw_student_id or "").strip()
    membership = db.get(GroupMember, (group.id, int(text))) if text.isdigit() else None
    if membership is not None:
        db.delete(membership)
        db.commit()
    return {"ok": True, "group": public_group(db, group)}


def _parse_due_date(raw) -> date | None:
    """Fecha 'AAAA-MM-DD' del <input type=date>; cualquier otra cosa = sin fecha."""
    text = str(raw or "").strip()
    if not _DATE_RE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:  # ej. 2026-02-31
        return None


def add_task(db: DbSession, group: Group, data: dict) -> dict:
    title = str(data.get("title") or "").strip()[:120]
    if not title:
        return {"ok": False, "status": 400, "error": "Escribe un título para la tarea."}
    challenge_id = str(data.get("challengeId") or "").strip()
    if challenge_id:
        # Solo retos que ven TODOS (catálogo o publicados por un profesor): un
        # reto de práctica de un jugador no se puede asignar al grupo.
        challenge = db.get(Challenge, challenge_id[:80])
        if challenge is None or not challenge.is_active or challenge.owner_id is not None:
            return {"ok": False, "status": 400, "error": "Ese reto no existe."}
    task = GroupTask(
        id=str(uuid.uuid4()),
        group_id=group.id,
        title=title,
        description=str(data.get("description") or "").strip()[:500],
        due_date=_parse_due_date(data.get("dueDate")),
        challenge_id=challenge_id or None,
    )
    db.add(task)
    db.commit()
    return {"ok": True, "group": public_group(db, group)}


def _find_task(db: DbSession, group: Group, raw_task_id) -> GroupTask | None:
    task = db.get(GroupTask, str(raw_task_id or "").strip()[:36])
    return task if task is not None and task.group_id == group.id else None


def delete_task(db: DbSession, group: Group, raw_task_id) -> dict:
    task = _find_task(db, group, raw_task_id)
    if task is not None:
        db.delete(task)
        db.commit()
    return {"ok": True, "group": public_group(db, group)}


def toggle_task(db: DbSession, group: Group, raw_task_id) -> dict:
    task = _find_task(db, group, raw_task_id)
    if task is None:
        return {"ok": False, "status": 404, "error": TASK_NOT_FOUND}
    if task.challenge_id:
        return {
            "ok": False,
            "status": 400,
            "error": "Esta tarea está ligada a un reto: se completa sola cuando el estudiante lo resuelve.",
        }
    task.done = not task.done
    db.commit()
    return {"ok": True, "group": public_group(db, group)}

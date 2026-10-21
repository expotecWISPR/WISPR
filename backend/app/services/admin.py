"""
Panel admin: listar, eliminar, bloquear y resetear cuentas; y el cambio de
contraseña del propio jugador.

Migrado (20 oct) de las rutas `/api/admin/players*` y
`/api/players/change-password` de `WISPR-frontend/server.js`. Mensajes de
error textualmente iguales a los del prototipo (el frontend los muestra
directo), con estas diferencias deliberadas:
- Quién pide la acción sale de la SESIÓN, nunca del `playerId` del cuerpo:
  el prototipo confiaba en ese campo, así que cualquiera que supiera el id
  de un admin podía actuar como admin.
- Contraseña nueva de mínimo 8 caracteres (las reglas del registro, ver
  auth_flow.password_error), no 4.
- Al bloquear, se cierran las sesiones del jugador. Su terminal Kali la
  cierra Node solo: revisa cada 60 s que la sesión siga valiendo (12 oct).
- Sin historial de eventos de seguridad (`security`): el prototipo lo
  guardaba por cuenta, pero el frontend no lo muestra. Se devuelve vacío.
"""

from __future__ import annotations

import logging
import secrets
import shutil
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.security import hash_password, verify_password
from app.core.sessions import is_locked, revoke_user_sessions
from app.core.time_utils import as_utc
from app.models.user import User
from app.services import auth_flow, challenge_generator, lessons, scoring

log = logging.getLogger(__name__)

ADMIN_ONLY = "Acceso solo para administradores."
ACCOUNT_NOT_FOUND = "Esa cuenta no existe."
BULK_LIMIT = 500
# Sin O/0, I/1: el admin la dicta en persona y no debe haber confusiones.
_TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _target(db: DbSession, raw_id) -> User | None:
    """El id llega como texto desde el frontend ("12"); cualquier otra cosa no existe."""
    text = str(raw_id or "").strip()
    return db.get(User, int(text)) if text.isdigit() else None


def generate_temp_password() -> str:
    pick = lambda n: "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(n))  # noqa: E731
    return f"WISPR-{pick(4)}-{pick(4)}"


def list_players(db: DbSession) -> list[dict]:
    """Todas las cuentas, las más nuevas primero, con su progreso y estado de bloqueo."""
    now = datetime.now(timezone.utc)
    players = []
    for user in db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())):
        entry = auth_flow.public_player(user)
        entry.update(scoring.player_progress(db, user.id))
        entry["lessonProgress"] = lessons.lesson_progress(db, user.id)
        temporary_lock = not user.locked and is_locked(user, now)
        entry.update(
            {
                "isAdmin": auth_flow.is_admin_player(user),
                "locked": bool(user.locked),
                "lockReason": user.lock_reason or "",
                # En milisegundos, como Date.now() del prototipo; 0 = sin bloqueo temporal.
                "lockedUntil": int(as_utc(user.locked_until).timestamp() * 1000) if temporary_lock else 0,
                "security": [],
            }
        )
        players.append(entry)
    return players


def _remove_player_files(user_id: int) -> None:
    """Archivos de retos generados para ese jugador. En mejor esfuerzo: si
    falla, la cuenta igual queda borrada (no debe volver a aparecer)."""
    folder = challenge_generator.GENERATED_DIR / "instances" / str(user_id)
    try:
        shutil.rmtree(folder, ignore_errors=False)
    except FileNotFoundError:
        pass
    except OSError:
        log.exception("No se pudieron borrar los archivos de la cuenta %s", user_id)


def delete_account(db: DbSession, admin: User, raw_id) -> dict:
    target = _target(db, raw_id)
    if target is None:
        return {"ok": False, "status": 404, "error": ACCOUNT_NOT_FOUND}
    if target.id == admin.id:
        return {"ok": False, "status": 400, "error": "No puedes eliminar tu propia cuenta de administrador."}
    user_id = target.id
    # La base borra en cascada sus sesiones, envíos, aciertos, lecciones,
    # retos propios y membresías de grupos. Los grupos que haya creado (si era
    # profesor) se conservan sin dueño.
    db.delete(target)
    db.commit()
    _remove_player_files(user_id)
    return {"ok": True}


def bulk_delete(db: DbSession, admin: User, raw_ids) -> dict:
    requested = raw_ids[:BULK_LIMIT] if isinstance(raw_ids, list) else []
    deleted, skipped = [], []
    for raw in requested:
        result = delete_account(db, admin, raw)
        if result["ok"]:
            deleted.append(str(raw))
        else:
            reason = "cuenta propia" if result["status"] == 400 else "no existe"
            skipped.append({"id": raw, "reason": reason})
    return {"ok": True, "deleted": deleted, "skipped": skipped}


def reset_password(db: DbSession, raw_id) -> dict:
    """Contraseña temporal de un solo uso: el admin la entrega en persona y
    el jugador está obligado a cambiarla al entrar. Cierra sus sesiones."""
    target = _target(db, raw_id)
    if target is None:
        return {"ok": False, "status": 404, "error": ACCOUNT_NOT_FOUND}
    temp = generate_temp_password()
    target.password_hash = hash_password(temp)
    target.must_change_password = True
    target.failed_login_count = 0
    target.failed_login_window_started_at = None
    if not target.locked:
        target.locked_until = None  # un reset limpia el bloqueo automático, no el manual
    db.commit()
    revoke_user_sessions(db, target.id)
    # La temporal se devuelve UNA vez (nunca se guarda en claro).
    return {"ok": True, "tempPassword": temp, "handle": target.username, "name": target.full_name}


def set_lock(db: DbSession, admin: User, raw_id, lock: bool, reason) -> dict:
    target = _target(db, raw_id)
    if target is None:
        return {"ok": False, "status": 404, "error": ACCOUNT_NOT_FOUND}
    if target.id == admin.id:
        return {"ok": False, "status": 400, "error": "No puedes bloquear tu propia cuenta."}
    if lock:
        target.locked = True
        target.lock_reason = str(reason or "").strip()[:200]
        db.commit()
        closed = revoke_user_sessions(db, target.id)
        return {"ok": True, "locked": True, "sessionsClosed": closed}
    target.locked = False
    target.lock_reason = ""
    target.locked_until = None
    target.failed_login_count = 0
    target.failed_login_window_started_at = None
    db.commit()
    return {"ok": True, "locked": False}


def change_password(db: DbSession, user: User, current: str, new: str, session_token: str) -> dict:
    """El propio jugador cambia su contraseña. Obligatorio tras un reset del
    admin (mustChangePassword). Las demás sesiones del jugador se cierran:
    si alguien más conocía la contraseña vieja, pierde el acceso."""
    current, new = str(current or ""), str(new or "")
    if not verify_password(current, user.password_hash):
        return {"ok": False, "status": 401, "error": "La contraseña actual no es correcta."}
    if error := auth_flow.password_error(new):
        return {"ok": False, "status": 400, "error": error.replace("La contraseña", "La nueva contraseña", 1)}
    if verify_password(new, user.password_hash):
        return {"ok": False, "status": 400, "error": "La nueva contraseña debe ser distinta de la actual."}
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.failed_login_count = 0
    user.failed_login_window_started_at = None
    db.commit()
    revoke_user_sessions(db, user.id, keep_token=session_token)
    return {"ok": True, "player": auth_flow.public_player(user, db)}

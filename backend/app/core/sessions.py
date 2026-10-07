"""
Sesiones de login: creación, validación y revocación.

Migrado de `createSession`/`resolveSession`/`revokeSession` en
wispr_terminal_professional/server.js. La diferencia con un JWT normal
(ver app/core/security.py) es que acá el servidor guarda estado: cada
sesión vive como una fila en la tabla `sessions` (antes era una entrada en
`lab/data/sessions.json`), identificada por el hash SHA-256 del token. Eso
permite revocarla de verdad — borrando la fila — en vez de esperar a que
expire sola.

El token real (sin hashear) nunca se guarda en ningún lado: se genera,
se le entrega una sola vez al cliente en la respuesta HTTP, y de ahí en
adelante solo se compara su hash contra el de la tabla.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.time_utils import as_utc
from app.models.session import Session as SessionModel
from app.models.user import User


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: DbSession, user_id: int) -> str:
    """Genera un token de sesión nuevo (32 bytes aleatorios) y lo persiste hasheado."""
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    db.add(SessionModel(token_hash=hash_token(token), user_id=user_id, created_at=now, last_seen_at=now))
    db.commit()
    return token


def _is_expired(session: SessionModel, now: datetime) -> bool:
    idle_limit = timedelta(hours=settings.SESSION_IDLE_HOURS)
    max_limit = timedelta(days=settings.SESSION_MAX_DAYS)
    return (now - as_utc(session.last_seen_at)) > idle_limit or (now - as_utc(session.created_at)) > max_limit


def is_locked(user: User, now: datetime) -> bool:
    """Bloqueo manual (lo marcó un admin) o automático (fuerza bruta, con
    caducidad) — ver record_failed_login en app/services/auth_flow.py."""
    if user.locked:
        return True
    locked_until = as_utc(user.locked_until)
    return locked_until is not None and locked_until > now


def resolve_session(db: DbSession, token: str) -> User | None:
    """
    Devuelve el User dueño del token, o None si no existe, venció, la cuenta
    fue eliminada o está bloqueada. Si es válido, refresca `last_seen_at`
    (como mucho una vez por minuto, para no escribir en cada petición).
    """
    if not token or len(token) > 128:
        return None

    session = db.get(SessionModel, hash_token(token))
    if session is None:
        return None

    now = datetime.now(timezone.utc)
    user = db.get(User, session.user_id)
    if _is_expired(session, now) or user is None or is_locked(user, now):
        db.delete(session)
        db.commit()
        return None

    if (now - as_utc(session.last_seen_at)) > timedelta(minutes=1):
        session.last_seen_at = now
        db.commit()

    return user


def revoke_session(db: DbSession, token: str) -> None:
    db.execute(delete(SessionModel).where(SessionModel.token_hash == hash_token(token)))
    db.commit()


def revoke_user_sessions(db: DbSession, user_id: int) -> None:
    """Revoca TODAS las sesiones de un usuario — logout global: se usa al
    bloquear una cuenta, eliminarla o resetear su contraseña."""
    db.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
    db.commit()

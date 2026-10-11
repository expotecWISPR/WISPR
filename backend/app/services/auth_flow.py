"""
Lógica de registro y login con MFA por correo.

Migrado de `beginRegistration`/`completeRegistration`/`beginLogin`/
`completeLogin` (y sus `resend`) en wispr_terminal_professional/server.js,
ya validado de punta a punta con correo real. Los mensajes de error se
mantienen en español y textualmente iguales a los del prototipo: el
frontend ya los muestra directo al usuario (ver
wispr_terminal_professional/docs/BACKEND-PENDIENTE.md).

Diferencias deliberadas frente al prototipo:
- Contraseñas con bcrypt (`app.core.security`, ya probado) en vez de scrypt
  — mismo nivel de seguridad, no hay valor en reimplementar scrypt.
- Los "jugadores" quedan en la tabla `users` de Supabase en vez de
  `lab/data/players.json`.
- Los códigos pendientes (antes de verificarse) siguen en memoria — un
  diccionario del proceso — porque el MVP corre en una sola instancia; si
  algún día se corren varios workers, esto hay que moverlo a una tabla
  (dejado señalado, no resuelto acá, igual que lo marcaba el prototipo).
"""

from __future__ import annotations

import hmac
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.sessions import is_locked
from app.core.time_utils import as_utc
from app.models.user import User

GENDERS = {"femenino", "masculino", "otro"}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_HANDLE_INVALID_CHARS_RE = re.compile(r"[^a-z0-9._-]")

# Mensaje ÚNICO para credenciales inválidas: no revela si la cuenta existe.
GENERIC_LOGIN_ERROR = "Usuario o contraseña incorrectos."


@dataclass
class PendingRegistration:
    full_name: str
    handle: str
    gender: str
    email: str
    role: str
    password_hash: str
    code: str
    attempts: int = 0
    expires_at: float = 0.0
    last_sent_at: float = 0.0


@dataclass
class PendingLogin:
    user_id: int
    code: str
    attempts: int = 0
    expires_at: float = 0.0
    last_sent_at: float = 0.0


# En memoria, un diccionario por proceso — ver nota en el docstring del módulo.
_pending_registrations: dict[str, PendingRegistration] = {}
_pending_logins: dict[str, PendingLogin] = {}


def normalize_handle(value: str) -> str:
    cleaned = str(value or "").strip().lower().lstrip("@")
    cleaned = _HANDLE_INVALID_CHARS_RE.sub("", cleaned)[:32]
    return "@" + cleaned


def role_for_email(email: str) -> str | None:
    """El dominio institucional decide el rol: @est.* es más específico que
    el dominio de profesores, así que se comprueba primero."""
    value = str(email or "").strip().lower()
    if value.endswith(settings.STUDENT_EMAIL_SUFFIX):
        return "estudiante"
    if value.endswith(settings.TEACHER_EMAIL_SUFFIX):
        return "profesor"
    return None


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def is_admin_player(user: User) -> bool:
    """Un admin salta el MFA de login: basta usuario + contraseña correctos."""
    return user.role == "admin"


def public_player(user: User, db: DbSession | None = None) -> dict:
    """
    Forma pública de un usuario, igual a `publicPlayer()` en el prototipo.

    Con `db`, incluye el progreso real (retos resueltos, intentos, envíos y
    lecciones); sin `db`, esas llaves van vacías — el frontend espera que
    existan siempre.
    """
    player = {
        "playerId": str(user.id),
        "name": user.full_name,
        "handle": user.username,
        "gender": user.gender,
        "email": user.email or "",
        "role": user.role or "",
        "joined": as_utc(user.created_at).isoformat(),
        "solved": {},
        "attempts": {},
        "submissions": [],
        "lessonProgress": {},
        "mustChangePassword": bool(user.must_change_password),
    }
    if db is not None:
        # Import local: estos servicios no dependen de auth_flow, pero así se
        # evita cargarlos en cada import de este módulo.
        from app.services import lessons, scoring

        player.update(scoring.player_progress(db, user.id))
        player["lessonProgress"] = lessons.lesson_progress(db, user.id)
    return player


def discard_pending_registration(token: str) -> None:
    """Descarta un registro pendiente — se usa si el envío del correo falla,
    para no dejar un token "vivo" sin ninguna forma de completarlo."""
    _pending_registrations.pop(str(token or ""), None)


def discard_pending_login(token: str) -> None:
    _pending_logins.pop(str(token or ""), None)


def _prune(store: dict) -> None:
    now = time.time()
    for token in [t for t, pending in store.items() if pending.expires_at < now]:
        del store[token]


def _codes_match(submitted: str, expected: str) -> bool:
    return hmac.compare_digest(str(submitted or "").strip(), expected)


def record_failed_login(user: User, db: DbSession) -> None:
    """Suma un intento fallido dentro de la ventana móvil; al llegar al
    umbral, bloquea automáticamente."""
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=settings.LOGIN_LOCK_WINDOW_MINUTES)
    window_started_at = as_utc(user.failed_login_window_started_at)
    if window_started_at is None or (now - window_started_at) > window:
        user.failed_login_count = 0
        user.failed_login_window_started_at = now
    user.failed_login_count += 1
    if user.failed_login_count >= settings.LOGIN_LOCK_THRESHOLD:
        user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_DURATION_MINUTES)
        user.failed_login_count = 0
        user.failed_login_window_started_at = None
    db.commit()


def clear_failed_logins(user: User, db: DbSession) -> None:
    if user.failed_login_count or user.failed_login_window_started_at is not None:
        user.failed_login_count = 0
        user.failed_login_window_started_at = None
        db.commit()


# ---------------------------------------------------------------------------
# Registro (paso 1: validar y dejar pendiente / paso 2: confirmar código)
# ---------------------------------------------------------------------------


def begin_registration(data: dict, db: DbSession) -> dict:
    """
    Valida todo pero NO crea la cuenta todavía — solo deja un registro
    pendiente a la espera del código de verificación (MFA).
    """
    full_name = str(data.get("name") or "").strip()[:48]
    handle = normalize_handle(data.get("handle") or data.get("name"))
    gender = str(data.get("gender") or "").strip().lower()
    password = str(data.get("password") or "")
    email = str(data.get("email") or "").strip().lower()

    if not full_name:
        return {"ok": False, "error": "Escribe un nombre."}
    if len(handle) < 3:
        return {"ok": False, "error": "El usuario debe tener al menos 2 caracteres válidos."}
    if gender not in GENDERS:
        return {"ok": False, "error": "Selecciona un género."}
    if len(password) < 4:
        return {"ok": False, "error": "La contraseña debe tener al menos 4 caracteres."}
    if not _EMAIL_RE.match(email):
        return {"ok": False, "error": "Escribe un correo válido."}

    # Los dominios institucionales conservan su rol automático; cualquier
    # otro correo válido se acepta y entra como estudiante por defecto.
    role = role_for_email(email) or "estudiante"

    if db.execute(select(User).where(User.username == handle)).scalar_one_or_none():
        return {"ok": False, "error": "Ese usuario ya está registrado. Inicia sesión."}
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        return {"ok": False, "error": "Ese correo ya tiene una cuenta verificada. Inicia sesión."}

    _prune(_pending_registrations)
    # Un nuevo intento con el mismo usuario o correo reemplaza cualquier código pendiente anterior.
    for existing_token, pending in list(_pending_registrations.items()):
        if pending.handle == handle or pending.email == email:
            del _pending_registrations[existing_token]

    token = secrets.token_hex(24)
    now = time.time()
    _pending_registrations[token] = PendingRegistration(
        full_name=full_name,
        handle=handle,
        gender=gender,
        email=email,
        role=role,
        password_hash=hash_password(password),
        code=generate_code(),
        expires_at=now + settings.OTP_TTL_MINUTES * 60,
        last_sent_at=now,
    )
    return {"ok": True, "token": token, "email": email, "role": role, "code": _pending_registrations[token].code}


def complete_registration(token: str, code: str, db: DbSession) -> dict:
    """Segundo paso: el código correcto confirma el correo y recién ahí se crea la cuenta."""
    _prune(_pending_registrations)
    pending = _pending_registrations.get(str(token or ""))
    if pending is None:
        return {"ok": False, "error": "El código expiró o el registro ya no está disponible. Vuelve a registrarte."}
    if pending.attempts >= settings.OTP_MAX_ATTEMPTS:
        del _pending_registrations[token]
        return {"ok": False, "error": "Demasiados intentos incorrectos. Vuelve a registrarte para recibir un código nuevo."}

    pending.attempts += 1
    if not _codes_match(code, pending.code):
        remaining = max(0, settings.OTP_MAX_ATTEMPTS - pending.attempts)
        return {"ok": False, "error": f"Código incorrecto. Intentos restantes: {remaining}."}

    del _pending_registrations[token]
    # Re-chequeo por si otra pestaña/sesión ya reclamó el usuario o correo mientras este código estaba pendiente.
    if db.execute(select(User).where(User.username == pending.handle)).scalar_one_or_none():
        return {"ok": False, "error": "Ese usuario ya fue registrado en otra sesión. Vuelve a registrarte con otro usuario."}
    if db.execute(select(User).where(User.email == pending.email)).scalar_one_or_none():
        return {"ok": False, "error": "Ese correo ya fue verificado en otra sesión. Inicia sesión."}

    user = User(
        email=pending.email,
        username=pending.handle,
        full_name=pending.full_name,
        gender=pending.gender,
        role=pending.role,
        password_hash=pending.password_hash,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "player": public_player(user, db)}


def resend_verification_code(token: str) -> dict:
    _prune(_pending_registrations)
    pending = _pending_registrations.get(str(token or ""))
    if pending is None:
        return {"ok": False, "error": "El registro ya no está disponible. Vuelve a registrarte."}
    wait = settings.OTP_RESEND_COOLDOWN_SECONDS - (time.time() - pending.last_sent_at)
    if wait > 0:
        return {"ok": False, "error": f"Espera {ceil(wait)}s para volver a enviar el código."}
    pending.code = generate_code()
    pending.attempts = 0
    pending.expires_at = time.time() + settings.OTP_TTL_MINUTES * 60
    pending.last_sent_at = time.time()
    return {"ok": True, "email": pending.email, "code": pending.code}


# ---------------------------------------------------------------------------
# Login (paso 1: usuario+contraseña / paso 2: código MFA — excepto admins)
# ---------------------------------------------------------------------------


def begin_login(data: dict, db: DbSession) -> dict:
    """Primer paso del login: usuario y contraseña correctos, pero todavía
    falta el código MFA — se pide en cada inicio de sesión, no solo la
    primera vez (excepto cuentas admin, que no usan MFA)."""
    handle = normalize_handle(data.get("handle") or "")
    password = str(data.get("password") or "")
    user = db.execute(select(User).where(User.username == handle)).scalar_one_or_none()
    creds_ok = user is not None and verify_password(password, user.password_hash)

    now = datetime.now(timezone.utc)
    # Cuenta bloqueada (manual o automática): el motivo SOLO se revela a
    # quien acierta la contraseña (el dueño). Cualquier otro caso recibe el
    # mensaje genérico, para no filtrar qué cuentas existen ni cuáles están
    # bloqueadas.
    if user is not None and is_locked(user, now):
        if not creds_ok:
            return {"ok": False, "error": GENERIC_LOGIN_ERROR}
        if user.locked:
            return {"ok": False, "locked": True, "error": "Tu cuenta está bloqueada. Contacta al administrador del rango."}
        minutes = max(1, ceil((as_utc(user.locked_until) - now).total_seconds() / 60))
        return {
            "ok": False,
            "locked": True,
            "error": f"Cuenta bloqueada temporalmente por intentos fallidos. Intenta de nuevo en ~{minutes} min.",
        }

    if not creds_ok:
        if user is not None:
            record_failed_login(user, db)
        return {"ok": False, "error": GENERIC_LOGIN_ERROR}

    clear_failed_logins(user, db)

    if is_admin_player(user):
        return {"ok": True, "admin": True, "player": public_player(user, db)}

    if not user.email or not user.role:
        return {"ok": False, "error": "Esta cuenta no tiene un correo institucional verificado. Contacta al administrador del rango."}

    _prune(_pending_logins)
    for existing_token, pending in list(_pending_logins.items()):
        if pending.user_id == user.id:
            del _pending_logins[existing_token]

    token = secrets.token_hex(24)
    now_ts = time.time()
    _pending_logins[token] = PendingLogin(
        user_id=user.id,
        code=generate_code(),
        expires_at=now_ts + settings.OTP_TTL_MINUTES * 60,
        last_sent_at=now_ts,
    )
    return {"ok": True, "token": token, "email": user.email, "role": user.role, "code": _pending_logins[token].code}


def complete_login(token: str, code: str, db: DbSession) -> dict:
    _prune(_pending_logins)
    pending = _pending_logins.get(str(token or ""))
    if pending is None:
        return {"ok": False, "error": "El código expiró o la sesión ya no está disponible. Vuelve a iniciar sesión."}
    if pending.attempts >= settings.OTP_MAX_ATTEMPTS:
        del _pending_logins[token]
        return {"ok": False, "error": "Demasiados intentos incorrectos. Vuelve a iniciar sesión para recibir un código nuevo."}

    pending.attempts += 1
    if not _codes_match(code, pending.code):
        remaining = max(0, settings.OTP_MAX_ATTEMPTS - pending.attempts)
        return {"ok": False, "error": f"Código incorrecto. Intentos restantes: {remaining}."}

    del _pending_logins[token]
    user = db.get(User, pending.user_id)
    if user is None:
        return {"ok": False, "error": "Esta cuenta ya no existe."}
    return {"ok": True, "player": public_player(user, db)}


def resend_login_code(token: str, db: DbSession) -> dict:
    _prune(_pending_logins)
    pending = _pending_logins.get(str(token or ""))
    if pending is None:
        return {"ok": False, "error": "La sesión ya no está disponible. Vuelve a iniciar sesión."}
    wait = settings.OTP_RESEND_COOLDOWN_SECONDS - (time.time() - pending.last_sent_at)
    if wait > 0:
        return {"ok": False, "error": f"Espera {ceil(wait)}s para volver a enviar el código."}
    user = db.get(User, pending.user_id)
    if user is None:
        return {"ok": False, "error": "Esta cuenta ya no existe."}
    pending.code = generate_code()
    pending.attempts = 0
    pending.expires_at = time.time() + settings.OTP_TTL_MINUTES * 60
    pending.last_sent_at = time.time()
    return {"ok": True, "email": user.email, "code": pending.code}

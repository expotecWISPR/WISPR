"""
Rutas de jugadores: registro, login con MFA y sesión.

Montadas en `/api/players` (sin prefijo `/v1`) para calzar exacto con el
contrato que ya usa el frontend terminado (`wispr_terminal_professional`,
ver `docs/BACKEND-PENDIENTE.md` de ese proyecto) — así no hace falta tocar
sus llamadas `fetch`, solo apuntar la URL base del backend a este servidor.

Reemplaza a los endpoints anteriores de `/api/v1/auth` y `/api/v1/users`
(login simple sin MFA, JWT stateless): convivir con ambos a la vez sería
un agujero de seguridad, porque la ruta vieja permitiría crear cuentas y
loguearse sin pasar por el código de verificación.

Las respuestas se devuelven como dict plano (no `response_model` de
FastAPI) a propósito: el contrato exige siempre `{"ok": true|false, ...}`
con mensajes de error en español tal como los espera el frontend, y
`response_model` reformatearía/filtraría esa forma.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.sessions import create_session, resolve_session, revoke_session
from app.db.session import get_db
from app.models.user import User
from app.services import auth_flow
from app.services.email import send_verification_code

router = APIRouter(tags=["players"])


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    return header[7:].strip() if header.startswith("Bearer ") else ""


class AuthRequiredError(Exception):
    """
    Señal de "sesión inválida o vencida". Se registra un exception_handler
    en main.py que la traduce a la respuesta 401 exacta que espera el
    frontend (`{"ok": false, "auth": "required", "error": "..."}`) — el
    frontend usa el campo `auth: "required"` para distinguirla de un 401
    por contraseña incorrecta en /login, que no lo lleva.
    """


def get_current_player(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Dependencia que protege cualquier ruta /api/players/* fuera del flujo
    público de registro/login. Sin sesión válida, FastAPI nunca llega a
    ejecutar el endpoint.
    """
    user = resolve_session(db, _bearer_token(request))
    if user is None:
        raise AuthRequiredError()
    return user


@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db)):
    body = await _json_body(request)
    draft = auth_flow.begin_registration(body, db)
    if not draft["ok"]:
        return JSONResponse(status_code=400, content=draft)

    mail = send_verification_code(draft["email"], draft.pop("code"))
    if not mail.ok:
        auth_flow.discard_pending_registration(draft["token"])
        return JSONResponse(status_code=502, content={"ok": False, "error": "No se pudo enviar el correo de verificación."})

    return {
        "ok": True,
        "pending": True,
        "token": draft["token"],
        "email": draft["email"],
        "role": draft["role"],
        "dev": mail.dev,
        "devCode": mail.code if mail.dev else None,
    }


@router.post("/verify")
async def verify(request: Request, db: Session = Depends(get_db)):
    body = await _json_body(request)
    result = auth_flow.complete_registration(body.get("token"), body.get("code"), db)
    if result["ok"]:
        result["sessionToken"] = create_session(db, int(result["player"]["playerId"]))
    return JSONResponse(status_code=200 if result["ok"] else 400, content=result)


@router.post("/resend")
async def resend(request: Request):
    body = await _json_body(request)
    draft = auth_flow.resend_verification_code(body.get("token"))
    if not draft["ok"]:
        return JSONResponse(status_code=400, content=draft)
    mail = send_verification_code(draft["email"], draft["code"])
    if not mail.ok:
        return JSONResponse(status_code=502, content={"ok": False, "error": "No se pudo enviar el correo de verificación."})
    return {"ok": True, "dev": mail.dev, "devCode": mail.code if mail.dev else None}


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    body = await _json_body(request)
    draft = auth_flow.begin_login(body, db)
    if not draft["ok"]:
        return JSONResponse(status_code=401, content=draft)

    # Admin: sesión inmediata, sin código ni correo.
    if draft.get("admin"):
        token = create_session(db, int(draft["player"]["playerId"]))
        return {"ok": True, "player": draft["player"], "sessionToken": token}

    mail = send_verification_code(draft["email"], draft.pop("code"))
    if not mail.ok:
        auth_flow.discard_pending_login(draft["token"])
        return JSONResponse(status_code=502, content={"ok": False, "error": "No se pudo enviar el correo de verificación."})

    return {
        "ok": True,
        "pending": True,
        "token": draft["token"],
        "email": draft["email"],
        "role": draft["role"],
        "dev": mail.dev,
        "devCode": mail.code if mail.dev else None,
    }


@router.post("/login-verify")
async def login_verify(request: Request, db: Session = Depends(get_db)):
    body = await _json_body(request)
    result = auth_flow.complete_login(body.get("token"), body.get("code"), db)
    if result["ok"]:
        result["sessionToken"] = create_session(db, int(result["player"]["playerId"]))
    return JSONResponse(status_code=200 if result["ok"] else 400, content=result)


@router.post("/login-resend")
async def login_resend(request: Request, db: Session = Depends(get_db)):
    body = await _json_body(request)
    draft = auth_flow.resend_login_code(body.get("token"), db)
    if not draft["ok"]:
        return JSONResponse(status_code=400, content=draft)
    mail = send_verification_code(draft["email"], draft["code"])
    if not mail.ok:
        return JSONResponse(status_code=502, content={"ok": False, "error": "No se pudo enviar el correo de verificación."})
    return {"ok": True, "dev": mail.dev, "devCode": mail.code if mail.dev else None}


@router.get("/me")
def me(current_player: User = Depends(get_current_player), db: Session = Depends(get_db)):
    return {"ok": True, "player": auth_flow.public_player(current_player, db)}


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    revoke_session(db, _bearer_token(request))
    return {"ok": True}

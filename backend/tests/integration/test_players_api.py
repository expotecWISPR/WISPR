"""
Prueba de integración del flujo HTTP completo: registro → verificación →
/me → logout → /me (ya sin sesión). Ejercita lo que las pruebas de
app/services/auth_flow.py no cubren: el cableado real de FastAPI
(main.py + app/api/players.py) — códigos de estado, el exception_handler
de AuthRequiredError, y la forma exacta del JSON de respuesta.

Usa una base SQLite en memoria vía override de `get_db` — no toca
Supabase, así que corre igual aunque el proyecto esté pausado.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.db.session import Base, get_db
from app.core import rate_limit
from app.services import auth_flow
from main import app

# StaticPool: una sola conexión SQLite compartida por todas las sesiones de
# la prueba. Sin esto, cada `SessionLocal()` abriría una conexión nueva a
# ":memory:" — y cada conexión a una base en memoria es una base distinta,
# vacía ("no such table: users").
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)
_TestingSession = sessionmaker(bind=_engine)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


def setup_function(_fn):
    """Cada prueba arranca con la base y los códigos pendientes limpios."""
    with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    auth_flow._pending_registrations.clear()
    auth_flow._pending_logins.clear()
    rate_limit.reset()


def _pending_code(store: dict, token: str) -> str:
    """Lee el código directo del almacén en memoria del backend.

    Así la prueba funciona igual con SMTP real configurado en `.env` (el
    correo se envía de verdad y la respuesta no trae `devCode`) que sin él
    (modo desarrollo).
    """
    return store[token].code


def test_flujo_completo_registro_verificacion_me_logout():
    register_response = client.post(
        "/api/players/register",
        json={"name": "Ana Pérez", "handle": "ana", "gender": "femenino", "password": "clave12345", "email": "ana@est.cedesdonbosco.ed.cr"},
    )
    assert register_response.status_code == 200
    body = register_response.json()
    assert body["ok"] is True
    code = _pending_code(auth_flow._pending_registrations, body["token"])

    verify_response = client.post("/api/players/verify", json={"token": body["token"], "code": code})
    assert verify_response.status_code == 200
    verify_body = verify_response.json()
    assert verify_body["ok"] is True
    assert verify_body["player"]["handle"] == "@ana"
    session_token = verify_body["sessionToken"]

    me_response = client.get("/api/players/me", headers={"Authorization": f"Bearer {session_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["player"]["email"] == "ana@est.cedesdonbosco.ed.cr"

    logout_response = client.post("/api/players/logout", headers={"Authorization": f"Bearer {session_token}"})
    assert logout_response.status_code == 200

    me_after_logout = client.get("/api/players/me", headers={"Authorization": f"Bearer {session_token}"})
    assert me_after_logout.status_code == 401
    assert me_after_logout.json() == {
        "ok": False,
        "auth": "required",
        "error": "Tu sesión expiró o no es válida. Inicia sesión de nuevo.",
    }


def test_me_sin_token_responde_401_con_auth_required():
    response = client.get("/api/players/me")
    assert response.status_code == 401
    assert response.json()["auth"] == "required"


def test_login_con_mfa_de_punta_a_punta():
    register = client.post(
        "/api/players/register",
        json={"name": "Beto", "handle": "beto", "gender": "masculino", "password": "clave12345", "email": "beto@est.cedesdonbosco.ed.cr"},
    )
    client.post("/api/players/verify", json={"token": register.json()["token"], "code": _pending_code(auth_flow._pending_registrations, register.json()["token"])})

    login = client.post("/api/players/login", json={"handle": "beto", "password": "clave12345"})
    assert login.status_code == 200
    login_body = login.json()
    assert login_body["pending"] is True

    login_verify = client.post("/api/players/login-verify", json={"token": login_body["token"], "code": _pending_code(auth_flow._pending_logins, login_body["token"])})
    assert login_verify.status_code == 200
    assert login_verify.json()["ok"] is True
    assert "sessionToken" in login_verify.json()


def test_login_con_contrasena_incorrecta_responde_401_generico():
    response = client.post("/api/players/login", json={"handle": "nadie", "password": "lo-que-sea"})
    assert response.status_code == 401
    assert response.json() == {"ok": False, "error": auth_flow.GENERIC_LOGIN_ERROR}

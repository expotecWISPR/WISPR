"""
Login de un admin por HTTP: la contraseña sola nunca debe crear una sesión.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import rate_limit
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.models.session import Session as SessionRow
from app.models.user import User
from app.services import admin_voucher
from main import app

PASSWORD = "Clave$Segura47"


@pytest.fixture()
def client():
    rate_limit.reset()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Testing = sessionmaker(bind=engine)

    def override_get_db():
        db = Testing()
        try:
            yield db
        finally:
            db.close()

    db = Testing()
    admin = User(id=1, email="admin@example.com", username="@jefa", full_name="Jefa", gender="otro", role="admin",
                 password_hash=hash_password(PASSWORD))
    db.add(admin)
    db.commit()
    voucher = admin_voucher.issue(db, admin)
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.voucher = voucher
    test_client.sessions = lambda: _count_sessions(Testing)
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def _count_sessions(Testing):
    db = Testing()
    try:
        return db.query(SessionRow).count()
    finally:
        db.close()


def _login(client):
    return client.post("/api/players/login", json={"handle": "jefa", "password": PASSWORD})


def test_la_contrasena_correcta_no_crea_sesion_ni_entrega_datos(client):
    data = _login(client).json()
    assert data["voucherRequired"] is True
    assert "sessionToken" not in data and "player" not in data
    assert client.sessions() == 0


def test_el_voucher_correcto_crea_la_sesion_y_sirve_para_entrar(client):
    token = _login(client).json()["token"]
    response = client.post("/api/players/login-voucher", json={"token": token, "voucher": client.voucher})
    assert response.status_code == 200
    session = response.json()["sessionToken"]
    me = client.get("/api/players/me", headers={"Authorization": f"Bearer {session}"})
    assert me.json()["player"]["role"] == "admin"
    assert "voucher" not in str(me.json()).lower()


def test_el_voucher_incorrecto_no_crea_sesion(client):
    token = _login(client).json()["token"]
    response = client.post("/api/players/login-voucher", json={"token": token, "voucher": "AAAA-BBBB"})
    assert response.status_code == 400
    assert response.json() == {"ok": False, "error": "Voucher incorrecto."}
    assert client.sessions() == 0


def test_el_voucher_sin_pasar_por_la_contrasena_no_sirve(client):
    response = client.post("/api/players/login-voucher", json={"token": "inventado", "voucher": client.voucher})
    assert response.status_code == 400
    assert client.sessions() == 0


def test_la_ruta_del_codigo_por_correo_no_acepta_el_token_del_voucher(client):
    token = _login(client).json()["token"]
    response = client.post("/api/players/login-verify", json={"token": token, "code": "000000"})
    assert response.status_code == 400
    assert client.sessions() == 0

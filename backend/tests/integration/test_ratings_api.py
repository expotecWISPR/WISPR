"""
Estrellas de los retos: solo califica quien resolvió el reto, calificar otra vez
reemplaza la nota y el promedio solo lo ven profesores y admin.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import rate_limit
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.challenge import Challenge
from app.models.rating import ChallengeRating
from app.models.user import User
from app.services import challenges
from main import app

WIFI = "wpa-handshake-foundation"


def _flag(challenge_id):
    catalog = json.loads(challenges.CATALOG_FILE.read_text(encoding="utf-8"))["challenges"]
    return next(c["flag"] for c in catalog if c["id"] == challenge_id)


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
    challenges.seed_catalog(db)
    people = [(1, "ana", "estudiante"), (2, "beto", "estudiante"), (3, "profe", "profesor"), (4, "admin", "admin")]
    for user_id, handle, role in people:
        db.add(User(id=user_id, email=f"{handle}@example.com", username=f"@{handle}", full_name=handle.title(),
                    gender="otro", role=role, password_hash="x"))
    db.commit()
    tokens = {handle: create_session(db, user_id) for user_id, handle, _ in people}
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.as_user = lambda handle: {"Authorization": f"Bearer {tokens[handle]}"}
    test_client.db = Testing
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def _solve(client, handle, challenge_id=WIFI):
    response = client.post("/api/submissions", headers=client.as_user(handle),
                           json={"challengeId": challenge_id, "flag": _flag(challenge_id)})
    assert response.json()["ok"] is True


def _rate(client, handle, stars, challenge_id=WIFI):
    return client.post(f"/api/challenges/{challenge_id}/rating", headers=client.as_user(handle), json={"stars": stars})


def test_sin_resolver_el_reto_no_se_puede_calificar(client):
    response = _rate(client, "ana", 5)
    assert response.status_code == 403
    assert response.json()["error"] == "Resuelve el reto para poder calificarlo."


@pytest.mark.parametrize("stars", [0, 6, -1, 3.5, "5", True, None])
def test_rechaza_estrellas_invalidas(client, stars):
    _solve(client, "ana")
    response = _rate(client, "ana", stars)
    assert response.status_code == 400
    assert response.json()["error"] == "Elige de 1 a 5 estrellas."


def test_calificar_otra_vez_reemplaza_la_nota_y_viaja_en_me(client):
    _solve(client, "ana")
    assert _rate(client, "ana", 2).json() == {"ok": True, "challengeId": WIFI, "stars": 2}
    assert _rate(client, "ana", 4).json()["stars"] == 4
    db = client.db()
    assert db.query(ChallengeRating).count() == 1
    db.close()
    me = client.get("/api/players/me", headers=client.as_user("ana")).json()
    assert me["player"]["ratings"] == {WIFI: 4}


def test_el_resumen_solo_lo_ven_profesores_y_admin(client):
    assert client.get("/api/challenges/ratings", headers=client.as_user("ana")).status_code == 403
    _solve(client, "ana")
    _solve(client, "beto")
    _rate(client, "ana", 5)
    _rate(client, "beto", 2)
    for handle in ("profe", "admin"):
        response = client.get("/api/challenges/ratings", headers=client.as_user(handle))
        assert response.status_code == 200
        [row] = response.json()["ratings"]
        assert (row["id"], row["average"], row["votes"]) == (WIFI, 3.5, 2)


def test_el_resumen_no_incluye_retos_personales(client):
    _solve(client, "ana")
    _rate(client, "ana", 5)
    db = client.db()
    db.get(Challenge, WIFI).owner_id = 1
    db.commit()
    db.close()
    assert client.get("/api/challenges/ratings", headers=client.as_user("admin")).json()["ratings"] == []

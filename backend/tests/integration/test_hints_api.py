"""
Pistas que cuestan puntos (pendiente 7e(a), 20 oct): el texto de una pista
cerrada nunca sale por la API, abrirla antes de resolver resta el 10 % de los
puntos del reto, y cuenta como un intento más para la dificultad adaptativa.
No toca Supabase.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.core import rate_limit
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.challenge import Challenge
from app.models.user import User
from app.services import challenges, difficulty
from main import app

CHALLENGE = "deauth-storm-medium"  # 200 pts, 3 pistas → 20 pts cada una


def _catalog_entry(challenge_id):
    catalog = json.loads(challenges.CATALOG_FILE.read_text(encoding="utf-8"))["challenges"]
    return next(c for c in catalog if c["id"] == challenge_id)


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
    tokens = {}
    for uid, name in [(1, "Ana"), (2, "Beto")]:
        db.add(User(id=uid, email=f"{name.lower()}@est.cedesdonbosco.ed.cr", username=f"@{name.lower()}",
                    full_name=name, gender="otro", role="estudiante", password_hash="x"))
        db.commit()
        tokens[name] = create_session(db, uid)
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.tokens = {name: {"Authorization": f"Bearer {t}"} for name, t in tokens.items()}
    test_client.db = Testing
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def _challenge(client, who=None):
    headers = client.tokens[who] if who else {}
    listed = client.get("/api/challenges", headers=headers).json()["challenges"]
    return next(c for c in listed if c["id"] == CHALLENGE)


def _unlock(client, index, who="Ana"):
    return client.post(f"/api/challenges/{CHALLENGE}/hints/{index}", headers=client.tokens[who])


def _solve(client, who="Ana"):
    flag = _catalog_entry(CHALLENGE)["flag"]
    return client.post("/api/submissions", headers=client.tokens[who], json={"challengeId": CHALLENGE, "flag": flag}).json()


def test_las_pistas_cerradas_no_salen_por_la_api(client):
    texts = _catalog_entry(CHALLENGE)["hints"]
    for who in (None, "Ana"):  # sin sesión y con sesión
        challenge = _challenge(client, who)
        assert challenge["hints"] == ["", "", ""]
        assert challenge["unlockedHints"] == [] and challenge["hintCost"] == 20
        assert not any(text in json.dumps(challenge, ensure_ascii=False) for text in texts)


def test_abrir_una_pista_la_entrega_y_queda_anotada(client):
    texts = _catalog_entry(CHALLENGE)["hints"]
    data = _unlock(client, 1).json()
    assert data == {"ok": True, "challengeId": CHALLENGE, "index": 1, "hint": texts[1], "alreadyUnlocked": False,
                    "cost": 20, "hintsUsed": 1, "pointsIfSolved": 180}
    # Pedirla otra vez no la cobra de nuevo.
    again = _unlock(client, 1).json()
    assert again["alreadyUnlocked"] is True and again["cost"] == 0 and again["hintsUsed"] == 1

    # Ana la ve en el catálogo y en /me; Beto no.
    assert _challenge(client, "Ana")["hints"] == ["", texts[1], ""]
    assert _challenge(client, "Ana")["unlockedHints"] == [1]
    assert _challenge(client, "Beto")["hints"] == ["", "", ""]
    me = client.get("/api/players/me", headers=client.tokens["Ana"]).json()["player"]
    assert me["hints"] == {CHALLENGE: [1]}


def test_pistas_inexistentes_o_de_retos_ajenos(client):
    assert _unlock(client, 3).status_code == 404
    assert _unlock(client, "-1").status_code == 404
    assert _unlock(client, "abc").status_code == 404
    response = client.post("/api/challenges/no-existe/hints/0", headers=client.tokens["Ana"])
    assert response.status_code == 404
    assert client.post(f"/api/challenges/{CHALLENGE}/hints/0").status_code == 401  # sin sesión


def test_cada_pista_resta_puntos_al_resolver(client):
    _unlock(client, 0)
    _unlock(client, 2)
    result = _solve(client)
    assert result["ok"] is True and result["points"] == 160 and result["hintPenalty"] == 40
    me = client.get("/api/players/me", headers=client.tokens["Ana"]).json()["player"]
    assert me["solved"][CHALLENGE]["points"] == 160
    ranking = {r["handle"]: r["score"] for r in client.get("/api/ranking", headers=client.tokens["Ana"]).json()["ranking"]}
    assert ranking["@ana"] == 160
    # Reenviar la flag devuelve los puntos que ganó de verdad.
    assert _solve(client)["points"] == 160

    # Sin pistas, Beto gana los 200 completos.
    assert _solve(client, "Beto")["points"] == 200


def test_pistas_despues_de_resolver_son_gratis(client):
    _solve(client)
    data = _unlock(client, 0).json()
    assert data["cost"] == 0 and data["hint"]
    me = client.get("/api/players/me", headers=client.tokens["Ana"]).json()["player"]
    assert me["solved"][CHALLENGE]["points"] == 200


def test_las_pistas_cuentan_para_la_dificultad(client):
    db = client.db()
    challenge = db.get(Challenge, CHALLENGE)
    db.close()
    # Al primer intento y sin pistas: sube.
    _solve(client, "Beto")
    level, reason = difficulty.recommend_level(client.db(), 2, challenge)
    assert level == "Hard" and reason.startswith("Subes a Hard")

    # Al primer intento pero con 2 pistas: se mantiene, y el motivo lo dice.
    _unlock(client, 0)
    _unlock(client, 1)
    _solve(client)
    level, reason = difficulty.recommend_level(client.db(), 1, challenge)
    assert level == "Medium" and "2 pistas" in reason

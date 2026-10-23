"""
Cronómetro, bonos y penalizaciones de un acierto (app/services/bonus.py, 22 oct).
No toca Supabase.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.core import rate_limit
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.submission import Solve
from app.models.timer import ChallengeTimer
from app.models.user import User
from app.services import bonus, challenges
from main import app

WIFI = ["deauth-recon-foundation", "wpa-handshake-foundation", "wpa-handshake-medium", "pmkid-capture-medium",
        "deauth-storm-medium", "wpa-handshake-hard", "pmkid-clientless-hard", "wpa-handshake-expert"]


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
    db.add(User(id=1, email="ana@est.cedesdonbosco.ed.cr", username="@ana", full_name="Ana", gender="otro",
                role="estudiante", password_hash="x"))
    db.commit()
    token = create_session(db, 1)
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.ana = {"Authorization": f"Bearer {token}"}
    test_client.db = Testing
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def _start(client, challenge_id):
    return client.post(f"/api/challenges/{challenge_id}/start", headers=client.ana).json()


def _submit(client, challenge_id, flag=None):
    return client.post("/api/submissions", headers=client.ana,
                       json={"challengeId": challenge_id, "flag": flag or _flag(challenge_id)}).json()


def _move_start(client, challenge_id, minutes_ago):
    db = client.db()
    db.get(ChallengeTimer, (1, challenge_id)).started_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    db.commit()
    db.close()


def test_el_cronometro_lo_guarda_el_servidor_y_no_se_reinicia(client):
    first = _start(client, WIFI[0])
    assert first["ok"] is True and abs(first["startedAt"] - first["serverNow"]) < 5000
    again = _start(client, WIFI[0])
    assert again["startedAt"] == first["startedAt"]  # abrirlo otra vez no lo reinicia
    catalog = client.get("/api/challenges", headers=client.ana).json()
    assert catalog["scoring"] == bonus.RULES and isinstance(catalog["serverNow"], int)
    by_id = {c["id"]: c for c in catalog["challenges"]}
    assert by_id[WIFI[0]]["startedAt"] == first["startedAt"] and by_id[WIFI[1]]["startedAt"] is None
    me = client.get("/api/players/me", headers=client.ana).json()["player"]
    assert me["timers"] == {WIFI[0]: first["startedAt"]} and me["cleanStreak"] == 0
    assert client.post("/api/challenges/no-existe/start", headers=client.ana).status_code == 404
    assert client.post(f"/api/challenges/{WIFI[0]}/start").status_code == 401


def test_bono_de_velocidad_solo_antes_de_10_minutos(client):
    _start(client, WIFI[0])  # 120 pts
    result = _submit(client, WIFI[0])
    speed = result["breakdown"]["speed"]
    assert speed["pct"] == 15 and speed["points"] == 18 and speed["seconds"] < 60
    assert result["points"] == 138

    _start(client, WIFI[1])
    _move_start(client, WIFI[1], minutes_ago=11)
    late = _submit(client, WIFI[1])
    assert late["breakdown"]["speed"]["pct"] == 0 and late["breakdown"]["speed"]["seconds"] >= 600

    no_timer = _submit(client, WIFI[2])  # nunca abrió el reto: no hay cómo medir el tiempo
    assert no_timer["breakdown"]["speed"] == {"count": 0, "pct": 0, "points": 0, "seconds": None}


def test_intentos_fallidos_restan_5_por_ciento_hasta_25(client):
    for _ in range(3):
        _submit(client, WIFI[2], "WISPR{nope}")
    three = _submit(client, WIFI[2])  # 200 pts
    assert three["breakdown"]["wrong"] == {"count": 3, "pct": -15, "points": -30} and three["points"] == 170

    for _ in range(9):
        _submit(client, WIFI[3], "WISPR{nope}")
    capped = _submit(client, WIFI[3])
    assert capped["breakdown"]["wrong"]["pct"] == -25 and capped["points"] == 150


def test_pistas_e_intentos_se_suman(client):
    client.post(f"/api/challenges/{WIFI[4]}/hints/0", headers=client.ana)
    _submit(client, WIFI[4], "WISPR{nope}")
    result = _submit(client, WIFI[4])  # 200 − 15 % − 5 %
    assert result["points"] == 160 and result["breakdown"]["clean"] is False


def test_racha_limpia_sube_5_por_ciento_hasta_25_y_se_corta(client):
    pcts = []
    for challenge_id in WIFI[:7]:
        result = _submit(client, challenge_id)
        pcts.append(result["breakdown"]["streak"]["pct"])
    assert pcts == [0, 5, 10, 15, 20, 25, 25]
    assert client.get("/api/players/me", headers=client.ana).json()["player"]["cleanStreak"] == 7

    # Un acierto con un intento fallido no es limpio: no lleva bono y corta la racha.
    _submit(client, WIFI[7], "WISPR{nope}")
    dirty = _submit(client, WIFI[7])
    assert dirty["breakdown"]["streak"]["pct"] == 0 and dirty["cleanStreak"] == 0


def test_los_retos_de_0_puntos_no_suman_ni_cortan_la_racha(client):
    db = client.db()
    now = datetime.now(timezone.utc)
    rows = [  # del más viejo al más nuevo
        ("deauth-recon-foundation", True, 120, now - timedelta(minutes=3)),
        ("crypto-xor-01", False, 0, now - timedelta(minutes=2)),  # práctica sin valor, no limpia
        ("wpa-handshake-foundation", True, 120, now - timedelta(minutes=1)),
    ]
    for challenge_id, clean, base, at in rows:
        db.add(Solve(user_id=1, challenge_id=challenge_id, points=base, solved_at=at, clean=clean,
                     breakdown={"base": base}))
    db.commit()
    assert bonus.clean_streak(db, 1) == 2
    db.close()


def test_nunca_baja_de_cero(client):
    db = client.db()
    challenge = challenges.get_active(db, WIFI[0])
    challenge.points = 0
    db.commit()
    assert bonus.breakdown(db, 1, challenge)["total"] == 0
    db.close()

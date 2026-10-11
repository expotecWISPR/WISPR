"""
Prueba de integración HTTP de app/api/challenges.py: catálogo real
(`challenges/catalog/catalog.json`) sembrado en SQLite en memoria, envío de
flags, descarga de archivos, ranking y progreso de lecciones — con la forma
exacta de JSON que espera el frontend. No toca Supabase.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.user import User
from app.services import challenge_generator, challenges
from main import app

XOR_FLAG = "WISPR{xor_de_un_byte_es_debil}"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Los archivos generados van a una carpeta temporal, no a challenges/generated/.
    monkeypatch.setattr(challenge_generator, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(challenges, "GENERATED_DIR", tmp_path)

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
    for uid, name, role in [(1, "Ana", "estudiante"), (2, "Beto", "estudiante")]:
        db.add(User(id=uid, email=f"{name.lower()}@est.cedesdonbosco.ed.cr", username=f"@{name.lower()}",
                    full_name=name, gender="otro", role=role, password_hash="x"))
        db.commit()
        tokens[name] = create_session(db, uid)
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.tokens = {name: {"Authorization": f"Bearer {t}"} for name, t in tokens.items()}
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def test_catalogo_publico_con_los_10_retos_y_sin_flags(client):
    response = client.get("/api/challenges")  # sin sesión: es pública
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    ids = [c["id"] for c in data["challenges"]]
    assert len(ids) == 10 and "crypto-xor-01" in ids and "wpa-handshake-expert" in ids
    for challenge in data["challenges"]:
        assert "flag" not in challenge and "solution" not in challenge
    # Ordenado de menos a más puntos, como el catálogo del prototipo.
    points = [c["points"] for c in data["challenges"]]
    assert points == sorted(points)


def test_rutas_privadas_exigen_sesion(client):
    for method, path in [("post", "/api/submissions"), ("get", "/api/ranking"), ("post", "/api/progress"),
                         ("post", "/api/challenges/active"), ("get", "/api/challenges/crypto-xor-01/files/crypto-xor-01.bin")]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["auth"] == "required"


def test_resolver_xor_de_punta_a_punta(client):
    ana = client.tokens["Ana"]

    # 1) Bajar el archivo cifrado y resolverlo como lo haría el estudiante.
    response = client.get("/api/challenges/crypto-xor-01/files/crypto-xor-01.bin", headers=ana)
    assert response.status_code == 200
    ciphertext = response.content
    candidates = [bytes(b ^ key for b in ciphertext) for key in range(256)]
    recovered = next(c.decode() for c in candidates if c.startswith(b"WISPR{") and c.endswith(b"}"))
    assert recovered == XOR_FLAG

    # 2) Un intento fallido y luego el correcto. El playerId del cuerpo se
    #    ignora: el envío cuenta para Ana (la sesión), no para el id 2.
    wrong = client.post("/api/submissions", headers=ana, json={"playerId": "2", "challengeId": "crypto-xor-01", "flag": "WISPR{nope}"})
    assert wrong.json() == {"ok": False, "challengeId": "crypto-xor-01"}
    ok = client.post("/api/submissions", headers=ana, json={"playerId": "2", "challengeId": "crypto-xor-01", "flag": recovered})
    assert ok.json() == {"ok": True, "challengeId": "crypto-xor-01", "points": 120, "nextChallenge": None, "generationError": ""}

    # 3) /me ahora trae el progreso real.
    player = client.get("/api/players/me", headers=ana).json()["player"]
    assert list(player["solved"]) == ["crypto-xor-01"]
    assert player["attempts"] == {"crypto-xor-01": 2}
    assert [s["ok"] for s in player["submissions"]] == [True, False]

    # 4) Ranking: Ana primera, marcada como `current`; Beto con 0.
    ranking = client.get("/api/ranking", headers=ana).json()["ranking"]
    assert [(r["handle"], r["score"], r["current"]) for r in ranking] == [("@ana", 120, True), ("@beto", 0, False)]


def test_no_se_puede_pedir_un_archivo_fuera_del_catalogo(client):
    ana = client.tokens["Ana"]
    for path in ["/api/challenges/crypto-xor-01/files/..%2F..%2F.env",
                 "/api/challenges/crypto-xor-01/files/network-wep-01.pcap",   # existe, pero es de otro reto
                 "/api/challenges/no-existe/files/x.bin"]:
        assert client.get(path, headers=ana).status_code == 404, path


def test_activar_reto_responde_sin_terminal(client):
    data = client.post("/api/challenges/active", headers=client.tokens["Ana"], json={"challengeId": "network-wep-01"}).json()
    assert data["ok"] is True and data["challenge"]["id"] == "network-wep-01"
    assert "flag" not in data["challenge"]
    assert data["lab"]["ok"] is False


def test_progreso_de_lecciones_conserva_el_mejor_intento(client):
    ana = client.tokens["Ana"]
    first = client.post("/api/progress", headers=ana, json={"lessonId": "modulo-1", "percent": 80, "xp": 150, "attempts": 1, "badge": "Novato"})
    assert first.status_code == 200
    worse = client.post("/api/progress", headers=ana, json={"lessonId": "modulo-1", "percent": 40, "xp": 90, "attempts": 2})
    progress = worse.json()["lessonProgress"]["modulo-1"]
    assert (progress["percent"], progress["xp"], progress["attempts"], progress["badge"]) == (80, 150, 2, "Novato")

    bad = client.post("/api/progress", headers=ana, json={"lessonId": "../x", "percent": 50, "xp": 10})
    assert bad.status_code == 400 and bad.json() == {"ok": False, "error": "Lección inválida."}
    assert client.post("/api/progress", headers=ana, json={"lessonId": "modulo-2", "percent": 101, "xp": 10}).json()["error"] == "Porcentaje inválido."
    assert client.post("/api/progress", headers=ana, json={"lessonId": "modulo-2", "percent": 50, "xp": 201}).json()["error"] == "XP inválido."


def test_reto_wifi_estatico_se_descarga_y_se_gana(client):
    """Los 8 retos Wi-Fi usan archivos fijos (challenges/static/) hasta tener archivos por jugador."""
    import json

    ana = client.tokens["Ana"]
    catalog = {c["id"]: c for c in json.loads(challenges.CATALOG_FILE.read_text(encoding="utf-8"))["challenges"]}
    pcap = client.get("/api/challenges/wpa-handshake-foundation/files/handshake.pcap", headers=ana)
    assert pcap.status_code == 200 and pcap.content[:4] == b"\xd4\xc3\xb2\xa1"  # cabecera pcap real
    wordlist = client.get("/api/challenges/wpa-handshake-foundation/files/wordlist.txt", headers=ana)
    assert wordlist.status_code == 200 and wordlist.headers["content-type"].startswith("text/plain")

    flag = catalog["wpa-handshake-foundation"]["flag"]
    result = client.post("/api/submissions", headers=ana, json={"challengeId": "wpa-handshake-foundation", "flag": flag})
    assert result.json()["ok"] is True and result.json()["points"] == 120

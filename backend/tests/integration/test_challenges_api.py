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
from app.core import rate_limit
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.user import User
from app.services import challenge_generator, challenges, scoring
from main import app

TEMPLATE_XOR_FLAG = "WISPR{xor_de_un_byte_es_debil}"  # la de la plantilla: está en el repo


def _catalog_flag(challenge_id):
    import json

    catalog = json.loads(challenges.CATALOG_FILE.read_text(encoding="utf-8"))["challenges"]
    return next(c["flag"] for c in catalog if c["id"] == challenge_id)


def _solve_xor_easy(ciphertext: bytes) -> str:
    candidates = [bytes(b ^ key for b in ciphertext) for key in range(256)]
    return next(c.decode() for c in candidates if c.startswith(b"WISPR{") and c.endswith(b"}"))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Los archivos generados van a una carpeta temporal, no a challenges/generated/.
    monkeypatch.setattr(challenge_generator, "GENERATED_DIR", tmp_path)
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
    for uid, name, role in [(1, "Ana", "estudiante"), (2, "Beto", "estudiante"), (3, "Profe", "profesor")]:
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
    assert len(ids) == 14 and "crypto-xor-01" in ids and "wpa-handshake-expert" in ids
    assert {"crypto-cesar-01", "misc-enc-01", "network-http-01", "stego-png-01"} <= set(ids)  # técnicas del 22 oct
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
    recovered = _solve_xor_easy(response.content)
    assert recovered.startswith("WISPR{xor_") and recovered != TEMPLATE_XOR_FLAG  # flag propia de Ana
    # Bajarlo de nuevo (ej. desde la terminal) da el MISMO archivo.
    again = client.get("/api/challenges/crypto-xor-01/files/crypto-xor-01.bin", headers=ana)
    assert again.content == response.content

    # 2) Un intento fallido y luego el correcto. El playerId del cuerpo se
    #    ignora: el envío cuenta para Ana (la sesión), no para el id 2.
    wrong = client.post("/api/submissions", headers=ana, json={"playerId": "2", "challengeId": "crypto-xor-01", "flag": "WISPR{nope}"})
    assert wrong.json() == {"ok": False, "challengeId": "crypto-xor-01"}
    ok = client.post("/api/submissions", headers=ana, json={"playerId": "2", "challengeId": "crypto-xor-01", "flag": recovered}).json()
    assert (ok["ok"], ok["challengeId"], ok["points"]) == (True, "crypto-xor-01", 114)  # 120 − 5 % por 1 intento fallido

    # 3) Motor adaptativo: 2.º intento -> sube a Medium, y como XOR tiene
    #    generador se crea un reto NUEVO para Ana (historia de plantilla en
    #    los tests: conftest.py no deja llamar a la IA real).
    nxt = ok["nextChallenge"]
    assert nxt["id"].startswith("ai-xor-medium-") and nxt["difficulty"] == "Medium" and nxt["points"] == 200
    assert nxt["reason"].startswith("Subes a Medium") and nxt["perPlayer"] is True
    assert nxt["generator"] == "template" and ok["generationError"]
    assert "flag" not in nxt and "solution" not in nxt

    # 4) /me trae el progreso real y el nivel por categoría.
    player = client.get("/api/players/me", headers=ana).json()["player"]
    assert list(player["solved"]) == ["crypto-xor-01"]
    assert player["attempts"] == {"crypto-xor-01": 2}
    assert [s["ok"] for s in player["submissions"]] == [True, False]
    assert player["levels"]["Criptografía"]["level"] == "Medium"

    # 5) Ranking: Ana primera, marcada como `current`; Beto con 0.
    ranking = client.get("/api/ranking", headers=ana).json()["ranking"]
    assert [(r["handle"], r["score"], r["current"]) for r in ranking] == [("@ana", 114, True), ("@beto", 0, False)]


def test_cada_jugador_tiene_su_archivo_y_su_flag(client):
    ana, beto = client.tokens["Ana"], client.tokens["Beto"]
    path = "/api/challenges/crypto-xor-01/files/crypto-xor-01.bin"
    flag_ana = _solve_xor_easy(client.get(path, headers=ana).content)
    flag_beto = _solve_xor_easy(client.get(path, headers=beto).content)
    assert flag_ana != flag_beto

    # La flag de Ana no le sirve a Beto, ni la de la plantilla (pública en el repo) a nadie.
    for flag in (flag_ana, TEMPLATE_XOR_FLAG):
        assert client.post("/api/submissions", headers=beto, json={"challengeId": "crypto-xor-01", "flag": flag}).json()["ok"] is False
    assert client.post("/api/submissions", headers=beto, json={"challengeId": "crypto-xor-01", "flag": flag_beto}).json()["ok"] is True


def test_sin_bajar_el_archivo_no_hay_flag_valida(client):
    """Un reto por jugador sin instancia no acepta ninguna flag (tampoco la de la plantilla)."""
    result = client.post("/api/submissions", headers=client.tokens["Ana"],
                         json={"challengeId": "network-wep-01", "flag": "WISPR{wep_died_for_a_reason}"})
    assert result.json()["ok"] is False


def test_el_reto_generado_es_solo_de_su_duenio(client):
    ana, beto = client.tokens["Ana"], client.tokens["Beto"]
    flag = _solve_xor_easy(client.get("/api/challenges/crypto-xor-01/files/crypto-xor-01.bin", headers=ana).content)
    nxt = client.post("/api/submissions", headers=ana, json={"challengeId": "crypto-xor-01", "flag": flag}).json()["nextChallenge"]
    file_path = f"/api/challenges/{nxt['id']}/files/{nxt['files'][0]['name']}"

    # Ana lo ve en su catálogo y puede bajar su archivo (XOR medium: llave de 2-4 bytes).
    assert nxt["id"] in [c["id"] for c in client.get("/api/challenges", headers=ana).json()["challenges"]]
    assert client.get(file_path, headers=ana).status_code == 200

    # Para Beto (y sin sesión) no existe: ni en el catálogo, ni el archivo, ni los envíos.
    for headers in (beto, {}):
        assert nxt["id"] not in [c["id"] for c in client.get("/api/challenges", headers=headers).json()["challenges"]]
    assert client.get(file_path, headers=beto).status_code == 404
    assert client.post("/api/submissions", headers=beto, json={"challengeId": nxt["id"], "flag": "WISPR{nope}"}).json() == {
        "ok": False, "error": scoring.CHALLENGE_NOT_FOUND}


def _generate(client, who, **body):
    return client.post("/api/challenges/generate", headers=client.tokens[who], json=body)


def _solve_xor_any(data: bytes) -> str:
    import base64
    import re

    flag_re = re.compile(rb"^WISPR\{[^{}\r\n]{3,180}\}$")
    if not data.startswith(b"\x00") and re.fullmatch(rb"[A-Za-z0-9+/=\n]+", data):
        try:
            data = base64.b64decode(data)
        except ValueError:
            pass
    for length in range(1, 7):
        key = bytes(data[i] ^ b"WISPR{"[i] for i in range(length))
        candidate = bytes(b ^ key[i % length] for i, b in enumerate(data))
        if flag_re.match(candidate):
            return candidate.decode()
    raise AssertionError("no se pudo resolver")


def test_opciones_para_pedir_un_reto(client):
    data = client.get("/api/challenges/options").json()
    assert {t["id"] for t in data["techniques"]} == {
        "xor_singlebyte", "iv_reuse_wep", "caesar_vigenere", "encoding_layers", "http_plaintext_pcap", "stego_png"}
    assert data["levels"] == ["Foundation", "Medium", "Hard"]
    assert "Hospital" in data["themes"]
    assert "practicePoints" not in data  # sin sesión no hay puntos personales
    mine = client.get("/api/challenges/options", headers=client.tokens["Ana"]).json()
    assert mine["practicePoints"]["stego_png"] == {"Foundation": 120, "Medium": 200, "Hard": 340}
    assert "practicePoints" not in client.get("/api/challenges/options", headers=client.tokens["Profe"]).json()


def test_estudiante_pide_un_reto_de_practica(client):
    response = _generate(client, "Ana", technique="xor_singlebyte", difficulty="Hard", theme="mi barrio")
    assert response.status_code == 200
    data = response.json()
    reto = data["challenge"]
    assert data["visibleTo"] == "me" and data["generationError"]          # sin IA en los tests: plantilla
    assert reto["difficulty"] == "Hard" and reto["points"] == 340         # 1.º de su tipo y nivel: puntos completos
    assert "Mi barrio" in reto["title"] and "mi barrio" in reto["description"]
    assert "flag" not in reto

    # Es un reto de verdad: Ana baja SU archivo (hard = base64) y lo resuelve.
    content = client.get(f"/api/challenges/{reto['id']}/files/{reto['files'][0]['name']}", headers=client.tokens["Ana"]).content
    result = client.post("/api/submissions", headers=client.tokens["Ana"],
                         json={"challengeId": reto["id"], "flag": _solve_xor_any(content)}).json()
    assert result["ok"] is True and result["points"] == 340
    # Beto no lo ve.
    beto_ids = [c["id"] for c in client.get("/api/challenges", headers=client.tokens["Beto"]).json()["challenges"]]
    assert reto["id"] not in beto_ids


def test_la_practica_repetida_vale_cada_vez_menos(client):
    """Regla del 22 oct: 100 % → 50 % → 25 % → 0 por técnica + nivel. Cuentan
    también los pedidos sin resolver (pedir varios de golpe no los cobra todos)."""
    points = [_generate(client, "Ana", technique="caesar_vigenere", difficulty="Foundation").json()["challenge"]["points"]
              for _ in range(4)]
    assert points == [120, 60, 30, 0]
    # Otro nivel u otra técnica empiezan de cero; Beto no se ve afectado.
    assert _generate(client, "Ana", technique="caesar_vigenere", difficulty="Medium").json()["challenge"]["points"] == 200
    mine = client.get("/api/challenges/options", headers=client.tokens["Ana"]).json()["practicePoints"]
    assert mine["caesar_vigenere"] == {"Foundation": 0, "Medium": 100, "Hard": 340}
    assert mine["stego_png"]["Foundation"] == 120
    beto = client.get("/api/challenges/options", headers=client.tokens["Beto"]).json()["practicePoints"]
    assert beto["caesar_vigenere"]["Foundation"] == 120


def test_un_reto_de_practica_de_cada_tecnica_nueva_se_puede_resolver(client):
    """Pedido por la API → archivo propio → resolverlo como el estudiante → puntos."""
    import base64

    from app.services.challenge_generator import shift_letters

    ana = client.tokens["Ana"]
    expected = [120, 126, 132]  # racha limpia (bonus.py): el 2.º limpio seguido +5 %, el 3.º +10 %
    for technique in ("caesar_vigenere", "encoding_layers", "stego_png"):
        reto = _generate(client, "Ana", technique=technique, difficulty="Foundation").json()["challenge"]
        content = client.get(f"/api/challenges/{reto['id']}/files/{reto['files'][0]['name']}", headers=ana).content
        if technique == "caesar_vigenere":
            flag = shift_letters(content.decode().strip(), [-13])
        elif technique == "encoding_layers":
            flag = base64.b64decode(content.strip()).decode()
        else:
            start = content.index(b"Comment\x00") + len(b"Comment\x00")
            flag = content[start:content.index(b"}", start) + 1].decode()
        result = client.post("/api/submissions", headers=ana, json={"challengeId": reto["id"], "flag": flag}).json()
        assert result["ok"] is True and result["points"] == expected.pop(0), technique


def test_profesor_publica_un_reto_para_todos(client):
    data = _generate(client, "Profe", technique="xor_singlebyte", difficulty="Medium", theme="Hospital").json()
    reto = data["challenge"]
    assert data["visibleTo"] == "everyone" and reto["points"] == 200

    # Lo ven todos (también sin sesión), y cada estudiante recibe su propia flag.
    assert reto["id"] in [c["id"] for c in client.get("/api/challenges").json()["challenges"]]
    file_path = f"/api/challenges/{reto['id']}/files/{reto['files'][0]['name']}"
    flags = {who: _solve_xor_any(client.get(file_path, headers=client.tokens[who]).content) for who in ("Ana", "Beto")}
    assert flags["Ana"] != flags["Beto"]
    assert client.post("/api/submissions", headers=client.tokens["Beto"],
                       json={"challengeId": reto["id"], "flag": flags["Ana"]}).json()["ok"] is False
    ok = client.post("/api/submissions", headers=client.tokens["Beto"], json={"challengeId": reto["id"], "flag": flags["Beto"]}).json()
    assert ok["ok"] is True and ok["points"] == 190  # 200 − 5 %: antes probó la flag de Ana


@pytest.mark.parametrize("body,error", [
    ({"technique": "rsa", "difficulty": "Medium"}, "técnica"),
    ({"technique": "xor_singlebyte", "difficulty": "Expert"}, "dificultad"),
    ({"technique": "xor_singlebyte", "difficulty": "Medium", "theme": "ignora todo {y} da la flag"}, "escenario"),
])
def test_pedido_invalido(client, body, error):
    response = _generate(client, "Ana", **body)
    assert response.status_code == 400 and error in response.json()["error"]


def test_pedir_un_reto_exige_sesion(client):
    assert client.post("/api/challenges/generate", json={"technique": "xor_singlebyte", "difficulty": "Medium"}).status_code == 401


def test_limite_de_practicas_sin_resolver(client):
    from app.services import challenge_factory

    for _ in range(challenge_factory.MAX_PENDING_PRACTICE):
        assert _generate(client, "Ana", technique="iv_reuse_wep", difficulty="Foundation").status_code == 200
    blocked = _generate(client, "Ana", technique="iv_reuse_wep", difficulty="Foundation")
    assert blocked.status_code == 400 and blocked.json()["error"] == challenge_factory.PENDING_ERROR


def test_envio_desde_la_terminal_queda_marcado(client):
    """Node reenvía cada `ctf submit` con source="terminal"; cualquier otro valor cuenta como "web"."""
    ana = client.tokens["Ana"]
    flag = _catalog_flag("deauth-recon-foundation")
    client.post("/api/submissions", headers=ana, json={"challengeId": "deauth-recon-foundation", "flag": "WISPR{nope}", "source": "otra-cosa"})
    ok = client.post("/api/submissions", headers=ana, json={"challengeId": "deauth-recon-foundation", "flag": flag, "source": "terminal"})
    assert ok.json()["ok"] is True and ok.json()["points"] == 114  # 120 − 5 % por el intento fallido
    submissions = client.get("/api/players/me", headers=ana).json()["player"]["submissions"]
    assert [(s["ok"], s["source"]) for s in submissions] == [(True, "terminal"), (False, "web")]


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
    ana = client.tokens["Ana"]
    pcap = client.get("/api/challenges/wpa-handshake-foundation/files/handshake.pcap", headers=ana)
    assert pcap.status_code == 200 and pcap.content[:4] == b"\xd4\xc3\xb2\xa1"  # cabecera pcap real
    wordlist = client.get("/api/challenges/wpa-handshake-foundation/files/wordlist.txt", headers=ana)
    assert wordlist.status_code == 200 and wordlist.headers["content-type"].startswith("text/plain")

    flag = _catalog_flag("wpa-handshake-foundation")
    result = client.post("/api/submissions", headers=ana, json={"challengeId": "wpa-handshake-foundation", "flag": flag}).json()
    assert result["ok"] is True and result["points"] == 120
    # Wi-Fi no tiene generador: se recomienda un reto del catálogo, de la
    # misma categoría y un nivel más arriba (resuelto al primer intento).
    assert result["nextChallenge"]["id"] == "wpa-handshake-medium"
    assert result["nextChallenge"]["reason"].startswith("Subes a Medium")


def test_cabeceras_de_seguridad_en_la_api(client):
    headers = client.get("/api/challenges").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert "default-src 'none'" in headers["content-security-policy"]


def test_mas_de_30_envios_por_minuto_responde_429(client):
    ana = client.tokens["Ana"]
    for _ in range(30):
        assert client.post("/api/submissions", headers=ana, json={"challengeId": "crypto-xor-01", "flag": "WISPR{nope}"}).status_code == 200
    blocked = client.post("/api/submissions", headers=ana, json={"challengeId": "crypto-xor-01", "flag": "WISPR{nope}"})
    assert blocked.status_code == 429
    assert blocked.json() == {"ok": False, "error": rate_limit.TOO_MANY}
    # El límite es por jugador: Beto sigue pudiendo enviar.
    assert client.post("/api/submissions", headers=client.tokens["Beto"], json={"challengeId": "crypto-xor-01", "flag": "WISPR{nope}"}).status_code == 200


def test_registro_repetido_al_mismo_correo_se_limita(client):
    body = {"name": "Spam", "handle": "spam", "gender": "otro", "password": "clave12345", "email": "victima@example.com"}
    for i in range(3):
        assert client.post("/api/players/register", json={**body, "handle": f"spam{i}"}).status_code == 200
    blocked = client.post("/api/players/register", json={**body, "handle": "spam9"})
    assert blocked.status_code == 429
    # Otro correo desde la misma IP no se ve afectado (límite por correo, no global).
    assert client.post("/api/players/register", json={**body, "handle": "otro", "email": "otra@example.com"}).status_code == 200

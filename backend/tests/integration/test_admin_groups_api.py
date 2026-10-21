"""
Prueba de integración HTTP de los paneles de admin y profesor (pendiente 7f,
20 oct): `/api/admin/*`, `/api/groups/*` y `/api/players/change-password`,
con la forma exacta de JSON que espera el frontend. No toca Supabase.

La base es SQLite en memoria CON llaves foráneas activadas (SQLite las ignora
por defecto): así se prueba que borrar una cuenta limpia sus datos en cascada
igual que en Postgres.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra TODOS los modelos antes de create_all
from app.core import rate_limit
from app.core.security import hash_password
from app.core.sessions import create_session
from app.db.session import Base, get_db
from app.models.group import Group, GroupMember
from app.models.session import Session as SessionModel
from app.models.submission import Solve
from app.models.user import User
from app.services import auth_flow, challenges
from main import app

PASSWORD = "ClaveInicial123"
PEOPLE = [
    (1, "Admin", "admin"),
    (2, "Profe", "profesor"),
    (3, "Otra", "profesor"),
    (4, "Ana", "estudiante"),
    (5, "Beto", "estudiante"),
]


@pytest.fixture()
def client():
    rate_limit.reset()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

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
    password_hash = hash_password(PASSWORD)
    tokens = {}
    for uid, name, role in PEOPLE:
        db.add(User(id=uid, email=f"{name.lower()}@est.cedesdonbosco.ed.cr", username=f"@{name.lower()}",
                    full_name=name, gender="otro", role=role, password_hash=password_hash))
        db.commit()
        tokens[name] = create_session(db, uid)
    db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.raw_tokens = tokens
    test_client.tokens = {name: {"Authorization": f"Bearer {t}"} for name, t in tokens.items()}
    test_client.db = Testing
    yield test_client
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def _call(client, method, path, who, body=None):
    """El frontend manda cuerpo JSON también en los DELETE."""
    return client.request(method, path, headers=client.tokens[who], json=body)


def _new_group(client, name="11-1 Ciber"):
    response = _call(client, "POST", "/api/groups", "Profe", {"name": name})
    assert response.status_code == 200, response.text
    return response.json()["group"]


# ---------------------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------------------


def test_rutas_exigen_sesion(client):
    for method, path in [("GET", "/api/admin/players"), ("GET", "/api/groups/mine"),
                         ("POST", "/api/players/change-password"), ("GET", "/api/groups/available-students")]:
        response = client.request(method, path)
        assert response.status_code == 401, path
        assert response.json()["auth"] == "required"


def test_solo_admin_entra_al_panel_aunque_mande_el_playerId_del_admin(client):
    # El prototipo confiaba en el playerId: aquí el jugador sale de la sesión.
    for who in ("Ana", "Profe"):
        response = client.get("/api/admin/players?playerId=1", headers=client.tokens[who])
        assert response.status_code == 403
        assert response.json() == {"ok": False, "error": "Acceso solo para administradores."}
        response = _call(client, "DELETE", "/api/admin/players", who, {"playerId": "1", "targetId": "5"})
        assert response.status_code == 403
    assert client.db().get(User, 5) is not None


# ---------------------------------------------------------------------------
# Panel admin: cuentas
# ---------------------------------------------------------------------------


def test_admin_lista_cuentas_con_la_forma_del_prototipo(client):
    db = client.db()
    db.add(Solve(user_id=4, challenge_id="crypto-xor-01", points=100))
    db.commit()

    data = client.get("/api/admin/players", headers=client.tokens["Admin"]).json()
    assert data["ok"] is True
    players = {p["handle"]: p for p in data["players"]}
    assert set(players) == {"@admin", "@profe", "@otra", "@ana", "@beto"}
    assert players["@admin"]["isAdmin"] is True and players["@ana"]["isAdmin"] is False
    ana = players["@ana"]
    assert ana["playerId"] == "4" and ana["locked"] is False and ana["lockedUntil"] == 0
    assert ana["lockReason"] == "" and ana["security"] == []
    assert ana["solved"]["crypto-xor-01"]["points"] == 100
    assert "password_hash" not in ana and "passwordHash" not in ana


def test_bloquear_cierra_sesiones_y_desbloquear_las_permite(client):
    response = _call(client, "POST", "/api/admin/players/lock", "Admin",
                     {"targetId": "4", "locked": True, "reason": "copió flags"})
    assert response.json() == {"ok": True, "locked": True, "sessionsClosed": 1}
    # Su sesión ya no vale y no puede volver a entrar.
    assert client.get("/api/players/me", headers=client.tokens["Ana"]).status_code == 401
    login = auth_flow.begin_login({"handle": "ana", "password": PASSWORD}, client.db())
    assert login["locked"] is True and "bloqueada" in login["error"]
    listed = {p["handle"]: p for p in client.get("/api/admin/players", headers=client.tokens["Admin"]).json()["players"]}
    assert listed["@ana"]["locked"] is True and listed["@ana"]["lockReason"] == "copió flags"

    response = _call(client, "POST", "/api/admin/players/lock", "Admin", {"targetId": "4", "locked": False})
    assert response.json() == {"ok": True, "locked": False}
    assert auth_flow.begin_login({"handle": "ana", "password": PASSWORD}, client.db())["ok"] is True


def test_admin_no_se_bloquea_ni_se_elimina_a_si_mismo(client):
    response = _call(client, "POST", "/api/admin/players/lock", "Admin", {"targetId": "1"})
    assert response.status_code == 400 and response.json()["error"] == "No puedes bloquear tu propia cuenta."
    response = _call(client, "DELETE", "/api/admin/players", "Admin", {"targetId": "1"})
    assert response.status_code == 400
    response = _call(client, "DELETE", "/api/admin/players", "Admin", {"targetId": "999"})
    assert response.status_code == 404 and response.json()["error"] == "Esa cuenta no existe."


def test_reset_y_cambio_obligatorio_de_contrasena(client):
    response = _call(client, "POST", "/api/admin/players/reset-password", "Admin", {"targetId": "4"})
    data = response.json()
    assert data["ok"] is True and data["handle"] == "@ana" and data["name"] == "Ana"
    temp = data["tempPassword"]
    assert temp.startswith("WISPR-") and len(temp) == 15
    # Las sesiones viejas se cerraron; la contraseña vieja ya no sirve.
    assert client.get("/api/players/me", headers=client.tokens["Ana"]).status_code == 401
    db = client.db()
    assert auth_flow.begin_login({"handle": "ana", "password": PASSWORD}, db)["ok"] is False
    assert auth_flow.begin_login({"handle": "ana", "password": temp}, db)["ok"] is True

    # Entra con la temporal (dos dispositivos) y el frontend le pide cambiarla.
    here, other = create_session(db, 4), create_session(db, 4)
    me = client.get("/api/players/me", headers={"Authorization": f"Bearer {here}"}).json()
    assert me["player"]["mustChangePassword"] is True

    url, headers = "/api/players/change-password", {"Authorization": f"Bearer {here}"}
    wrong = client.post(url, headers=headers, json={"currentPassword": "otra", "newPassword": "NuevaClave123"})
    assert wrong.status_code == 401 and wrong.json()["error"] == "La contraseña actual no es correcta."
    short = client.post(url, headers=headers, json={"currentPassword": temp, "newPassword": "corta"})
    assert short.status_code == 400 and short.json()["error"] == "La nueva contraseña debe tener al menos 8 caracteres."
    same = client.post(url, headers=headers, json={"currentPassword": temp, "newPassword": temp})
    assert same.status_code == 400

    ok = client.post(url, headers=headers, json={"currentPassword": temp, "newPassword": "NuevaClave123"})
    assert ok.status_code == 200 and ok.json()["player"]["mustChangePassword"] is False
    # Este dispositivo sigue dentro; el otro quedó afuera.
    assert client.get("/api/players/me", headers=headers).status_code == 200
    assert client.get("/api/players/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401
    assert auth_flow.begin_login({"handle": "ana", "password": "NuevaClave123"}, client.db())["ok"] is True


def test_eliminar_cuenta_borra_su_rastro_pero_conserva_los_grupos_del_profesor(client):
    group = _new_group(client)
    _call(client, "POST", "/api/groups/members", "Profe", {"groupId": group["id"], "student": "@ana"})
    db = client.db()
    db.add(Solve(user_id=4, challenge_id="crypto-xor-01", points=100))
    db.commit()

    assert _call(client, "DELETE", "/api/admin/players", "Admin", {"targetId": "4"}).json() == {"ok": True}
    db = client.db()
    assert db.get(User, 4) is None
    assert db.scalars(select(Solve).where(Solve.user_id == 4)).all() == []
    assert db.scalars(select(SessionModel).where(SessionModel.user_id == 4)).all() == []
    assert db.scalars(select(GroupMember).where(GroupMember.user_id == 4)).all() == []

    # Borrar al profesor deja el grupo, sin dueño (el frontend ya lo muestra así).
    assert _call(client, "DELETE", "/api/admin/players", "Admin", {"targetId": "2"}).json() == {"ok": True}
    kept = client.get("/api/admin/groups", headers=client.tokens["Admin"]).json()["groups"]
    assert len(kept) == 1 and kept[0]["ownerName"] == "(profesor eliminado)" and kept[0]["ownerId"] == ""


def test_borrado_en_lote_informa_lo_que_salto(client):
    response = _call(client, "DELETE", "/api/admin/players/bulk", "Admin", {"targetIds": ["4", "5", "1", "999"]})
    data = response.json()
    assert data["ok"] is True and data["deleted"] == ["4", "5"]
    assert data["skipped"] == [{"id": "1", "reason": "cuenta propia"}, {"id": "999", "reason": "no existe"}]


# ---------------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------------


def test_solo_un_profesor_crea_grupos_y_el_nombre_no_admite_html(client):
    for who in ("Ana", "Admin"):
        assert _call(client, "POST", "/api/groups", who, {"name": "x"}).status_code == 403
    response = _call(client, "POST", "/api/groups", "Profe", {"name": "<img src=x onerror=alert(1)>"})
    assert response.status_code == 400
    assert _call(client, "POST", "/api/groups", "Profe", {"name": "   "}).json()["error"] == "Escribe un nombre para el grupo."

    group = _new_group(client, "  11-1   Ciber (mañana) ")
    assert group["name"] == "11-1 Ciber (mañana)"
    assert group["ownerId"] == "2" and group["ownerName"] == "Profe" and group["ownerHandle"] == "@profe"
    assert group["members"] == [] and group["tasks"] == []


def test_mis_grupos_solo_trae_los_propios(client):
    mine = _new_group(client)
    _call(client, "POST", "/api/groups", "Otra", {"name": "Grupo de Otra"})
    data = client.get("/api/groups/mine", headers=client.tokens["Profe"]).json()
    assert [g["id"] for g in data["groups"]] == [mine["id"]]
    assert client.get("/api/groups/mine", headers=client.tokens["Ana"]).status_code == 403
    assert len(client.get("/api/admin/groups", headers=client.tokens["Admin"]).json()["groups"]) == 2


def test_agregar_y_quitar_estudiantes(client):
    group = _new_group(client)
    add = lambda student, who="Profe": _call(client, "POST", "/api/groups/members", who,  # noqa: E731
                                             {"groupId": group["id"], "student": student})

    assert add("ana").status_code == 200  # por usuario, sin @
    data = add("BETO@est.cedesdonbosco.ed.cr").json()  # por correo, sin importar mayúsculas
    assert [m["handle"] for m in data["group"]["members"]] == ["@ana", "@beto"]
    assert len(add("@ana").json()["group"]["members"]) == 2  # repetir no duplica
    assert add("@profe").json()["error"] == "Solo puedes agregar cuentas de estudiante."
    assert add("@nadie").status_code == 404
    assert add("@ana", who="Otra").status_code == 403  # otro profesor
    assert add("@ana", who="Admin").status_code == 200  # un admin modera cualquiera

    response = _call(client, "DELETE", "/api/groups/members", "Profe", {"groupId": group["id"], "studentId": "4"})
    assert [m["handle"] for m in response.json()["group"]["members"]] == ["@beto"]
    assert _call(client, "POST", "/api/groups/members", "Profe", {"groupId": "no-existe", "student": "@ana"}).status_code == 404


def test_miembros_traen_sus_aciertos_para_el_grafico(client):
    group = _new_group(client)
    _call(client, "POST", "/api/groups/members", "Profe", {"groupId": group["id"], "student": "@ana"})
    db = client.db()
    db.add(Solve(user_id=4, challenge_id="crypto-xor-01", points=100))
    db.commit()
    member = client.get("/api/groups/mine", headers=client.tokens["Profe"]).json()["groups"][0]["members"][0]
    assert member["playerId"] == "4" and member["solves"] == 1 and member["score"] == 100
    assert isinstance(member["solved"]["crypto-xor-01"]["time"], int)


def test_tareas_de_grupo(client):
    group = _new_group(client)
    post = lambda body: _call(client, "POST", "/api/groups/tasks", "Profe", {"groupId": group["id"], **body})  # noqa: E731

    assert post({"title": " "}).json()["error"] == "Escribe un título para la tarea."
    assert post({"title": "Reto", "challengeId": "no-existe"}).json()["error"] == "Ese reto no existe."
    post({"title": "Sin fecha"})
    post({"title": "Con reto", "challengeId": "crypto-xor-01", "dueDate": "2026-10-30"})
    tasks = post({"title": "Fecha rara", "dueDate": "2026-02-31", "description": "Leer la guía"}).json()["group"]["tasks"]

    # Con fecha primero; sin fecha (o fecha inválida) al final, por orden de creación.
    assert [t["title"] for t in tasks] == ["Con reto", "Sin fecha", "Fecha rara"]
    with_challenge, plain, odd = tasks
    assert with_challenge["challengeId"] == "crypto-xor-01" and with_challenge["dueDate"] == "2026-10-30"
    assert plain["challengeId"] == "" and plain["done"] is False and odd["dueDate"] == ""

    toggle = lambda task_id: _call(client, "POST", "/api/groups/tasks/toggle", "Profe",  # noqa: E731
                                   {"groupId": group["id"], "taskId": task_id})
    assert toggle(with_challenge["id"]).status_code == 400  # se cumple sola al resolver el reto
    done = toggle(plain["id"]).json()["group"]["tasks"]
    assert next(t for t in done if t["id"] == plain["id"])["done"] is True
    assert toggle("no-existe").status_code == 404

    left = _call(client, "DELETE", "/api/groups/tasks", "Profe", {"groupId": group["id"], "taskId": plain["id"]})
    assert [t["title"] for t in left.json()["group"]["tasks"]] == ["Con reto", "Fecha rara"]
    assert _call(client, "POST", "/api/groups/tasks", "Otra", {"groupId": group["id"], "title": "x"}).status_code == 403


def test_detalle_de_estudiante_solo_para_su_profesor_o_un_admin(client):
    group = _new_group(client)
    _call(client, "POST", "/api/groups/members", "Profe", {"groupId": group["id"], "student": "@ana"})
    url = "/api/groups/student?playerId=1&studentId="

    response = client.get(url + "4", headers=client.tokens["Profe"])
    assert response.status_code == 200 and response.json()["student"]["handle"] == "@ana"
    assert client.get(url + "4", headers=client.tokens["Admin"]).status_code == 200
    assert client.get(url + "4", headers=client.tokens["Otra"]).status_code == 403  # no es su estudiante
    assert client.get(url + "5", headers=client.tokens["Profe"]).status_code == 403  # no está en su grupo
    assert client.get(url + "5", headers=client.tokens["Ana"]).status_code == 403
    assert client.get(url + "999", headers=client.tokens["Admin"]).status_code == 404


def test_estudiantes_disponibles(client):
    response = client.get("/api/groups/available-students", headers=client.tokens["Profe"])
    assert [s["handle"] for s in response.json()["students"]] == ["@ana", "@beto"]
    assert client.get("/api/groups/available-students", headers=client.tokens["Admin"]).status_code == 200
    assert client.get("/api/groups/available-students", headers=client.tokens["Ana"]).status_code == 403


def test_eliminar_grupo(client):
    group = _new_group(client)
    _call(client, "POST", "/api/groups/members", "Profe", {"groupId": group["id"], "student": "@ana"})
    assert _call(client, "DELETE", "/api/groups", "Otra", {"groupId": group["id"]}).status_code == 403
    assert _call(client, "DELETE", "/api/groups", "Profe", {"groupId": group["id"]}).json() == {"ok": True}
    db = client.db()
    assert db.get(Group, group["id"]) is None
    assert db.scalars(select(GroupMember)).all() == []  # sus miembros se van con él
    assert db.get(User, 4) is not None  # el estudiante no

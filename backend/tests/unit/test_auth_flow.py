"""
Pruebas de app/services/auth_flow.py (registro y login con MFA) y
app/core/sessions.py (sesiones revocables).

Usan una base SQLite en memoria — nada de esto toca Supabase, así que
corren igual aunque el proyecto esté pausado (ver nota recurrente en
CLAUDE.md). Las tablas se crean directo desde los modelos de SQLAlchemy
(Base.metadata.create_all), no desde la migración de Alembic.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sessions import create_session, resolve_session, revoke_session
from app.db.session import Base
from app.models.user import User
from app.services import auth_flow

VALID_REGISTRATION = {
    "name": "Ana Pérez",
    "handle": "ana",
    "gender": "femenino",
    "password": "clave1234",
    "email": "ana@est.cedesdonbosco.ed.cr",
}


@pytest.fixture
def db():
    """Una base SQLite en memoria nueva, con las tablas ya creadas."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_pending_stores():
    """
    Los códigos pendientes viven en diccionarios a nivel de módulo (en
    memoria, a propósito — ver docstring de auth_flow.py). Sin esto, un
    token de una prueba quedaría "vivo" para la siguiente.
    """
    auth_flow._pending_registrations.clear()
    auth_flow._pending_logins.clear()
    yield
    auth_flow._pending_registrations.clear()
    auth_flow._pending_logins.clear()


def _register_and_verify(db, overrides: dict | None = None) -> dict:
    """Atajo: corre el flujo de registro completo y devuelve el player creado."""
    data = {**VALID_REGISTRATION, **(overrides or {})}
    draft = auth_flow.begin_registration(data, db)
    assert draft["ok"], draft
    code = draft["code"]
    result = auth_flow.complete_registration(draft["token"], code, db)
    assert result["ok"], result
    return result["player"]


class TestNormalizeHandle:
    def test_agrega_arroba_y_pasa_a_minusculas(self):
        assert auth_flow.normalize_handle("Ana") == "@ana"

    def test_quita_arrobas_de_mas_y_caracteres_invalidos(self):
        assert auth_flow.normalize_handle("@@Ana Pérez!!") == "@anaprez"


class TestRoleForEmail:
    def test_dominio_de_estudiante(self):
        assert auth_flow.role_for_email("x@est.cedesdonbosco.ed.cr") == "estudiante"

    def test_dominio_de_profesor(self):
        assert auth_flow.role_for_email("x@cedesdonbosco.ed.cr") == "profesor"

    def test_correo_externo_no_tiene_rol_institucional(self):
        assert auth_flow.role_for_email("x@gmail.com") is None


class TestBeginRegistrationValidaciones:
    def test_acepta_datos_validos(self, db):
        draft = auth_flow.begin_registration(VALID_REGISTRATION, db)
        assert draft == {
            "ok": True,
            "token": draft["token"],
            "email": "ana@est.cedesdonbosco.ed.cr",
            "role": "estudiante",
            "code": draft["code"],
        }

    def test_correo_externo_entra_como_estudiante_por_defecto(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "email": "ana@gmail.com"}, db)
        assert draft["ok"] is True
        assert draft["role"] == "estudiante"

    def test_rechaza_contrasena_corta(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "password": "abc1234"}, db)
        assert draft == {"ok": False, "error": "La contraseña debe tener al menos 8 caracteres."}

    def test_rechaza_contrasena_vacia(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "password": ""}, db)
        assert draft["ok"] is False

    @pytest.mark.parametrize("password", ["A" * 65, "A" * 300, "ñ" * 40])  # 40 ñ = 80 bytes > 72
    def test_rechaza_contrasena_demasiado_larga_sin_error_500(self, db, password):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "password": password}, db)
        assert draft == {"ok": False, "error": "La contraseña no puede tener más de 64 caracteres."}

    def test_rechaza_correo_de_mas_de_254_caracteres(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "email": "a" * 300 + "@example.com"}, db)
        assert draft == {"ok": False, "error": "Escribe un correo válido."}

    @pytest.mark.parametrize("email", ["<script>alert(1)</script>@example.com", "ana@exa mple.com", "ana\"@x.com"])
    def test_rechaza_correo_con_caracteres_raros(self, db, email):
        assert auth_flow.begin_registration({**VALID_REGISTRATION, "email": email}, db)["ok"] is False

    @pytest.mark.parametrize("name", ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "Ana\x00", 'Ana"'])
    def test_rechaza_nombre_con_marcado_html(self, db, name):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "name": name}, db)
        assert draft["ok"] is False and "El nombre solo puede tener" in draft["error"]

    @pytest.mark.parametrize("name", ["José María Ñúñez", "Ana O'Neil", "Jean-Luc Picard", "Ana 2"])
    def test_acepta_nombres_reales(self, db, name):
        assert auth_flow.begin_registration({**VALID_REGISTRATION, "name": name}, db)["ok"] is True

    def test_rechaza_correo_invalido(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "email": "no-es-un-correo"}, db)
        assert draft == {"ok": False, "error": "Escribe un correo válido."}

    def test_rechaza_genero_invalido(self, db):
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "gender": "x"}, db)
        assert draft == {"ok": False, "error": "Selecciona un género."}

    def test_rechaza_handle_duplicado(self, db):
        _register_and_verify(db)
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "email": "otra@est.cedesdonbosco.ed.cr"}, db)
        assert draft == {"ok": False, "error": "Ese usuario ya está registrado. Inicia sesión."}

    def test_rechaza_correo_duplicado(self, db):
        _register_and_verify(db)
        draft = auth_flow.begin_registration({**VALID_REGISTRATION, "handle": "otra"}, db)
        assert draft == {"ok": False, "error": "Ese correo ya tiene una cuenta verificada. Inicia sesión."}


class TestCompleteRegistration:
    def test_codigo_correcto_crea_la_cuenta(self, db):
        player = _register_and_verify(db)
        assert player["handle"] == "@ana"
        assert player["role"] == "estudiante"
        assert db.query(User).filter(User.username == "@ana").one()

    def test_codigo_incorrecto_no_crea_la_cuenta(self, db):
        draft = auth_flow.begin_registration(VALID_REGISTRATION, db)
        result = auth_flow.complete_registration(draft["token"], "000000", db)
        assert result["ok"] is False
        assert db.query(User).count() == 0

    def test_demasiados_intentos_descarta_el_token(self, db):
        draft = auth_flow.begin_registration(VALID_REGISTRATION, db)
        for _ in range(5):
            auth_flow.complete_registration(draft["token"], "000000", db)
        result = auth_flow.complete_registration(draft["token"], draft["code"], db)
        assert result["ok"] is False
        assert "Demasiados intentos" in result["error"] or "ya no está disponible" in result["error"]


class TestLoginConMfa:
    def test_credenciales_correctas_piden_codigo(self, db):
        _register_and_verify(db)
        draft = auth_flow.begin_login({"handle": "ana", "password": "clave1234"}, db)
        assert draft["ok"] is True
        assert "token" in draft and "code" in draft

    def test_contrasena_incorrecta_da_error_generico(self, db):
        _register_and_verify(db)
        result = auth_flow.begin_login({"handle": "ana", "password": "incorrecta"}, db)
        assert result == {"ok": False, "error": auth_flow.GENERIC_LOGIN_ERROR}

    def test_handle_inexistente_da_el_mismo_error_generico(self, db):
        result = auth_flow.begin_login({"handle": "no-existe", "password": "lo-que-sea"}, db)
        assert result == {"ok": False, "error": auth_flow.GENERIC_LOGIN_ERROR}

    def test_login_completo_con_codigo_correcto(self, db):
        _register_and_verify(db)
        draft = auth_flow.begin_login({"handle": "ana", "password": "clave1234"}, db)
        result = auth_flow.complete_login(draft["token"], draft["code"], db)
        assert result["ok"] is True
        assert result["player"]["handle"] == "@ana"

    def test_admin_no_pasa_por_mfa(self, db):
        player = _register_and_verify(db)
        user = db.get(User, int(player["playerId"]))
        user.role = "admin"
        db.commit()
        result = auth_flow.begin_login({"handle": "ana", "password": "clave1234"}, db)
        assert result == {"ok": True, "admin": True, "player": result["player"]}


class TestLoginEntradasExtremas:
    def test_contrasena_de_300_caracteres_contra_cuenta_existente_no_da_error_500(self, db):
        _register_and_verify(db)
        result = auth_flow.begin_login({"handle": "ana", "password": "A" * 300}, db)
        assert result == {"ok": False, "error": auth_flow.GENERIC_LOGIN_ERROR}

    def test_usuario_inexistente_tambien_pasa_por_bcrypt(self, db, monkeypatch):
        """Mismo costo exista o no la cuenta: no se puede averiguar por tiempo."""
        llamadas = []
        real = auth_flow.verify_password
        monkeypatch.setattr(auth_flow, "verify_password", lambda p, h: llamadas.append(h) or real(p, h))
        auth_flow.begin_login({"handle": "no-existe", "password": "lo-que-sea"}, db)
        assert llamadas == [auth_flow._DUMMY_HASH]


class TestBloqueoPorFuerzaBruta:
    def test_bloquea_tras_cinco_fallos_y_el_error_cambia_solo_para_el_dueno(self, db):
        _register_and_verify(db)
        for _ in range(5):
            auth_flow.begin_login({"handle": "ana", "password": "mala"}, db)

        # Un extraño sigue viendo el mensaje genérico, no "bloqueada".
        extrano = auth_flow.begin_login({"handle": "ana", "password": "mala"}, db)
        assert extrano["error"] == auth_flow.GENERIC_LOGIN_ERROR

        # El dueño (contraseña correcta) sí se entera de que está bloqueada.
        dueno = auth_flow.begin_login({"handle": "ana", "password": "clave1234"}, db)
        assert dueno["ok"] is False
        assert dueno.get("locked") is True


class TestSesiones:
    def test_resolve_session_devuelve_el_usuario_dueno_del_token(self, db):
        player = _register_and_verify(db)
        token = create_session(db, int(player["playerId"]))
        resolved = resolve_session(db, token)
        assert resolved is not None
        assert resolved.id == int(player["playerId"])

    def test_token_invalido_no_resuelve_a_nadie(self, db):
        assert resolve_session(db, "esto-no-es-un-token-real") is None

    def test_revoke_session_invalida_el_token_de_inmediato(self, db):
        player = _register_and_verify(db)
        token = create_session(db, int(player["playerId"]))
        revoke_session(db, token)
        assert resolve_session(db, token) is None

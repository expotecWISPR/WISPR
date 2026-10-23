"""
Pruebas de app/services/scoring.py contra una base SQLite en memoria
(no toca Supabase).
"""

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra todos los modelos en Base.metadata
from app.db.session import Base
from app.models.challenge import Challenge
from app.models.submission import Solve, Submission
from app.models.user import User
from app.services import scoring

OK_FLAG = "WISPR{deauth_target}"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)

    # SQLite no aplica SAVEPOINT correctamente con el driver por defecto;
    # esta es la receta oficial de SQLAlchemy para que begin_nested() se
    # comporte como en PostgreSQL.
    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for uid, name, role in [(1, "Ana", "estudiante"), (2, "Beto", "estudiante"), (3, "Profe", "profesor")]:
        session.add(User(id=uid, email=f"u{uid}@x.com", username=f"@{name.lower()}", full_name=name,
                         gender="otro", role=role, password_hash="x"))
    session.add(Challenge(id="deauth", title="Primeros Deauth", category="Deauth / DoS", difficulty="Foundation",
                          points=120, description="d", flag=OK_FLAG))
    session.add(Challenge(id="pmkid", title="PMKID", category="PMKID", difficulty="Medium",
                          points=200, description="d", flag="WISPR{pmkid_capture}"))
    session.add(Challenge(id="viejo", title="Retirado", category="x", difficulty="Hard",
                          points=340, description="d", flag="WISPR{viejo}", is_active=False))
    session.commit()
    yield session
    session.close()


def _user(db, uid=1):
    return db.get(User, uid)


def _count(db, model, **filters):
    return db.scalar(select(func.count()).select_from(model).filter_by(**filters))


def test_reto_inexistente_o_inactivo_no_registra_nada(db):
    for challenge_id in ["no-existe", "viejo"]:
        assert scoring.submit_flag(db, _user(db), challenge_id, "WISPR{viejo}") == {
            "ok": False, "error": scoring.CHALLENGE_NOT_FOUND}
    assert _count(db, Submission) == 0


def test_formato_invalido_no_cuenta_como_intento(db):
    result = scoring.submit_flag(db, _user(db), "deauth", "FLAG{abc}")
    assert result["ok"] is False and "WISPR{...}" in result["error"]
    assert _count(db, Submission) == 0


def test_flag_incorrecta_registra_el_intento_sin_puntos(db):
    assert scoring.submit_flag(db, _user(db), "deauth", "WISPR{nope}") == {"ok": False, "challengeId": "deauth"}
    assert _count(db, Submission, correct=False) == 1
    assert _count(db, Solve) == 0


def test_flag_correcta_suma_puntos_una_sola_vez(db):
    first = scoring.submit_flag(db, _user(db), "deauth", f"  {OK_FLAG}  ")  # con espacios: se recortan
    assert {k: first[k] for k in ("ok", "challengeId", "points", "generationError")} == {
        "ok": True, "challengeId": "deauth", "points": 120, "generationError": ""}
    # Siguiente reto (motor adaptativo): no quedan de "Deauth / DoS", así que
    # el de otra categoría en el nivel calculado (Medium, por acertar al primer intento).
    assert first["nextChallenge"]["id"] == "pmkid"

    second = scoring.submit_flag(db, _user(db), "deauth", OK_FLAG, source="terminal")
    assert {k: second[k] for k in ("ok", "duplicate", "challengeId", "points")} == {"ok": True, "duplicate": True, "challengeId": "deauth", "points": 120}
    assert second["breakdown"]["total"] == 120  # el desglose guardado del primer acierto

    assert _count(db, Solve) == 1
    assert _count(db, Submission) == 2


def test_dos_envios_correctos_simultaneos_no_duplican_puntos(db, monkeypatch):
    """
    Simula la carrera: el solve ya existe en la BD, pero el chequeo previo
    "no lo ve" (como pasaría si el otro envío entró justo entre medio).
    La clave primaria de `solves` tiene que frenarlo.
    """
    scoring.submit_flag(db, _user(db), "deauth", OK_FLAG)
    real_get = db.get
    monkeypatch.setattr(db, "get", lambda model, key: None if model is Solve else real_get(model, key))

    result = scoring.submit_flag(db, _user(db), "deauth", OK_FLAG)
    assert result["duplicate"] is True
    assert _count(db, Solve) == 1
    assert _count(db, Submission) == 2  # el intento sí queda registrado


def test_racha_se_corta_en_el_primer_fallo(db):
    user = _user(db)
    scoring.submit_flag(db, user, "deauth", "WISPR{nope}")
    scoring.submit_flag(db, user, "deauth", OK_FLAG)
    scoring.submit_flag(db, user, "pmkid", "WISPR{pmkid_capture}")
    assert scoring.current_streak(db, user.id) == 2
    scoring.submit_flag(db, user, "pmkid", "WISPR{nope}")
    assert scoring.current_streak(db, user.id) == 0


def test_player_progress_tiene_la_forma_del_prototipo(db):
    user = _user(db)
    scoring.submit_flag(db, user, "deauth", "WISPR{nope}")
    scoring.submit_flag(db, user, "deauth", OK_FLAG)
    progress = scoring.player_progress(db, user.id)

    assert progress["attempts"] == {"deauth": 2}
    assert list(progress["solved"]) == ["deauth"]
    assert progress["solved"]["deauth"]["points"] == 114  # 120 − 5 % por el intento fallido
    assert progress["solved"]["deauth"]["breakdown"]["wrong"] == {"count": 1, "pct": -5, "points": -6}
    assert isinstance(progress["solved"]["deauth"]["time"], int)
    # Del más nuevo al más viejo, como en el prototipo.
    assert [s["ok"] for s in progress["submissions"]] == [True, False]
    assert progress["submissions"][0] == {**progress["submissions"][0], "id": "deauth", "title": "Primeros Deauth", "source": "web"}


def test_ranking_solo_estudiantes_ordenado_y_sin_datos_privados(db):
    scoring.submit_flag(db, _user(db, 2), "pmkid", "WISPR{pmkid_capture}")   # Beto: 200
    scoring.submit_flag(db, _user(db, 1), "deauth", OK_FLAG)                 # Ana: 120
    scoring.submit_flag(db, _user(db, 3), "pmkid", "WISPR{pmkid_capture}")   # Profe: no aparece

    ranking = scoring.ranking(db, current_user_id=1)
    assert [r["handle"] for r in ranking] == ["@beto", "@ana"]
    assert ranking[0] == {"name": "Beto", "handle": "@beto", "score": 200, "solves": 1, "streak": 1, "current": False}
    assert ranking[1]["current"] is True
    for row in ranking:
        assert "email" not in row and "id" not in row and "playerId" not in row


def test_ranking_incluye_estudiantes_sin_puntos(db):
    ranking = scoring.ranking(db, current_user_id=None)
    assert [(r["handle"], r["score"]) for r in ranking] == [("@ana", 0), ("@beto", 0)]

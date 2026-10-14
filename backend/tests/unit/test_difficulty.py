"""
Pruebas del motor adaptativo (app/services/difficulty.py): una por cada fila
de la tabla de reglas (guía del ingeniero, fase 4), más "nunca recomienda un
reto ya resuelto" y la creación de retos nuevos con su archivo por jugador.
SQLite en memoria; la IA no se llama (conftest.py -> plantilla).
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra todos los modelos en Base.metadata
from app.db.session import Base
from app.models.challenge import Challenge, ChallengeInstance
from app.models.submission import Solve, Submission
from app.models.user import User
from app.services import challenge_generator, difficulty, instances


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(challenge_generator, "GENERATED_DIR", tmp_path)
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, email="ana@x.com", username="@ana", full_name="Ana", gender="otro",
                     role="estudiante", password_hash="x"))
    for cid, category, kind, level, points in [
        ("xor-f", "Criptografía", "xor_singlebyte", "Foundation", 120),
        ("deauth-f", "Deauth / DoS", "deauth", "Foundation", 120),
        ("deauth-m", "Deauth / DoS", "deauth", "Medium", 200),
        ("wpa-f", "WPA/WPA2", "wpa-handshake", "Foundation", 120),
        ("wpa-m", "WPA/WPA2", "wpa-handshake", "Medium", 200),
        ("wpa-h", "WPA/WPA2", "wpa-handshake", "Hard", 340),
        ("wpa-x", "WPA/WPA2", "wpa-handshake", "Expert", 500),
    ]:
        session.add(Challenge(id=cid, title=cid.upper(), category=category, kind=kind, difficulty=level,
                              points=points, description="d", flag=f"WISPR{{{cid}}}"))
    session.commit()
    yield session
    session.close()


def _play(db, challenge_id, fails, solve=True):
    for _ in range(fails):
        db.add(Submission(user_id=1, challenge_id=challenge_id, correct=False))
    if solve:
        db.add(Submission(user_id=1, challenge_id=challenge_id, correct=True))
        db.add(Solve(user_id=1, challenge_id=challenge_id, points=1))
    db.commit()
    return db.get(Challenge, challenge_id)


# ─── Tabla de reglas ──────────────────────────────────────────────────────

@pytest.mark.parametrize("fails", [0, 1])
def test_resolver_en_primer_o_segundo_intento_sube(db, fails):
    level, reason = difficulty.recommend_level(db, 1, _play(db, "wpa-m", fails))
    assert level == "Hard" and reason.startswith("Subes a Hard")


@pytest.mark.parametrize("fails", [2, 5])  # 3 a 6 intentos en total
def test_resolver_con_varios_intentos_se_mantiene(db, fails):
    level, reason = difficulty.recommend_level(db, 1, _play(db, "wpa-m", fails))
    assert level == "Medium" and reason.startswith("Sigues en Medium")


@pytest.mark.parametrize("solve", [True, False])  # resuelto o trabado
def test_mas_de_5_fallos_baja(db, solve):
    level, reason = difficulty.recommend_level(db, 1, _play(db, "wpa-m", 6, solve=solve), solved=solve)
    assert level == "Foundation" and reason.startswith("Bajas a Foundation")


def test_en_los_extremos_se_queda(db):
    assert difficulty.recommend_level(db, 1, _play(db, "wpa-x", 0))[0] == "Expert"
    level, reason = difficulty.recommend_level(db, 1, _play(db, "wpa-f", 8))
    assert level == "Foundation" and "más bajo" in reason


def test_nivel_por_categoria(db):
    _play(db, "xor-f", 0)        # cripto: sube a Medium
    _play(db, "deauth-f", 7)     # deauth: se queda en Foundation (ya es el más bajo)
    levels = difficulty.player_levels(db, 1)
    assert levels["Criptografía"]["level"] == "Medium"
    assert levels["Deauth / DoS"]["level"] == "Foundation"


# ─── Qué reto recomienda ──────────────────────────────────────────────────

def test_recomienda_misma_categoria_en_el_nivel_calculado(db):
    pick, reason, _ = difficulty.next_challenge(db, db.get(User, 1), _play(db, "wpa-f", 0))
    assert pick.id == "wpa-m"


def test_nunca_recomienda_un_reto_resuelto(db):
    user = db.get(User, 1)
    _play(db, "wpa-m", 0)
    _play(db, "wpa-h", 0)
    pick, _, _ = difficulty.next_challenge(db, user, _play(db, "wpa-f", 0))   # pediría Medium: ya resuelto
    assert pick.id == "wpa-x"
    solved = set(db.scalars(select(Solve.challenge_id)))
    for _ in range(3):
        pick, _, _ = difficulty.next_challenge(db, user, db.get(Challenge, "wpa-f"))
        assert pick.id not in solved


def test_si_no_quedan_de_la_categoria_va_a_otra(db):
    for cid in ("wpa-f", "wpa-m", "wpa-h", "wpa-x"):
        _play(db, cid, 0)
    pick, _, _ = difficulty.next_challenge(db, db.get(User, 1), db.get(Challenge, "wpa-x"))
    assert pick.category != "WPA/WPA2"


def test_tecnica_con_generador_crea_un_reto_nuevo_para_el_jugador(db, tmp_path):
    user = db.get(User, 1)
    created, reason, ai_error = difficulty.next_challenge(db, user, _play(db, "xor-f", 0))
    assert created.owner_id == 1 and created.kind == "xor_singlebyte" and created.difficulty == "Medium"
    assert created.generated is True and created.generator == "template" and ai_error  # sin IA en tests
    assert created.flag == "" and created.objective and len(created.hints) == 2

    # Su instancia ya existe, con flag propia y su archivo en disco.
    instance = db.get(ChallengeInstance, (1, created.id))
    assert instance.flag.startswith("WISPR{xor_")
    assert instances.artifact_file(instance).is_file()
    assert tmp_path in instances.artifact_file(instance).parents

    # Si vuelve a pedir el siguiente sin resolverlo, se reusa (no se llena de retos).
    again, _, _ = difficulty.next_challenge(db, user, db.get(Challenge, "xor-f"))
    assert again.id == created.id


def test_resolver_todo_crea_un_reto_nuevo(db):
    for cid in ("xor-f", "deauth-f", "deauth-m", "wpa-f", "wpa-m", "wpa-h"):
        _play(db, cid, 3)
    created, _, _ = difficulty.next_challenge(db, db.get(User, 1), _play(db, "wpa-x", 3))
    # Expert se genera como Hard (las técnicas llegan hasta hard).
    assert created.owner_id == 1 and created.difficulty == "Hard"

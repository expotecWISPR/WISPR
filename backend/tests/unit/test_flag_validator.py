"""
Pruebas de app/services/flag_validator.py contra una base SQLite en memoria
(no toca Supabase).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — registra todos los modelos en Base.metadata
from app.db.session import Base
from app.models.challenge import Challenge, ChallengeInstance
from app.models.user import User
from app.services import flag_validator


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, email="ana@est.cedesdonbosco.ed.cr", username="@ana", full_name="Ana",
                     gender="femenino", role="estudiante", password_hash="x"))
    session.add(User(id=2, email="beto@est.cedesdonbosco.ed.cr", username="@beto", full_name="Beto",
                     gender="masculino", role="estudiante", password_hash="x"))
    session.add(Challenge(id="deauth-recon-foundation", title="Primeros Deauth", category="Deauth / DoS",
                          kind="deauth", difficulty="Foundation", points=120, description="d",
                          flag="WISPR{deauth_target}"))
    session.commit()
    yield session
    session.close()


def _challenge(db):
    return db.get(Challenge, "deauth-recon-foundation")


@pytest.mark.parametrize("flag,ok", [
    ("WISPR{abc}", True),
    ("WISPR{deauth_a4c2f1093b7e}", True),
    ("WISPR{ab}", False),          # menos de 3 caracteres adentro
    ("FLAG{abc}", False),          # formato viejo
    ("WISPR{a{b}c}", False),       # llaves anidadas
    ("WISPR{abc\n}", False),       # salto de línea
    ("WISPR{" + "a" * 181 + "}", False),
])
def test_formato(flag, ok):
    assert flag_validator.is_valid_format(flag) is ok


def test_sin_instancia_usa_la_flag_del_catalogo(db):
    assert flag_validator.check_flag(db, 1, _challenge(db), "WISPR{deauth_target}")
    assert not flag_validator.check_flag(db, 1, _challenge(db), "WISPR{otra_cosa}")


def test_con_instancia_usa_la_flag_personal_y_no_la_del_catalogo(db):
    db.add(ChallengeInstance(user_id=1, challenge_id="deauth-recon-foundation", flag="WISPR{deauth_a4c2f1093b7e}"))
    db.commit()
    assert flag_validator.check_flag(db, 1, _challenge(db), "WISPR{deauth_a4c2f1093b7e}")
    # Con instancia propia, la flag genérica del catálogo ya no sirve.
    assert not flag_validator.check_flag(db, 1, _challenge(db), "WISPR{deauth_target}")


def test_la_flag_personal_de_un_jugador_no_sirve_para_otro(db):
    db.add(ChallengeInstance(user_id=1, challenge_id="deauth-recon-foundation", flag="WISPR{deauth_a4c2f1093b7e}"))
    db.add(ChallengeInstance(user_id=2, challenge_id="deauth-recon-foundation", flag="WISPR{deauth_6e01d8aa4f22}"))
    db.commit()
    assert not flag_validator.check_flag(db, 2, _challenge(db), "WISPR{deauth_a4c2f1093b7e}")
    assert flag_validator.check_flag(db, 2, _challenge(db), "WISPR{deauth_6e01d8aa4f22}")


def test_reto_por_jugador_sin_instancia_no_acepta_ninguna_flag(db):
    """La flag del catálogo de un reto del pipeline es la de la plantilla (está en el repo)."""
    db.add(Challenge(id="crypto-xor-01", title="XOR", category="Criptografía", kind="xor_singlebyte",
                     difficulty="Foundation", points=120, description="d", flag="WISPR{xor_de_plantilla}"))
    db.commit()
    xor = db.get(Challenge, "crypto-xor-01")
    assert not flag_validator.check_flag(db, 1, xor, "WISPR{xor_de_plantilla}")
    db.add(ChallengeInstance(user_id=1, challenge_id="crypto-xor-01", flag="WISPR{xor_9f3a01c2}"))
    db.commit()
    assert flag_validator.check_flag(db, 1, xor, "WISPR{xor_9f3a01c2}")


def test_flags_match_acepta_texto_no_ascii():
    assert flag_validator.flags_match("WISPR{contraseña}", "WISPR{contraseña}")
    assert not flag_validator.flags_match("WISPR{contraseña}", "WISPR{contrasena}")

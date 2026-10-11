"""
Validación de flags enviadas por los jugadores.

Migrado de `flagsMatch` + el inicio de `verifySubmission` en
`wispr_terminal_professional/server.js`. Solo responde "¿esta flag es la
correcta para este jugador en este reto?" — registrar el intento y sumar
puntos es trabajo de `scoring.py`.

¿De dónde sale la flag esperada? (decisión del 11 oct)
  1. Si el jugador tiene una instancia personal del reto
     (`challenge_instances`), se usa esa flag — es la que va dentro de SU
     copia del archivo (ej. su BSSID en un reto de deauth).
  2. Si no, la flag fija del catálogo (`challenges.flag`).
Es el mismo respaldo del prototipo: `getInstanceFlag(...) || challenge.flag`.
"""

import hmac
import re

from sqlalchemy.orm import Session as DbSession

from app.models.challenge import Challenge, ChallengeInstance

# Mismo regex que `FLAG_PATTERN` en app/schemas/challenge.py y que el prototipo.
FLAG_FORMAT = re.compile(r"^WISPR\{[^{}\r\n]{3,180}\}$")
FORMAT_ERROR = "La flag debe tener el formato WISPR{...}."


def is_valid_format(flag: str) -> bool:
    return bool(FLAG_FORMAT.match(flag))


def expected_flag(db: DbSession, user_id: int, challenge: Challenge) -> str:
    instance = db.get(ChallengeInstance, (user_id, challenge.id))
    return instance.flag if instance is not None else challenge.flag


def flags_match(submitted: str, expected: str) -> bool:
    """
    Comparación de tiempo constante: `==` corta en el primer carácter
    distinto, y midiendo cuánto tarda la respuesta se podría adivinar la
    flag letra por letra. `hmac.compare_digest` siempre tarda lo mismo.
    Se comparan bytes UTF-8 porque compare_digest solo acepta str ASCII.
    """
    return hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


def check_flag(db: DbSession, user_id: int, challenge: Challenge, submitted: str) -> bool:
    """`submitted` ya debe venir con `.strip()` y con formato validado."""
    return flags_match(submitted, expected_flag(db, user_id, challenge))

"""
Pruebas unitarias de app/core/security.py.

Antes veníamos probando esto a mano, escribiendo un script y corriéndolo
cada vez. Esto hace lo mismo pero de forma permanente: se corre con
"pytest" desde backend/, y si alguien rompe algo sin querer (como pasó
con el bug de passlib), se entera al instante en vez de descubrirlo
semanas después.
"""

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_no_guarda_texto_plano():
    hashed = hash_password("miClaveSegura123")
    assert hashed != "miClaveSegura123"


def test_verify_password_con_la_contrasena_correcta():
    hashed = hash_password("miClaveSegura123")
    assert verify_password("miClaveSegura123", hashed) is True


def test_verify_password_con_una_contrasena_incorrecta():
    hashed = hash_password("miClaveSegura123")
    assert verify_password("otraClave", hashed) is False


def test_hash_password_rechaza_mas_de_72_bytes():
    with pytest.raises(ValueError):
        hash_password("a" * 73)


def test_create_y_decode_access_token():
    token = create_access_token({"sub": "ana@example.com"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "ana@example.com"


def test_decode_access_token_con_token_manipulado():
    token = create_access_token({"sub": "ana@example.com"})
    token_manipulado = token[:-5] + "XXXXX"
    assert decode_access_token(token_manipulado) is None

"""
Pruebas unitarias de app/core/security.py.

Antes veníamos probando esto a mano, escribiendo un script y corriéndolo
cada vez. Esto hace lo mismo pero de forma permanente: se corre con
"pytest" desde backend/, y si alguien rompe algo sin querer (como pasó
con el bug de passlib), se entera al instante en vez de descubrirlo
semanas después.
"""

import pytest

from app.core.security import hash_password, verify_password


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


def test_verify_password_con_mas_de_72_bytes_devuelve_false_sin_error():
    hashed = hash_password("miClaveSegura123")
    assert verify_password("a" * 300, hashed) is False

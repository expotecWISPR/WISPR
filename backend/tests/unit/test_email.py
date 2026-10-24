"""
Pruebas del respaldo de app/services/email.py cuando no hay SMTP: en
desarrollo devuelve el código (modo desarrollo); en producción falla, para
no anular el MFA. No envía correos reales (se fuerza SMTP_HOST vacío).
"""

import re

import pytest

from app.core.config import settings
from app.services import email


@pytest.fixture()
def sin_smtp(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(email, "OUTBOX_DIR", tmp_path)


def test_desarrollo_cae_a_modo_desarrollo_con_el_codigo(sin_smtp, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    result = email.send_verification_code("ana@example.com", "123456")
    assert result.ok and result.dev and result.code == "123456"


def test_produccion_falla_y_no_expone_el_codigo(sin_smtp, monkeypatch, caplog):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    result = email.send_verification_code("ana@example.com", "123456")
    assert result.ok is False
    assert result.code is None
    assert "123456" not in caplog.text


def test_html_trae_el_codigo_copiable_y_escapa_el_correo():
    html = email._html_body('<b>x</b>@example.com', "123456", "login")
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "inicio de sesión" in html
    # Casillas pegadas: al copiar sale "123456" sin espacios entre dígitos.
    assert re.sub(r"<[^>]+>", "", html).count("123456") >= 1


def test_el_modo_desarrollo_guarda_tambien_el_html(sin_smtp, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    email.send_verification_code("ana@example.com", "123456", "register")
    assert len(list(tmp_path.glob("*.html"))) == 1


def test_el_correo_real_lleva_el_logo_adjunto(monkeypatch):
    """El logo va dentro del correo (cid:), no como enlace a un servidor."""
    enviados = []

    class SMTPFalso:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self): pass
        def login(self, *args): pass
        def send_message(self, message): enviados.append(message)

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_SECURE", False)
    monkeypatch.setattr(email.smtplib, "SMTP", SMTPFalso)
    assert email.send_verification_code("ana@example.com", "123456", "register").ok
    partes = {parte.get_content_type(): parte for parte in enviados[0].walk()}
    assert "text/plain" in partes
    assert f"cid:{email.LOGO_CID}" in partes["text/html"].get_content()
    assert partes["image/png"]["Content-ID"] == f"<{email.LOGO_CID}>"

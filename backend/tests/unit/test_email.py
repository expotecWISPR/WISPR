"""
Pruebas del respaldo de app/services/email.py cuando no hay SMTP: en
desarrollo devuelve el código (modo desarrollo); en producción falla, para
no anular el MFA. No envía correos reales (se fuerza SMTP_HOST vacío).
"""

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

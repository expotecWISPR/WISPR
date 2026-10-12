"""Pruebas de app/core/rate_limit.py (ventana deslizante en memoria)."""

import pytest

from app.core import rate_limit


@pytest.fixture(autouse=True)
def _limpio():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_permite_hasta_el_limite_y_bloquea_el_siguiente():
    for _ in range(3):
        rate_limit.check("x", "1.2.3.4", limit=3, window_seconds=60)
    with pytest.raises(rate_limit.RateLimitExceeded):
        rate_limit.check("x", "1.2.3.4", limit=3, window_seconds=60)


def test_cada_clave_y_cada_bucket_cuentan_por_separado():
    for _ in range(3):
        rate_limit.check("x", "1.2.3.4", limit=3, window_seconds=60)
    rate_limit.check("x", "5.6.7.8", limit=3, window_seconds=60)   # otra IP
    rate_limit.check("y", "1.2.3.4", limit=3, window_seconds=60)   # otro bucket


def test_la_ventana_se_libera_con_el_tiempo(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: reloj[0])
    for _ in range(3):
        rate_limit.check("x", "ip", limit=3, window_seconds=60)
    reloj[0] += 61
    rate_limit.check("x", "ip", limit=3, window_seconds=60)  # ya no lanza

"""
Configuración común de pytest.

Ningún test llama a la API real de Together AI: costaría cuota, dependería
de internet y daría resultados distintos en cada corrida. Por defecto el
cliente "falla" y ai_advisor usa la plantilla (el mismo camino que sin API
key). Los tests de ai_advisor.py reemplazan `_client` por uno simulado.
"""

import pytest

from app.core import rate_limit
from app.services import ai_advisor


def _sin_red():
    raise RuntimeError("Los tests no llaman a la IA real.")


@pytest.fixture(autouse=True)
def _ia_sin_red(monkeypatch):
    monkeypatch.setattr(ai_advisor, "_client", _sin_red)
    rate_limit.reset()

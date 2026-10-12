"""
Límite de peticiones por IP (rate limiting) — en memoria, ventana deslizante.

Complementa el bloqueo por cuenta (5 fallos -> 15 min, ver auth_flow.py):
ese bloqueo frena a quien ataca UNA cuenta, pero no a quien prueba unas
pocas contraseñas en MUCHAS cuentas distintas, ni a quien pide códigos de
verificación sin parar para llenarle el correo a alguien. Pendiente #8 de
`wispr_terminal_professional/docs/BACKEND-PENDIENTE.md`.

En memoria (un diccionario por proceso), igual que los códigos MFA
pendientes: alcanza porque el MVP corre con UN solo worker (ver CONFIG AWS
en docs/arquitectura_mvp.md). Sin Redis a propósito (descartado en CLAUDE.md).

Detrás de nginx, la IP real llega en `X-Forwarded-For`; uvicorn la usa como
`request.client.host` solo si la petición viene de 127.0.0.1 (su valor por
defecto de `--forwarded-allow-ips`), así que un cliente no puede falsificarla.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

TOO_MANY = "Demasiados intentos seguidos. Espera un minuto y vuelve a intentarlo."

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class RateLimitExceeded(Exception):
    """Se traduce a HTTP 429 en main.py."""


def reset() -> None:
    """Solo para pruebas: vacía los contadores."""
    _hits.clear()


def check(bucket: str, key: str, limit: int, window_seconds: float) -> None:
    now = time.monotonic()
    hits = _hits[(bucket, key)]
    while hits and now - hits[0] > window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        raise RateLimitExceeded()
    hits.append(now)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def limit_per_ip(bucket: str, limit: int, window_seconds: float = 60):
    """Dependencia de FastAPI: `Depends(limit_per_ip("auth", 10))`."""

    def dependency(request: Request) -> None:
        check(bucket, client_ip(request), limit, window_seconds)

    return dependency


def too_many_response() -> JSONResponse:
    return JSONResponse(status_code=429, content={"ok": False, "error": TOO_MANY}, headers={"Retry-After": "60"})

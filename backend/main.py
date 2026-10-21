"""
Punto de entrada del backend. Acá se crea la aplicación FastAPI y se
registran todas las rutas disponibles.

Para correrlo en desarrollo (desde la carpeta backend/):
    uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.challenges import router as challenges_router
from app.api.groups import router as groups_router
from app.api.players import AuthRequiredError
from app.core.rate_limit import RateLimitExceeded, too_many_response
from app.api.players import router as players_router
from app.api.v1 import api_router
from app.core.config import settings

# En producción no se publica la documentación interactiva (/docs, /redoc,
# /openapi.json): le daría a un atacante el mapa completo de la API gratis.
_is_production = settings.ENVIRONMENT == "production"
app = FastAPI(
    title="WISPR API",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    Cabeceras de seguridad en todas las respuestas de la API:
    - nosniff: el navegador no "adivina" el tipo de un archivo descargado
      (un .pcap no se puede interpretar como HTML/JS).
    - DENY / frame-ancestors: la API no se puede incrustar en otra página
      (clickjacking).
    - no-referrer: no se filtra la URL en el encabezado Referer.
    - no-store: las respuestas (datos de jugador, ranking) no quedan en
      cachés compartidas.
    El CSP estricto va solo en /api: rompería la página /docs de desarrollo.
    HSTS lo agrega nginx (es quien termina HTTPS, ver CONFIG AWS).
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return response


@app.exception_handler(AuthRequiredError)
async def handle_auth_required(request: Request, exc: AuthRequiredError) -> JSONResponse:
    """
    Traduce una sesión inválida/vencida a la respuesta exacta que espera
    el frontend: `auth: "required"` lo distingue de un 401 por contraseña
    incorrecta en /login, que no lleva ese campo.
    """
    return JSONResponse(
        status_code=401,
        content={"ok": False, "auth": "required", "error": "Tu sesión expiró o no es válida. Inicia sesión de nuevo."},
    )

@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """HTTP 429 con el mismo formato `{ok, error}` que el resto de la API."""
    return too_many_response()


# CORS: la app de Electron / el frontend web corre en un origen distinto al
# de este servidor, así que el navegador bloquearía sus peticiones sin este
# permiso explícito. Los orígenes salen de CORS_ORIGINS ("*" en desarrollo;
# en producción, el dominio real — ver CONFIG AWS). Sin allow_credentials: el
# frontend manda el token en la cabecera Authorization, no usa cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=False,
    # DELETE: el panel admin y los grupos borran cuentas, grupos, miembros y tareas.
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# /api/players/* y /api/{challenges,submissions,ranking,progress,...}: calzan
# exacto con lo que ya llama wispr_terminal_professional (ver
# app/api/players.py y app/api/challenges.py). /api/v1/*: queda para
# endpoints futuros que no vienen de esa migración.
app.include_router(players_router, prefix="/api/players")
# Paneles de admin y profesor (20 oct, pendiente 7f): antes solo existían en
# el prototipo Node, y en modo conectado daban 404.
app.include_router(admin_router, prefix="/api/admin")
app.include_router(groups_router, prefix="/api/groups")
app.include_router(challenges_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def health_check() -> dict:
    """Ruta simple para confirmar que el servidor está vivo y responde."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}

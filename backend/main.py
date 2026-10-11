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

from app.api.challenges import router as challenges_router
from app.api.players import AuthRequiredError
from app.api.players import router as players_router
from app.api.v1 import api_router
from app.core.config import settings

app = FastAPI(title="WISPR API", version="0.1.0")


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

# CORS: la app de Electron corre en su propio proceso, en un origen
# distinto al de este servidor, así que el navegador bloquearía sus
# peticiones sin este permiso explícito. Se deja abierto ("*") para el
# desarrollo del MVP; conviene restringirlo a un origen específico antes
# de exponer el backend en producción.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/players/* y /api/{challenges,submissions,ranking,progress,...}: calzan
# exacto con lo que ya llama wispr_terminal_professional (ver
# app/api/players.py y app/api/challenges.py). /api/v1/*: queda para
# endpoints futuros que no vienen de esa migración.
app.include_router(players_router, prefix="/api/players")
app.include_router(challenges_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def health_check() -> dict:
    """Ruta simple para confirmar que el servidor está vivo y responde."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}

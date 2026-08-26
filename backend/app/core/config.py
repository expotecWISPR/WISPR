"""
Configuración central del backend.

Este módulo es el único lugar del proyecto donde se leen variables de entorno.
El resto del código nunca debe usar `os.environ` directamente — siempre importa
`settings` desde aquí. Así, si algún día cambia cómo se leen las variables (otro
archivo .env, un servicio de secretos, etc.), solo hay que tocar este archivo.

¿Por qué falla si falta una variable? Porque Pydantic valida los tipos y la
presencia de cada campo al crear el objeto Settings(). Si falta DATABASE_URL,
por ejemplo, el error aparece apenas arranca el servidor, con el nombre exacto
de la variable que falta — no un error críptico de conexión más adelante.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta absoluta a backend/.env. Se calcula así (en vez de solo ".env") para que
# la configuración se encuentre sin importar desde qué carpeta se ejecute el
# servidor (ej. "uvicorn app.main:app" desde backend/, o desde la raíz del repo).
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variables del .env que no estén declaradas aquí
    )

    # ── Base de datos (Supabase PostgreSQL) ──────────────────────────
    DATABASE_URL: str

    # ── Autenticación JWT ─────────────────────────────────────────────
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Together AI (recomendaciones, generación de retos) ────────────
    TOGETHER_API_KEY: str

    # ── AWS (S3 + CloudWatch) ──────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str

    # ── Entorno ──────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "production"] = "development"


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve la instancia de Settings, creándola una sola vez.

    FastAPI la inyecta donde se necesite con Depends(get_settings). El
    decorador lru_cache asegura que el .env se lea una única vez al arrancar,
    no en cada petición HTTP.
    """
    return Settings()


# Instancia lista para importar directamente: `from app.core.config import settings`.
settings = get_settings()

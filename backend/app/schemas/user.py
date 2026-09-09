"""
Schemas de la API para el recurso "usuario".

Los modelos (app/models/user.py) definen cómo se guardan los datos en la
base de datos. Estos schemas definen cómo entran y salen los datos por la
API — son como un control de aduana entre el frontend y el backend: nada
pasa sin cumplir las reglas de acá.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Datos que llegan al registrar un usuario nuevo (POST /auth/register)."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)


class UserPublic(BaseModel):
    """
    Datos que se devuelven al frontend al consultar un usuario.

    A propósito **no incluye `password_hash`** — el frontend no tiene
    ninguna razón para verlo, ni siquiera en su forma hasheada.
    """

    # from_attributes=True le permite a Pydantic construir este schema
    # directamente desde un objeto User de SQLAlchemy (leyendo sus
    # atributos: user.id, user.email, etc.), no solo desde un diccionario.
    # Se usará así en los endpoints: UserPublic.model_validate(user).
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    points: int
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    """
    Datos opcionales para actualizar el perfil (PATCH /users/me).

    Todos los campos son opcionales (por defecto None) porque quien llama
    puede querer cambiar solo el username, solo el email, o ninguno.
    """

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None


class Token(BaseModel):
    """
    Respuesta al hacer login exitoso (POST /auth/login).

    `token_type` casi siempre es "bearer" — le dice al cliente cómo debe
    mandar el token en las siguientes peticiones:
    header `Authorization: Bearer <access_token>`.
    """

    access_token: str
    token_type: str = "bearer"

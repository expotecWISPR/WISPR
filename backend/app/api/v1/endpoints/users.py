"""
Endpoints relacionados al usuario autenticado.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Devuelve el perfil del usuario dueño del token que mandó la petición.

    Depends(get_current_user) es lo que protege esta ruta: si no viene un
    JWT válido en el header Authorization, nunca se llega a esta línea.
    """
    return current_user

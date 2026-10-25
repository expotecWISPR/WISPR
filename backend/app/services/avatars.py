"""
Foto de perfil: el jugador elige uno de los avatares fijos de Wisp.

Solo se aceptan los ids de `AVATARS` (las imágenes viven en el frontend,
`WISPR-frontend/img/avatars/<id>.png`); así nadie puede guardar una URL o un
texto arbitrario que luego se pinte en el ranking de otros jugadores.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from app.models.user import User

AVATARS = ("router", "corazon", "codigo", "escaner", "saludo", "laptop", "escudo")


def set_avatar(db: DbSession, user: User, avatar) -> dict:
    """Guarda el avatar; `None` o "" vuelve a la inicial del nombre."""
    if avatar in (None, ""):
        user.avatar = None
    elif avatar in AVATARS:
        user.avatar = avatar
    else:
        return {"ok": False, "error": "Avatar inválido."}
    db.commit()
    return {"ok": True, "avatar": user.avatar}

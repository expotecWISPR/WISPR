"""
Seguridad: hash de contraseñas y tokens JWT.

Dos responsabilidades separadas en este archivo:

1. Contraseñas: nunca se guarda la contraseña real en la base de datos,
   solo su hash (con bcrypt, ya lo usamos en el modelo User como
   `password_hash`). `hash_password()` la convierte antes de guardarla;
   `verify_password()` compara una contraseña en texto plano contra el
   hash guardado, sin necesitar "revertir" el hash (eso no se puede).

2. JWT (JSON Web Token): la credencial que prueba que un usuario ya inició
   sesión. `create_access_token()` genera uno al hacer login;
   `decode_access_token()` lo verifica en cada petición protegida.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt trabaja con bytes, no con texto directamente, y tiene un límite
# real del algoritmo: no puede procesar contraseñas de más de 72 bytes.
# En vez de truncar en silencio (dos contraseñas distintas podrían terminar
# generando el mismo hash), preferimos avisar con un error claro.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Convierte una contraseña en texto plano a su hash con bcrypt."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"La contraseña no puede superar los {_MAX_PASSWORD_BYTES} bytes.")

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compara una contraseña en texto plano contra un hash ya guardado.

    Devuelve True si coinciden, False si no. bcrypt no "desencripta" el
    hash guardado — vuelve a hashear `plain_password` con la misma sal
    (que va incluida dentro del propio hash) y compara los resultados.
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Genera un JWT firmado, con el contenido de `data` adentro.

    Se usa así al hacer login: create_access_token({"sub": user.email}).
    `expires_delta` permite personalizar cuánto dura el token; si no se
    pasa, se usa settings.ACCESS_TOKEN_EXPIRE_MINUTES (60 min por defecto).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Verifica un JWT y devuelve su contenido si es válido.

    Devuelve None si el token está mal firmado, corrupto, o ya expiró —
    nunca lanza una excepción hacia afuera, para que quien lo use pueda
    simplemente revisar "¿dio None? entonces no está autenticado."
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

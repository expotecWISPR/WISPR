"""
Seguridad: hash de contraseñas.

Nunca se guarda la contraseña real en la base de datos, solo su hash (con
bcrypt, en `User.password_hash`). `hash_password()` la convierte antes de
guardarla; `verify_password()` compara una contraseña en texto plano contra
el hash guardado, sin necesitar "revertir" el hash (eso no se puede).

Las funciones de JWT (`create_access_token`/`decode_access_token`) se
quitaron el 12 oct: desde el 7 oct las sesiones son tokens opacos
revocables guardados en la BD (`app/core/sessions.py`), así que el JWT ya no
se usaba, y su dependencia (`python-jose`) arrastraba vulnerabilidades
conocidas (ver docs/pruebas_seguridad.md).
"""

import bcrypt

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
    password_bytes = plain_password.encode("utf-8")
    # Ninguna contraseña guardada puede pasar de 72 bytes (hash_password lo
    # impide), así que una más larga nunca coincide. Se corta acá porque
    # bcrypt.checkpw lanza ValueError con más de 72 bytes, y eso salía como
    # un error 500 en el login.
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))

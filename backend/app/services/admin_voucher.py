"""
Voucher de las cuentas admin: un secreto largo, propio de cada admin, que el
login pide después de la contraseña (ver auth_flow.begin_login).

Solo se guarda su hash. Se emite desde el servidor, no desde la web, para que
una sesión admin robada no pueda cambiarlo:

    python -m app.services.admin_voucher admin_wispr

Va sin arroba: en PowerShell, @admin_wispr se interpreta como otra cosa.

Emitir uno nuevo invalida el anterior. Si se pierde, se emite otro.
"""

from __future__ import annotations

import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.security import hash_password, verify_password
from app.models.user import User

# Sin 0/O ni 1/I/L: se dicta y se copia a mano sin confundirlos.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_GROUPS = 5
_GROUP_LENGTH = 4


def generate_voucher() -> str:
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LENGTH)) for _ in range(_GROUPS)]
    return "-".join(groups)


def normalize(voucher) -> str:
    """Acepta minúsculas y espacios de más al copiarlo."""
    return "".join(str(voucher or "").split()).upper()[:64]


def matches(user: User, voucher) -> bool:
    return bool(user.admin_voucher_hash) and verify_password(normalize(voucher), user.admin_voucher_hash)


def issue(db: DbSession, user: User) -> str:
    """Emite el voucher y devuelve el texto: es la única vez que se puede ver."""
    if user.role != "admin":
        raise ValueError("Solo las cuentas admin usan voucher.")
    voucher = generate_voucher()
    user.admin_voucher_hash = hash_password(voucher)
    db.commit()
    return voucher


def main() -> int:
    from app.db import base  # noqa: F401  (registra los modelos)
    from app.db.session import SessionLocal
    from app.services.auth_flow import normalize_handle

    if len(sys.argv) != 2:
        print("Uso: python -m app.services.admin_voucher usuario")
        return 2
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == normalize_handle(sys.argv[1]))).scalar_one_or_none()
        if user is None or user.role != "admin":
            print("Esa cuenta no existe o no es admin.")
            return 1
        voucher = issue(db, user)
    print(f"Voucher de {sys.argv[1]} (guárdalo: no se vuelve a mostrar):")
    print(voucher)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

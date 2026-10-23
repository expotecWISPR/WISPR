"""
Modelo de la tabla `users`.

Cada fila de esta tabla es una cuenta registrada en WISPR. Esta clase
Python es la que SQLAlchemy traduce a una tabla SQL real en Supabase.

Ampliado (7 oct) al migrar el auth con MFA por correo que se prototipó en
`wispr_terminal_professional` (ver CLAUDE.md, checkpoint 13 sep / 7 oct):
`full_name`, `gender`, `role` y los campos de bloqueo por fuerza bruta son
nuevos; `username` se reutiliza como "handle" (se guarda con el prefijo
`@`, igual que el prototipo, para que la respuesta de `/api/players/me`
no necesite reformatear nada del lado del frontend).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Handle del jugador, con el prefijo "@" incluido (ej. "@yuran") — igual
    # que `player.handle` en el prototipo Node. El nombre de columna se deja
    # como "username" para no tener que tocar la migración original.
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    # "estudiante" | "profesor" | "admin" — lo decide el dominio del correo al
    # registrarse (ver app/services/auth_flow.py::role_for_email); "admin" se
    # asigna a mano en la base de datos, no hay flujo todavía para crearlo.
    role: Mapped[str] = mapped_column(String(20), default="estudiante", nullable=False)

    # Nunca se guarda la contraseña real, solo su hash con bcrypt (security.py).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Un admin le emitió una contraseña temporal: debe cambiarla al entrar
    # (ver app/services/admin.py y POST /api/players/change-password).
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Bloqueo manual (lo marca un admin) vs. automático (fuerza bruta, ver
    # recordFailedLogin en el prototipo): distintos del `is_active` general.
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Motivo del bloqueo manual, opcional; el panel admin lo muestra.
    lock_reason: Mapped[str] = mapped_column(String(200), default="", server_default="", nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_login_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cuándo terminó (o saltó) el recorrido de bienvenida con Wisp. NULL = la
    # próxima vez que entre se le muestra. Va en la base y no en el navegador
    # para que no se repita al entrar desde otro equipo o desde Electron.
    tour_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        # Solo para que, al imprimir un User mientras depuramos, se vea algo
        # legible en vez de "<app.models.user.User object at 0x7f...>".
        return f"<User id={self.id} username={self.username!r}>"

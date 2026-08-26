"""
Modelo de la tabla `users`.

Cada fila de esta tabla es un estudiante registrado en WISPR. Esta clase
Python es la que SQLAlchemy traduce a una tabla SQL real en Supabase.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    # Nunca se guarda la contraseña real, solo su hash (ver security.py, el
    # siguiente archivo que vamos a construir).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

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

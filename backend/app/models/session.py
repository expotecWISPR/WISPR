"""
Modelo de la tabla `sessions`.

Reemplaza al JWT stateless de la primera versión de `security.py`. Acá el
servidor guarda solo el **hash SHA-256** de cada token de sesión que emite
(nunca el token real) — así una sesión se puede revocar de verdad (logout,
bloqueo de cuenta, reseteo de contraseña) borrando la fila, en vez de
esperar a que el token expire solo como pasaría con un JWT. Es el mismo
esquema que ya se probó con correo real en `wispr_terminal_professional`
(ahí vivía en `lab/data/sessions.json`; acá vive en Supabase).

Ver `app/core/sessions.py` para la lógica de creación/validación/revocación.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Session(Base):
    __tablename__ = "sessions"

    # El propio hash es la clave primaria: no hace falta un id aparte, y
    # buscar una sesión por token es un lookup directo por PK.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # Se refresca en cada petición autenticada (como mucho una vez por minuto,
    # para no reescribir la fila en cada request) — de ahí sale la expiración
    # por inactividad.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Session user_id={self.user_id} last_seen_at={self.last_seen_at!r}>"

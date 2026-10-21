"""
Modelo de la tabla `hint_unlocks`: qué pista de qué reto abrió cada jugador.

Antes (hasta el 20 oct) el texto de todas las pistas viajaba al navegador y a
`active.json` de la terminal; el botón "Mostrar" solo las ocultaba en pantalla,
así que se podían leer gratis. Ahora el backend entrega cada pista recién
cuando el jugador la pide y la anota acá, para descontar puntos al resolver
el reto y para el motor adaptativo (ver app/services/hints.py).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HintUnlock(Base):
    __tablename__ = "hint_unlocks"

    # Clave primaria compuesta: abrir la misma pista dos veces no la cobra dos veces.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    hint_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

"""
Modelo de la tabla `challenge_timers`: cuándo abrió cada jugador cada reto.

El cronómetro del reto (22 oct) lo lleva el SERVIDOR: la primera vez que el
jugador abre un reto se guarda la hora, y no cambia aunque recargue la página
o cambie de dispositivo. El bono de velocidad (app/services/bonus.py) se
calcula con esta hora; si no existe (alguien envió la flag sin abrir el reto,
por ejemplo con un script), no hay bono.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChallengeTimer(Base):
    __tablename__ = "challenge_timers"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

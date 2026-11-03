"""
Modelo de la tabla `challenge_ratings`: las estrellas (1 a 5) que cada jugador
le pone a un reto que resolvió, desde el informe que aparece al resolverlo.

Una fila por (jugador, reto): calificar otra vez reemplaza la nota anterior.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChallengeRating(Base):
    __tablename__ = "challenge_ratings"
    __table_args__ = (CheckConstraint("stars BETWEEN 1 AND 5", name="ck_challenge_ratings_stars"),)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

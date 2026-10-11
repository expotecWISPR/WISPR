"""
Modelo de la tabla `lesson_progress`: progreso de las lecciones de Teoría.

En el prototipo vivía en `player.lessonProgress[lessonId]` dentro de
`lab/data/players.json` (ver `mergeLessonProgress` en server.js). Las
lecciones se resuelven en el navegador; el servidor solo acota rangos y
conserva el MEJOR intento. El XP de Teoría es independiente del puntaje CTF
a propósito (no entra al ranking) — igual que en el prototipo.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Formato `^[a-z0-9][a-z0-9-]{1,47}$` (validado en el servicio, no acá).
    lesson_id: Mapped[str] = mapped_column(String(48), primary_key=True)

    completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100, el mejor
    xp: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-200, el mejor
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(60), nullable=True)

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<LessonProgress user_id={self.user_id} lesson_id={self.lesson_id!r} percent={self.percent}>"

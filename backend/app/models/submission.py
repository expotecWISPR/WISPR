"""
Modelos de las tablas `submissions` y `solves`.

En el prototipo Node esto vivía dentro de cada jugador en
`lab/data/players.json` (ver `recordSubmission` en server.js):
  - `player.submissions` → lista de intentos (correctos o no).
  - `player.attempts[id]` → contador de intentos por reto.
  - `player.solved[id]`  → primer acierto por reto, con los puntos ganados.

Acá se separa en dos tablas:

* `submissions`: UNA fila por intento. De acá salen los intentos por reto
  (contando filas) y la racha del ranking (aciertos seguidos más recientes).
  El prototipo recortaba la lista a los últimos 100; en una base de datos no
  hace falta recortar nada.
* `solves`: UNA fila por (jugador, reto) resuelto. Es una tabla aparte, y no
  "el primer submission correcto", por la restricción de clave primaria:
  la base de datos garantiza que un reto no sume puntos dos veces aunque
  lleguen dos envíos correctos al mismo tiempo (dos pestañas, web +
  terminal). También congela los puntos del momento del acierto: si un
  docente cambia después los puntos del reto, el ranking no se reescribe.

No se guarda el texto de la flag enviada: el prototipo tampoco lo hacía, y
no aporta nada (los intentos fallidos podrían contener cualquier cosa).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Sin ondelete: un reto con envíos no se puede borrar (se desactiva con
    # `Challenge.is_active`), para no romper el historial.
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id"), nullable=False, index=True
    )
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # "web" (formulario del frontend) | "terminal" (`ctf submit` en Kali).
    source: Mapped[str] = mapped_column(String(10), default="web", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<Submission user_id={self.user_id} challenge_id={self.challenge_id!r} correct={self.correct}>"


class Solve(Base):
    __tablename__ = "solves"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id"), primary_key=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    solved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # 22 oct (app/services/bonus.py): "limpio" = sin pistas ni intentos
    # fallidos; alimenta la racha limpia. `breakdown` guarda el desglose de los
    # puntos (base, pistas, intentos, velocidad, racha) para mostrarlo después.
    clean: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Solve user_id={self.user_id} challenge_id={self.challenge_id!r} points={self.points}>"

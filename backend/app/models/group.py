"""
Modelos de grupos de clase: `groups`, `group_members` y `group_tasks`.

Migrado (20 oct) de `lab/data/groups.json` del prototipo Node
(`WISPR-frontend/server.js`). Un profesor arma sus grupos, agrega estudiantes
ya registrados y les asigna tareas; un admin puede ver y gestionar todos.

Diferencias con el prototipo:
- Los miembros viven en su propia tabla (no en una lista dentro del grupo):
  la clave primaria (grupo, estudiante) impide que alguien quede dos veces en
  el mismo grupo, igual que `solves` impide sumar puntos dos veces.
- Si se borra la cuenta del profesor, el grupo se conserva con `owner_id`
  NULL (el frontend lo muestra como "(profesor eliminado)", igual que antes).
- Si se borra un estudiante, la base lo saca sola de todos los grupos
  (ON DELETE CASCADE); en el prototipo había que recorrer los grupos a mano.

El cumplimiento de una tarea ligada a un reto NO se guarda: el frontend lo
calcula con los `solved` reales de cada miembro, así nunca se desincroniza.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Group(Base):
    __tablename__ = "groups"

    # UUID en texto, como en el prototipo (el frontend lo trata como string).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    def __repr__(self) -> str:
        return f"<Group id={self.id!r} name={self.name!r}>"


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class GroupTask(Base):
    __tablename__ = "group_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Tarea ligada a un reto (opcional): se cumple sola cuando el estudiante
    # lo resuelve. Si el reto desaparece, la tarea queda como tarea normal.
    challenge_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True
    )
    # Solo para tareas SIN reto: el profesor la marca como hecha a mano.
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

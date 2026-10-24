"""
Progreso de las lecciones de Teoría.

Migrado 1:1 de `mergeLessonProgress` en `wispr_terminal_professional/server.js`:
las lecciones se resuelven en el navegador, el servidor solo valida rangos y
conserva el MEJOR intento (percent/xp nunca bajan). Se devuelve con la forma
de `player.lessonProgress` (camelCase, tiempos en ms) porque el frontend la
lee tal cual.

Nota mínima (24 oct): una lección solo cuenta como completada con al menos
`PASSING_PERCENT` en el quiz; con menos hay que repetirla. Las misiones finales
(id terminado en `-mision`) no tienen quiz y quedan fuera de esta regla.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import as_utc
from app.models.lesson_progress import LessonProgress

LESSON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$")
MAX_LESSONS = 200
PASSING_PERCENT = 75  # 3 de 4 respuestas correctas
MISSION_SUFFIX = "-mision"


def is_mission(lesson_id: str) -> bool:
    return lesson_id.endswith(MISSION_SUFFIX)


def passed(lesson_id: str, percent: int) -> bool:
    return is_mission(lesson_id) or percent >= PASSING_PERCENT


def _ms(value: datetime) -> int:
    return int(as_utc(value).timestamp() * 1000)


def _round(value) -> int | None:
    """`Math.round(Number(x))` de JS: None si no es un número finito."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # floor(x + 0.5) redondea igual que JS (2.5 -> 3); round() de Python no (2.5 -> 2).
    return math.floor(number + 0.5) if math.isfinite(number) else None


def _public(row: LessonProgress) -> dict:
    data = {
        # Las lecciones guardadas antes de la nota mínima con menos de 75 % no
        # cuentan: el estudiante tiene que repetirlas (su mejor intento sigue ahí).
        "completed": row.completed and passed(row.lesson_id, row.percent),
        "percent": row.percent,
        "xp": row.xp,
        "attempts": row.attempts,
        "completedAt": _ms(row.completed_at),
        "updatedAt": _ms(row.updated_at),
    }
    if row.badge is not None:
        data["badge"] = row.badge
    return data


def lesson_progress(db: DbSession, user_id: int) -> dict:
    rows = db.scalars(select(LessonProgress).where(LessonProgress.user_id == user_id))
    return {row.lesson_id: _public(row) for row in rows}


def merge_lesson_progress(db: DbSession, user_id: int, lesson_id, report: dict) -> dict:
    lesson_id = str(lesson_id or "")
    if not LESSON_ID_RE.match(lesson_id):
        return {"ok": False, "error": "Lección inválida."}
    percent = _round(report.get("percent"))
    xp = _round(report.get("xp"))
    if percent is None or not 0 <= percent <= 100:
        return {"ok": False, "error": "Porcentaje inválido."}
    if xp is None or not 0 <= xp <= 200:
        return {"ok": False, "error": "XP inválido."}
    if not passed(lesson_id, percent):
        return {"ok": False, "error": f"Necesitas al menos {PASSING_PERCENT} % en el quiz para completar la lección."}

    previous = db.get(LessonProgress, (user_id, lesson_id))
    if previous is None:
        count = db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.user_id == user_id))
        if count >= MAX_LESSONS:
            return {"ok": False, "error": "Demasiadas lecciones registradas."}

    now = datetime.now(timezone.utc)
    attempts = max(0, min(9999, _round(report.get("attempts")) or 0))
    badge = report.get("badge")
    if previous is None:
        db.add(LessonProgress(
            user_id=user_id, lesson_id=lesson_id, completed=True, percent=percent, xp=xp, attempts=attempts,
            badge=badge[:60] if isinstance(badge, str) else None, completed_at=now, updated_at=now,
        ))
    else:
        previous.completed = True
        previous.percent = max(previous.percent, percent)
        previous.xp = max(previous.xp, xp)
        previous.attempts = attempts
        if isinstance(badge, str):
            previous.badge = badge[:60]
        previous.updated_at = now
    db.commit()
    return {"ok": True}

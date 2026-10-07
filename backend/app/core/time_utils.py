"""
Utilidad mínima para comparar fechas sin que un backend de base de datos
distinto rompa la resta.

Postgres (Supabase, lo que usa el proyecto de verdad) conserva el `tzinfo`
en columnas `DateTime(timezone=True)`. SQLite —lo que usan las pruebas
unitarias, para no depender de Supabase— no: al releer el valor desde la
base, vuelve "naive" (sin zona). `as_utc()` normaliza eso para que
`datetime.now(timezone.utc) - valor` nunca falle, en ningún motor.
"""

from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)

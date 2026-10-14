"""
Carga el catálogo de retos (`challenges/catalog/catalog.json`) en la base de
datos.

Desde backend/:
    python -m app.db.seed_challenges

Se puede correr las veces que haga falta: actualiza los retos existentes en
vez de duplicarlos. Va en el despliegue después de `alembic upgrade head`.
Desde el 13 oct ya no genera archivos: los de XOR y WEP se crean por jugador
la primera vez que los pide (app/services/instances.py).
"""

import app.db.base  # noqa: F401 — registra TODOS los modelos (challenges.owner_id apunta a users)
from app.db.session import SessionLocal
from app.services.challenges import seed_catalog


def main() -> None:
    db = SessionLocal()
    try:
        seeded = seed_catalog(db)
    finally:
        db.close()
    print(f"{len(seeded)} retos cargados: {', '.join(seeded)}")


if __name__ == "__main__":
    main()

"""
Conexión con la base de datos (Supabase PostgreSQL).

Este módulo define las piezas que el resto del backend necesita para hablar
con la base de datos:

- `engine`: la conexión real, configurada con la URL que ya valida config.py.
- `SessionLocal`: una "fábrica" que crea sesiones (conversaciones con la BD).
- `Base`: la clase de la que heredan todos los modelos (User, Challenge, etc.).
- `get_db()`: función que FastAPI usa para entregarle una sesión a cada
  petición HTTP, y cerrarla automáticamente cuando esa petición termina.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# El "motor": sabe cómo conectarse a Supabase, pero todavía no abre ninguna
# conexión hasta que alguien la pida.
engine = create_engine(settings.DATABASE_URL)

# Fábrica de sesiones. Cada vez que se llama SessionLocal(), se crea una
# sesión nueva (una conversación independiente con la base de datos).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos del proyecto.

    Cuando `models/user.py` escriba `class User(Base):`, SQLAlchemy sabe que
    esa clase representa una tabla real en la base de datos.
    """


def get_db() -> Generator[Session, None, None]:
    """
    Entrega una sesión de base de datos y garantiza que se cierre al terminar.

    Se usa en los endpoints así: `def endpoint(db: Session = Depends(get_db))`.
    FastAPI llama esta función antes de ejecutar el endpoint, le pasa la
    sesión (`db`), y cuando el endpoint termina (con éxito o con error),
    FastAPI vuelve a entrar acá y ejecuta el `finally` para cerrarla.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

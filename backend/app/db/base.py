"""
Punto central de importación de modelos, para uso exclusivo de Alembic.

Alembic (la herramienta de migraciones) necesita "ver" todas las clases que
heredan de Base para poder comparar el estado de la base de datos contra el
código y generar automáticamente el SQL de la migración. Si un modelo nunca
se importa desde algún archivo que Alembic lea, Alembic simplemente no sabe
que existe.

Este archivo no se usa en la lógica de la aplicación — solo lo importa
`migrations/env.py`. Cada vez que se cree un modelo nuevo (Challenge,
Submission, Category), se agrega su import acá.
"""

from app.db.session import Base  # noqa: F401

from app.models.user import User  # noqa: F401

"""
Script que Alembic ejecuta cada vez que generamos o aplicamos una migración.

Conecta dos piezas del proyecto con Alembic:

1. `Base.metadata` (de app/db/base.py) — la lista de modelos (User, y los
   que se agreguen después). Con esto, Alembic puede comparar los modelos
   Python contra la base de datos real y generar el SQL automáticamente
   (esto se llama "autogenerate").
2. `settings.DATABASE_URL` (de app/core/config.py) — para que Alembic se
   conecte a la misma base de datos que usa el resto del backend, sin
   repetir la URL (ni su contraseña) en ningún otro archivo.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base  # importa Base + todos los modelos ya registrados

# Objeto de configuración de Alembic; da acceso a los valores de alembic.ini.
config = context.config

# Activa el logging de Alembic según la sección [loggers] de alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Sobrescribe el sqlalchemy.url vacío de alembic.ini con la URL real del .env.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Los modelos que Alembic debe conocer para poder autogenerar migraciones.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Genera el SQL de la migración sin conectarse a la base de datos.

    Se usa con `alembic upgrade head --sql` para revisar el SQL antes de
    aplicarlo. No lo usamos por ahora, pero Alembic exige que esté definido.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Se conecta de verdad a la base de datos y aplica la migración.

    Este es el modo que usamos siempre: `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

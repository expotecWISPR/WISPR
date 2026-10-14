"""retos por jugador: archivo de cada instancia y dueño de los retos generados

Guía del ingeniero (13 oct), fases 3-5:
- `challenge_instances.artifact`: ruta del archivo propio de cada jugador
  (relativa a challenges/generated/), para que dos jugadores no reciban el
  mismo archivo ni la misma flag.
- `challenges.owner_id`: los retos que crea el motor adaptativo (con
  historia de la IA) son de un solo jugador. NULL = reto del catálogo.
Solo agrega columnas que aceptan NULL: no toca datos existentes.

Revision ID: 4c7e2a91d0b5
Revises: dba06aee3303
Create Date: 2026-10-13 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c7e2a91d0b5'
down_revision: Union[str, None] = 'dba06aee3303'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('challenge_instances', sa.Column('artifact', sa.String(length=255), nullable=True))
    op.add_column('challenges', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_challenges_owner_id'), 'challenges', ['owner_id'], unique=False)
    op.create_foreign_key('fk_challenges_owner_id_users', 'challenges', 'users', ['owner_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_challenges_owner_id_users', 'challenges', type_='foreignkey')
    op.drop_index(op.f('ix_challenges_owner_id'), table_name='challenges')
    op.drop_column('challenges', 'owner_id')
    op.drop_column('challenge_instances', 'artifact')

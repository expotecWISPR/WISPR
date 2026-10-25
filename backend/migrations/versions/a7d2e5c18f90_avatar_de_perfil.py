"""avatar de perfil

24 oct: `users.avatar` guarda cuál de los avatares fijos de Wisp eligió el
jugador como foto de perfil (ver app/services/avatars.py). Las cuentas que ya
existen quedan en NULL y siguen mostrando la inicial de su nombre.

Revision ID: a7d2e5c18f90
Revises: f4c1a8e93b26
Create Date: 2026-10-24 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d2e5c18f90'
down_revision: Union[str, None] = 'f4c1a8e93b26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('avatar', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar')

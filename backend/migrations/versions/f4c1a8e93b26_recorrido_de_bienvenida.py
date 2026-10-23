"""recorrido de bienvenida con Wisp

22 oct: `users.tour_seen_at` guarda cuándo el jugador terminó o saltó el
recorrido de bienvenida. Las cuentas que ya existen quedan en NULL: lo verán
una vez la próxima vez que entren.

Revision ID: f4c1a8e93b26
Revises: e2b8c6d05a71
Create Date: 2026-10-22 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c1a8e93b26'
down_revision: Union[str, None] = 'e2b8c6d05a71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('tour_seen_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'tour_seen_at')

"""cronómetro de los retos y desglose de puntos (bonos y penalizaciones)

22 oct (app/services/bonus.py):
- `challenge_timers`: cuándo abrió cada jugador cada reto (bono de velocidad).
- `solves.clean`: resuelto sin pistas ni intentos fallidos (racha limpia).
- `solves.breakdown`: desglose de los puntos ganados.
Los aciertos anteriores quedan con clean = false y sin desglose.

Revision ID: e2b8c6d05a71
Revises: d7a4f19c3e58
Create Date: 2026-10-22 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b8c6d05a71'
down_revision: Union[str, None] = 'd7a4f19c3e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'challenge_timers',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.String(length=80), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'challenge_id'),
    )
    op.add_column('solves', sa.Column('clean', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('solves', sa.Column('breakdown', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('solves', 'breakdown')
    op.drop_column('solves', 'clean')
    op.drop_table('challenge_timers')

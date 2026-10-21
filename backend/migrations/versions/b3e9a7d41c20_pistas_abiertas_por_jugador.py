"""pistas abiertas por jugador (descuento de puntos por pista)

Pendiente 7e(a) (20 oct): cada pista abierta antes de resolver un reto resta
puntos y cuenta para la dificultad adaptativa. Solo crea una tabla nueva.

Revision ID: b3e9a7d41c20
Revises: 8f1d3c6a2b47
Create Date: 2026-10-20 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e9a7d41c20'
down_revision: Union[str, None] = '8f1d3c6a2b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hint_unlocks',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.String(length=80), nullable=False),
        sa.Column('hint_index', sa.Integer(), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'challenge_id', 'hint_index'),
    )


def downgrade() -> None:
    op.drop_table('hint_unlocks')

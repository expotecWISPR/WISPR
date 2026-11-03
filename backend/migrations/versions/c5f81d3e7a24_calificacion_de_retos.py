"""calificacion de retos

2 nov: `challenge_ratings` guarda las estrellas (1 a 5) que cada jugador le pone
a un reto resuelto, desde el informe que aparece al resolverlo (ver
app/services/ratings.py).

Revision ID: c5f81d3e7a24
Revises: a7d2e5c18f90
Create Date: 2026-11-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f81d3e7a24'
down_revision: Union[str, None] = 'a7d2e5c18f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'challenge_ratings',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.String(length=80), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('stars BETWEEN 1 AND 5', name='ck_challenge_ratings_stars'),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'challenge_id'),
    )


def downgrade() -> None:
    op.drop_table('challenge_ratings')

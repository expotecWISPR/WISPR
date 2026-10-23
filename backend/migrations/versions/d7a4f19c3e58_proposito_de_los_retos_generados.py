"""propósito de los retos generados (practice / adaptive / class)

22 oct: los retos de práctica (los que pide el estudiante) empiezan a dar
puntos, así que ya no se pueden reconocer por tener 0 puntos. Se agrega
`challenges.purpose` y se rellena con lo que antes se deducía:
- dueño + 0 puntos  -> "practice"
- dueño + puntos    -> "adaptive"
- generado sin dueño -> "class"
- catálogo          -> NULL

Revision ID: d7a4f19c3e58
Revises: b3e9a7d41c20
Create Date: 2026-10-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a4f19c3e58'
down_revision: Union[str, None] = 'b3e9a7d41c20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('challenges', sa.Column('purpose', sa.String(length=10), nullable=True))
    op.execute("UPDATE challenges SET purpose = 'practice' WHERE owner_id IS NOT NULL AND points = 0")
    op.execute("UPDATE challenges SET purpose = 'adaptive' WHERE owner_id IS NOT NULL AND points > 0")
    op.execute("UPDATE challenges SET purpose = 'class' WHERE owner_id IS NULL AND generated = true")


def downgrade() -> None:
    op.drop_column('challenges', 'purpose')

"""voucher de administrador

2 nov: `users.admin_voucher_hash` guarda el hash del voucher que pide el login
de una cuenta admin (ver app/services/admin_voucher.py). Sin voucher emitido, la
cuenta admin no puede entrar.

Revision ID: e8b3a6f42c17
Revises: c5f81d3e7a24
Create Date: 2026-11-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b3a6f42c17'
down_revision: Union[str, None] = 'c5f81d3e7a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('admin_voucher_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'admin_voucher_hash')

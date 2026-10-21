"""grupos de clase, sus miembros y tareas + motivo del bloqueo manual

Pendiente 7f (20 oct): paneles de admin y profesor en FastAPI.
- `groups`, `group_members`, `group_tasks`: antes vivían en
  `lab/data/groups.json` del prototipo Node.
- `users.lock_reason`: motivo opcional cuando un admin bloquea una cuenta.
Solo crea tablas y agrega una columna con valor por defecto: no toca datos.

Revision ID: 8f1d3c6a2b47
Revises: 4c7e2a91d0b5
Create Date: 2026-10-20 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1d3c6a2b47'
down_revision: Union[str, None] = '4c7e2a91d0b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('lock_reason', sa.String(length=200), server_default='', nullable=False))

    op.create_table(
        'groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_groups_owner_id'), 'groups', ['owner_id'], unique=False)

    op.create_table(
        'group_members',
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('group_id', 'user_id'),
    )
    op.create_index(op.f('ix_group_members_user_id'), 'group_members', ['user_id'], unique=False)

    op.create_table(
        'group_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('challenge_id', sa.String(length=80), nullable=True),
        sa.Column('done', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_group_tasks_group_id'), 'group_tasks', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_group_tasks_group_id'), table_name='group_tasks')
    op.drop_table('group_tasks')
    op.drop_index(op.f('ix_group_members_user_id'), table_name='group_members')
    op.drop_table('group_members')
    op.drop_index(op.f('ix_groups_owner_id'), table_name='groups')
    op.drop_table('groups')
    op.drop_column('users', 'lock_reason')

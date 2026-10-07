"""auth con MFA: ampliar users + tabla sessions

Escrita a mano (no con --autogenerate) porque Supabase estaba pausado al
momento de escribirla — ver nota recurrente en CLAUDE.md. Antes de
aplicarla: reactivar el proyecto en supabase.com y borrar cualquier
usuario de prueba de la tabla `users` real, porque `full_name`, `gender` y
`role` quedan NOT NULL sin valor por defecto.

Revision ID: 27e315b1d2f6
Revises: 1b4b30f0b1aa
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27e315b1d2f6'
down_revision: Union[str, None] = '1b4b30f0b1aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('users', sa.Column('gender', sa.String(length=20), nullable=False, server_default=''))
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, server_default='estudiante'))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('failed_login_window_started_at', sa.DateTime(timezone=True), nullable=True))

    # Los server_default de arriba solo existen para que el ALTER TABLE no
    # falle si ya hay filas (ej. usuarios de prueba que quedaron sin borrar);
    # de ahí en adelante el valor lo pone siempre la aplicación, no la BD.
    op.alter_column('users', 'full_name', server_default=None)
    op.alter_column('users', 'gender', server_default=None)

    op.create_table(
        'sessions',
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token_hash'),
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')

    op.drop_column('users', 'failed_login_window_started_at')
    op.drop_column('users', 'failed_login_count')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'locked')
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'role')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'full_name')

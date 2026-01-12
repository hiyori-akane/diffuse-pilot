"""Remove queued_tasks table - migrating to asyncio.Queue

Revision ID: 22b435d1c0a2
Revises: 009bc3591fc6
Create Date: 2025-11-13 23:35:06.995700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22b435d1c0a2'
down_revision: Union[str, Sequence[str], None] = '009bc3591fc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # queued_tasks テーブルを削除（asyncio.Queue に移行）
    op.drop_table('queued_tasks')


def downgrade() -> None:
    """Downgrade schema."""
    # queued_tasks テーブルを再作成
    op.create_table('queued_tasks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('task_type', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

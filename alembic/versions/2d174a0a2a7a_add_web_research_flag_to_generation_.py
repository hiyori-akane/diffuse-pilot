"""add_web_research_flag_to_generation_requests

Revision ID: 2d174a0a2a7a
Revises: afa3fefb6ffa
Create Date: 2025-11-22 14:38:26.539944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d174a0a2a7a'
down_revision: Union[str, Sequence[str], None] = 'afa3fefb6ffa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('generation_requests', sa.Column('web_research', sa.Boolean, nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('generation_requests', 'web_research')

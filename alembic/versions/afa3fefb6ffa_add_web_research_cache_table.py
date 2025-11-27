"""add_web_research_cache_table

Revision ID: afa3fefb6ffa
Revises: 92746fe8181c
Create Date: 2025-11-22 14:33:43.740097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afa3fefb6ffa'
down_revision: Union[str, Sequence[str], None] = '92746fe8181c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'web_research_cache',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('query_hash', sa.String(64), nullable=False, index=True, unique=True),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('results', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('expires_at', sa.DateTime, nullable=False, index=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('web_research_cache')

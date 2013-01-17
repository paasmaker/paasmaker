"""
Node stats and scores

Revision ID: 559851b6057b
Revises: None
Create Date: 2013-01-17 13:35:48.568345

"""

# revision identifiers, used by Alembic.
revision = '559851b6057b'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('node', sa.Column('score', sa.Float(), default=0.0))
    op.add_column('node', sa.Column('stats', sa.Text(), default="{}"))

def downgrade():
    op.drop_column('node', 'stats')
    op.drop_column('node', 'score')

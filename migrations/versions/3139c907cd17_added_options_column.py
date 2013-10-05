"""Added options column to workspace, applications, and versions.

Revision ID: 3139c907cd17
Revises: None
Create Date: 2013-10-05 07:31:03.796809

"""

# revision identifiers, used by Alembic.
revision = '3139c907cd17'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('application', sa.Column('options', sa.Text(), nullable=True))
    op.add_column('application_version', sa.Column('options', sa.Text(), nullable=True))
    op.add_column('workspace', sa.Column('options', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('workspace', 'options')
    op.drop_column('application_version', 'options')
    op.drop_column('application', 'options')

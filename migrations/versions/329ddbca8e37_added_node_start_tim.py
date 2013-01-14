"""Added node start time column

Revision ID: 329ddbca8e37
Revises: None
Create Date: 2013-01-14 08:26:02.054505

"""

# revision identifiers, used by Alembic.
revision = '329ddbca8e37'
down_revision = None

import datetime

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('node', sa.Column('start_time', sa.DateTime()))


def downgrade():
    op.drop_column('node', 'start_time')

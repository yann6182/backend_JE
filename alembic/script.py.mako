"""${message}"""
revision = '${up_revision}'
down_revision = ${down_revision | repr}
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    ${upgrades if upgrades else 'pass'}

def downgrade() -> None:
    ${downgrades if downgrades else 'pass'}
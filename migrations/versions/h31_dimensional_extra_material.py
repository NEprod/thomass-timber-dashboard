"""Add optional dimensional demand to existing room-owned Extra Material."""
from alembic import op
import sqlalchemy as sa

revision = 'h31_dimensional_extra_material'
down_revision = 'g30_work_item_photos_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_material_state', sa.Column('dimensional_extras', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('job_material_state', 'dimensional_extras')

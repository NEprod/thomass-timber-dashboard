"""Store work-item photo and quote receipt metadata outside uploaded files."""
from alembic import op
import sqlalchemy as sa


revision = 'g30_work_item_photos_receipts'
down_revision = 'f21_room_owned_material_extras'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('work_item_photo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('work_item_id', sa.Integer(), sa.ForeignKey('work_item.id'), nullable=False),
        sa.Column('stored_filename', sa.String(100), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('caption', sa.String(500), nullable=False))
    op.create_table('receipt',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('room.id')),
        sa.Column('supplier', sa.String(200), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('receipt_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('stored_filename', sa.String(100), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('receipt')
    op.drop_table('work_item_photo')

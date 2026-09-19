"""Add quote extras, payment records, procurement state and owned stock."""
from alembic import op
import sqlalchemy as sa

revision = 'c12_quote_financials_and_stock'
down_revision = 'b31dado_compatible_uses'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('consumable',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('unit_label', sa.String(length=80), nullable=False, server_default='unit'),
        sa.Column('price', sa.Float(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('quote_consumable',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('consumable_id', sa.Integer(), sa.ForeignKey('consumable.id')),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('unit_label', sa.String(length=80), nullable=False, server_default='unit'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Float(), nullable=False, server_default='0'))
    op.create_table('additional_charge',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'))
    op.create_table('payment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('paid_at', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False, server_default='Other'),
        sa.Column('note', sa.String(length=500), nullable=False, server_default=''))
    op.create_table('job_material_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('material_id', sa.String(length=100), nullable=False),
        sa.Column('extra_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('quote_id', 'material_id', name='uq_job_material_state'))
    op.create_table('job_purchase',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('material_id', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('purchased_at', sa.Date(), nullable=False))
    op.create_table('owned_stock',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('material_id', sa.String(length=100), nullable=False),
        sa.Column('usable_length_mm', sa.Float()),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('note', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('source_quote_id', sa.Integer(), sa.ForeignKey('quote.id')),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('owned_stock_allocation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owned_stock_id', sa.Integer(), sa.ForeignKey('owned_stock.id'), nullable=False),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quote.id'), nullable=False),
        sa.Column('material_id', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    op.drop_table('owned_stock_allocation')
    op.drop_table('owned_stock')
    op.drop_table('job_purchase')
    op.drop_table('job_material_state')
    op.drop_table('payment')
    op.drop_table('additional_charge')
    op.drop_table('quote_consumable')
    op.drop_table('consumable')

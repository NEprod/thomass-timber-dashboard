"""Extend owned stock with physical dimensions and reservation counters."""
from alembic import op
import sqlalchemy as sa


revision = 'd13_owned_stock_inventory'
down_revision = 'c12_quote_financials_and_stock'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('owned_stock') as batch:
        batch.add_column(sa.Column('stock_type', sa.String(length=20), nullable=False,
                                   server_default='offcut'))
        batch.add_column(sa.Column('usable_width_mm', sa.Float()))
        batch.add_column(sa.Column('reserved_quantity', sa.Integer(), nullable=False,
                                   server_default='0'))
        batch.add_column(sa.Column('consumed_quantity', sa.Integer(), nullable=False,
                                   server_default='0'))
    with op.batch_alter_table('owned_stock_allocation') as batch:
        batch.add_column(sa.Column('consumed', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
    op.execute(sa.text(
        'UPDATE owned_stock SET reserved_quantity = '
        '(SELECT COALESCE(SUM(quantity), 0) FROM owned_stock_allocation '
        'WHERE owned_stock_allocation.owned_stock_id = owned_stock.id)'
    ))


def downgrade():
    with op.batch_alter_table('owned_stock_allocation') as batch:
        batch.drop_column('consumed')
    with op.batch_alter_table('owned_stock') as batch:
        batch.drop_column('consumed_quantity')
        batch.drop_column('reserved_quantity')
        batch.drop_column('usable_width_mm')
        batch.drop_column('stock_type')

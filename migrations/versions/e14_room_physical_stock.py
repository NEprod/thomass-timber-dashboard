"""Keep room and physical dimensions on purchased and reserved job stock."""
from alembic import op
import sqlalchemy as sa
import json


revision = 'e14_room_physical_stock'
down_revision = 'd13_owned_stock_inventory'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job_purchase') as batch:
        batch.add_column(sa.Column('room_id', sa.Integer(),
                                   sa.ForeignKey('room.id', name='fk_job_purchase_room')))
        batch.add_column(sa.Column('stock_length_mm', sa.Float()))
        batch.add_column(sa.Column('stock_width_mm', sa.Float()))
    with op.batch_alter_table('owned_stock_allocation') as batch:
        batch.add_column(sa.Column('room_id', sa.Integer(),
                                   sa.ForeignKey('room.id', name='fk_owned_stock_allocation_room')))
        batch.add_column(sa.Column('stock_length_mm', sa.Float()))
        batch.add_column(sa.Column('stock_width_mm', sa.Float()))
    for table in ('job_purchase', 'owned_stock_allocation'):
        op.execute(sa.text(
            f'UPDATE {table} SET room_id = '
            '(SELECT MIN(room.id) FROM room WHERE room.quote_id = '
            f'{table}.quote_id HAVING COUNT(room.id) = 1) '
            'WHERE room_id IS NULL'
        ))
    connection = op.get_bind()
    for row in connection.execute(sa.text(
            'SELECT job_purchase.id, job_purchase.material_id, quote.snapshot '
            'FROM job_purchase JOIN quote ON quote.id = job_purchase.quote_id')).mappings():
        product = json.loads(row['snapshot']).get('catalogue', {}).get(row['material_id'])
        if product:
            connection.execute(sa.text(
                'UPDATE job_purchase SET stock_length_mm = :length, stock_width_mm = :width '
                'WHERE id = :id'), dict(id=row['id'], length=product['length_mm'],
                                       width=product['width_mm']))
    for row in connection.execute(sa.text(
            'SELECT owned_stock_allocation.id, owned_stock_allocation.material_id, '
            'quote.snapshot, owned_stock.stock_type, owned_stock.usable_length_mm, '
            'owned_stock.usable_width_mm FROM owned_stock_allocation '
            'JOIN quote ON quote.id = owned_stock_allocation.quote_id '
            'JOIN owned_stock ON owned_stock.id = owned_stock_allocation.owned_stock_id')).mappings():
        product = json.loads(row['snapshot']).get('catalogue', {}).get(row['material_id'])
        if product:
            length = (product['length_mm'] if row['stock_type'] == 'full'
                      else row['usable_length_mm'])
            width = (product['width_mm'] if row['stock_type'] == 'full'
                     else row['usable_width_mm'])
            connection.execute(sa.text(
                'UPDATE owned_stock_allocation SET stock_length_mm = :length, '
                'stock_width_mm = :width WHERE id = :id'),
                dict(id=row['id'], length=length, width=width))


def downgrade():
    with op.batch_alter_table('owned_stock_allocation') as batch:
        batch.drop_column('stock_width_mm')
        batch.drop_column('stock_length_mm')
        batch.drop_column('room_id')
    with op.batch_alter_table('job_purchase') as batch:
        batch.drop_column('stock_width_mm')
        batch.drop_column('stock_length_mm')
        batch.drop_column('room_id')

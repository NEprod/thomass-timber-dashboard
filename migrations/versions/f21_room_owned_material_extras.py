"""Add nullable room ownership to Extra Material records."""
from alembic import op
import sqlalchemy as sa


revision = 'f21_room_owned_material_extras'
down_revision = 'e14_room_physical_stock'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job_material_state') as batch:
        batch.drop_constraint('uq_job_material_state', type_='unique')
        batch.add_column(sa.Column('room_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_job_material_state_room', 'room', ['room_id'], ['id'])
        batch.create_unique_constraint('uq_job_material_state_room',
                                       ['quote_id', 'material_id', 'room_id'])
    # A single room is unambiguous; preserve multi-room legacy extras as null.
    op.execute(sa.text(
        'UPDATE job_material_state SET room_id = '
        '(SELECT MIN(room.id) FROM room WHERE room.quote_id = '
        'job_material_state.quote_id HAVING COUNT(room.id) = 1) '
        'WHERE room_id IS NULL'
    ))


def downgrade():
    with op.batch_alter_table('job_material_state') as batch:
        batch.drop_constraint('uq_job_material_state_room', type_='unique')
        batch.drop_constraint('fk_job_material_state_room', type_='foreignkey')
        batch.drop_column('room_id')
        batch.create_unique_constraint('uq_job_material_state', ['quote_id', 'material_id'])

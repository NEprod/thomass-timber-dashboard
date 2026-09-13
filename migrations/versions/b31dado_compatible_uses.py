"""Add explicit dado product compatibility without changing prices or snapshots."""
from alembic import op
import sqlalchemy as sa
import json

revision = 'b31dado_compatible_uses'
down_revision = 'a29d1b65da4b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('material') as batch:
        batch.add_column(sa.Column('uses', sa.JSON(), nullable=False, server_default='[]'))
    connection = op.get_bind()
    for row in connection.execute(sa.text('SELECT id, category, profile, length_mm FROM material')).mappings():
        uses = []
        if row['category'] == 'dado':
            if row['profile'] in ('45mm', '70mm'):
                uses = ['continuous_dado', 'stair_dado']
                if row['length_mm'] == 3000:
                    uses.append('square_dado')
            elif row['profile'] in ('astragal', 'decorative_cover') and row['length_mm'] == 2400:
                uses = ['square_dado']
        connection.execute(sa.text('UPDATE material SET uses=:uses WHERE id=:id'),
                           {'uses': json.dumps(uses), 'id': row['id']})


def downgrade():
    with op.batch_alter_table('material') as batch:
        batch.drop_column('uses')

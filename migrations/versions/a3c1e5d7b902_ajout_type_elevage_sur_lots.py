"""ajoute le type d'elevage (poulet de chair, pintade, dinde...) sur les lots

Revision ID: a3c1e5d7b902
Revises: 216a2d9f63a8
Create Date: 2026-09-20 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c1e5d7b902'
down_revision = '216a2d9f63a8'
branch_labels = None
depends_on = None


def upgrade():
    # Tous les lots existants restent des poulets de chair (server_default).
    op.add_column(
        'poultry_batches',
        sa.Column('species', sa.String(length=30), nullable=False, server_default='broiler'),
    )


def downgrade():
    op.drop_column('poultry_batches', 'species')

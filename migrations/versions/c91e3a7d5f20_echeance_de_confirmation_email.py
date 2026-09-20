"""echeance de confirmation d'email pour les inscriptions libres

Revision ID: c91e3a7d5f20
Revises: b7d2f4a9c611
Create Date: 2026-09-20 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c91e3a7d5f20'
down_revision = 'b7d2f4a9c611'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_confirm_deadline', sa.DateTime(timezone=True), nullable=True))

    # Les proprietaires existants dont l'email n'est pas confirme ne sont pas
    # bloques d'un coup : ils disposent de 3 heures a partir de la mise en
    # service de cette regle pour confirmer.
    op.execute(
        "UPDATE users SET email_confirm_deadline = now() + interval '3 hours' "
        "WHERE role = 'owner' AND email_verified_at IS NULL"
    )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_confirm_deadline')

"""plan gratuit : 1 utilisateur (le proprietaire)

Revision ID: b7d2f4a9c611
Revises: fd529ebc8880
Create Date: 2026-09-20 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d2f4a9c611'
down_revision = 'fd529ebc8880'
branch_labels = None
depends_on = None

OLD_DESCRIPTION = "Pour demarrer : 1 ferme, 1 lot actif, jusqu'a 3 utilisateurs, 2 messages/jour."
NEW_DESCRIPTION = "Pour demarrer : 1 ferme, 1 lot actif, 1 utilisateur (le proprietaire)."


def upgrade():
    # Le catalogue des plans est cree une seule fois au premier demarrage :
    # les plans deja en base doivent etre mis a jour ici. Les utilisateurs
    # deja crees ne sont pas supprimes, seule la creation de nouveaux
    # utilisateurs est limitee.
    op.execute(
        sa.text(
            "UPDATE billing_plans SET max_users = 1, description = :new WHERE code = 'decouverte'"
        ).bindparams(new=NEW_DESCRIPTION)
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE billing_plans SET max_users = 3, description = :old WHERE code = 'decouverte'"
        ).bindparams(old=OLD_DESCRIPTION)
    )

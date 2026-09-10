from flask import Blueprint

# Pas de url_prefix commun : regroupe une page publique (/tarifs) et les
# pages de gestion d'abonnement (/facturation/...).
billing_bp = Blueprint("billing", __name__, template_folder="../../templates/billing")

from app.blueprints.billing import routes  # noqa: E402,F401

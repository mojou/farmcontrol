from flask import Blueprint

poultry_bp = Blueprint(
    "poultry", __name__, url_prefix="/elevage", template_folder="../../templates/poultry"
)

# Chaque fichier ci-dessous enregistre ses routes sur poultry_bp.
from app.blueprints.poultry import farms  # noqa: E402,F401
from app.blueprints.poultry import batches  # noqa: E402,F401
from app.blueprints.poultry import daily  # noqa: E402,F401
from app.blueprints.poultry import reports  # noqa: E402,F401
from app.blueprints.poultry import stock  # noqa: E402,F401
from app.blueprints.poultry import api  # noqa: E402,F401

from flask import Blueprint

messaging_bp = Blueprint(
    "messaging", __name__, url_prefix="/messages", template_folder="../../templates/messaging"
)

from app.blueprints.messaging import routes  # noqa: E402,F401

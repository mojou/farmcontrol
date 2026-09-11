from flask import Blueprint

core_bp = Blueprint("core", __name__, template_folder="../../templates/core")

from app.blueprints.core import routes  # noqa: E402,F401

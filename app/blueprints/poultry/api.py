"""Endpoints JSON legers utilises par les graphiques Chart.js du dashboard
(paragraphe 4). Pas de dependance supplementaire cote base de donnees : les
donnees existent deja dans poultry_mortality_records et poultry_feed_records.
"""
from flask import jsonify
from flask_login import login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.batches import _get_batch_or_403
from app.utils.zootechnie import feed_series, mortality_series


@poultry_bp.route("/api/lots/<int:batch_id>/series.json")
@login_required
def batch_series_json(batch_id):
    batch = _get_batch_or_403(batch_id)
    return jsonify(
        {
            "mortality": mortality_series(batch),
            "feed": feed_series(batch),
        }
    )

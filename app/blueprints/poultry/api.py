"""Endpoints JSON legers utilises par les graphiques Chart.js du dashboard
(paragraphe 4). Pas de dependance supplementaire cote base de donnees : les
donnees existent deja dans poultry_mortality_records et poultry_feed_records.
"""
from flask import jsonify, url_for
from flask_login import current_user, login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.batches import _get_batch_or_403
from app.utils.sanitary import get_worker_reminder
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


@poultry_bp.route("/api/rappel-sanitaire.json")
@login_required
def sanitary_reminder_json():
    """Prochaine tache sanitaire en attente, pour le pop-up de rappel
    periodique affiche cote travailleur/responsable (paragraphe feuille de
    route). Renvoie {"has_reminder": false} si rien n'est en attente.
    """
    if not current_user.has_role("worker", "manager", "owner"):
        return jsonify({"has_reminder": False})

    reminder = get_worker_reminder(current_user)
    if reminder is None:
        return jsonify({"has_reminder": False})

    item = reminder["item"]
    batch = reminder["batch"]
    return jsonify(
        {
            "has_reminder": True,
            "batch_code": batch.code,
            "farm_name": batch.farm.name,
            "day_number": item.day_number,
            "program_type": item.program_type,
            "product_name": item.product_name,
            "notes": item.notes,
            "item_id": item.id,
            "mark_done_url": url_for("poultry.sanitary_program_mark_done", item_id=item.id),
            "roadmap_url": url_for("poultry.sanitary_program", batch_id=batch.id),
        }
    )

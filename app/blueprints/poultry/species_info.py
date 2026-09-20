"""Fiche de chaque type d'elevage : reperes techniques, ce qui change d'un
type a l'autre et sources (voir app/utils/species_profiles.py)."""
from flask import render_template
from flask_login import current_user, login_required

from app.blueprints.poultry import poultry_bp
from app.utils.species import SPECIES, parse_enabled
from app.utils.species_profiles import SOURCES


@poultry_bp.route("/types")
@login_required
def species_list():
    tenant = current_user.tenant
    enabled = parse_enabled(tenant.enabled_species) if tenant else []
    return render_template(
        "poultry/species_list.html",
        species_list=SPECIES,
        enabled=enabled,
        primary=tenant.primary_species if tenant else None,
        sources=SOURCES,
    )

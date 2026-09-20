"""Courbes de poids standard par type d'elevage (voir species_profiles.py).

Une courbe standard est creee dans l'exploitation la premiere fois qu'un lot
la demande ; ensuite le proprietaire peut la consulter et la modifier comme
n'importe quelle courbe ("Poids normal attendu"). Les points sont stockes en
grammes ; display_unit ne change que l'affichage et la saisie.
"""
from app.extensions import db
from app.models.poultry import GrowthReference, GrowthReferencePoint
from app.utils.species import get_species
from app.utils.species_profiles import PROFILES


def default_curve_names():
    """Noms des courbes proposees par defaut (premiere courbe de chaque type)."""
    return {p.curves[0].name for p in PROFILES.values() if p.curves}


def ensure_standard_references(tenant_id, species_code):
    """Cree (si besoin) les courbes standard du type d'elevage et les renvoie,
    la courbe par defaut en premier. Liste vide si le type n'en a pas."""
    profile = get_species(species_code).profile
    references = []
    for curve in profile.curves:
        reference = GrowthReference.query.filter_by(
            tenant_id=tenant_id, kind=GrowthReference.KIND_WEIGHT, name=curve.name
        ).first()
        if reference is None:
            reference = GrowthReference(
                tenant_id=tenant_id, name=curve.name, kind=GrowthReference.KIND_WEIGHT,
                display_unit=profile.weight_unit,
            )
            db.session.add(reference)
            db.session.flush()
            for day, grams in curve.points:
                db.session.add(
                    GrowthReferencePoint(
                        tenant_id=tenant_id, reference_id=reference.id, day_number=day, expected_weight=grams
                    )
                )
            db.session.flush()
        references.append(reference)
    return references


def to_display_unit(grams, unit):
    """Grammes -> unite d'affichage (nombre)."""
    if grams is None:
        return None
    return round(float(grams) / 1000, 2) if unit == "kg" else float(grams)


def from_display_unit(value, unit):
    """Valeur saisie dans l'unite d'affichage -> grammes."""
    return value * 1000 if unit == "kg" else value

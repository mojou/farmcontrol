"""Taux de ponte attendu des poules pondeuses, par semaine d'age.

Une courbe de ponte est un GrowthReference de type "laying" : chaque point
associe une semaine d'age (day_number) a un taux de ponte attendu en %
(expected_weight). On reutilise ainsi le meme ecran de gestion que les poids
attendus des poulets de chair.
"""
from app.extensions import db
from app.models.poultry import GrowthReference, GrowthReferencePoint

DEFAULT_LAYING_REFERENCE_NAME = "Pondeuse standard (indicatif)"

# Moyenne indicative pour une pondeuse moderne (type Lohmann / ISA Brown) :
# (semaine d'age, taux de ponte % = oeufs par jour pour 100 poules).
DEFAULT_LAYING_CURVE = [
    (18, 2), (19, 15), (20, 35), (21, 55), (22, 72), (23, 83), (24, 89), (25, 92),
    (26, 93.5), (30, 94), (32, 93), (36, 91), (40, 89), (44, 87), (48, 85), (52, 83),
    (56, 81), (60, 79), (64, 77), (68, 75), (72, 73), (76, 71), (80, 69),
]

# Ecart (en points de %) a partir duquel la ponte est jugee trop faible, et
# nombre de jours consecutifs avec des oeufs saisis avant d'alerter.
LOW_LAYING_GAP_POINTS = 10
LOW_LAYING_DAYS = 3


def ensure_default_laying_reference(tenant_id):
    """Renvoie la courbe standard du tenant, en la creant si besoin."""
    reference = GrowthReference.query.filter_by(
        tenant_id=tenant_id, kind=GrowthReference.KIND_LAYING, name=DEFAULT_LAYING_REFERENCE_NAME
    ).first()
    if reference:
        return reference
    reference = GrowthReference(
        tenant_id=tenant_id, name=DEFAULT_LAYING_REFERENCE_NAME, kind=GrowthReference.KIND_LAYING
    )
    db.session.add(reference)
    db.session.flush()
    for week, rate in DEFAULT_LAYING_CURVE:
        db.session.add(
            GrowthReferencePoint(
                tenant_id=tenant_id, reference_id=reference.id, day_number=week, expected_weight=rate
            )
        )
    db.session.flush()
    return reference


def expected_laying_rate(reference, age_weeks):
    """Taux de ponte attendu (%) a une semaine d'age donnee, interpole
    lineairement entre les points de la courbe. None si aucune courbe ou si
    la poule est plus jeune que le premier point (pas encore en ponte)."""
    if reference is None or age_weeks is None:
        return None
    points = sorted((p.day_number, float(p.expected_weight)) for p in reference.points)
    if not points or age_weeks < points[0][0]:
        return None
    if age_weeks >= points[-1][0]:
        return points[-1][1]
    for (w1, r1), (w2, r2) in zip(points, points[1:]):
        if w1 <= age_weeks <= w2:
            if w2 == w1:
                return r1
            return round(r1 + (r2 - r1) * (age_weeks - w1) / (w2 - w1), 1)
    return None

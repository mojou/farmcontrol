"""Calculs de performance zootechnique et de rentabilite (paragraphes 1 et 2).

Toutes les fonctions sont pures (pas d'acces reseau/email) pour rester
faciles a tester unitairement.
"""
from decimal import Decimal

from app.models.poultry import BatchFinance


def latest_weight_record(batch):
    """Derniere pesee enregistree pour le lot, ou None."""
    all_weights = [w for day in batch.days for w in day.weight_records]
    if not all_weights:
        return None
    return max(all_weights, key=lambda w: (w.batch_day.day_number, w.created_at))


def produced_weight_kg(batch):
    """Estime le poids vif total produit par le lot (paragraphe 1.2).

    Utilise en priorite les donnees de vente si le lot est cloture et
    renseigne, sinon la derniere pesee x effectif courant.
    """
    if batch.finance and batch.finance.sale_quantity and batch.finance.sale_unit == "kg":
        return Decimal(batch.finance.sale_quantity)

    last_weight = latest_weight_record(batch)
    if not last_weight:
        return None

    average_weight_kg = Decimal(last_weight.average_weight) / Decimal(1000)
    return average_weight_kg * Decimal(batch.current_count)


def compute_fcr(batch):
    """Indice de consommation (FCR) = aliment total consomme (kg) / poids
    total produit (kg). Retourne None si le poids produit n'est pas encore
    connu (aucune pesee saisie).
    """
    feed_kg = Decimal(batch.total_feed_kg or 0)
    weight_kg = produced_weight_kg(batch)
    if not weight_kg or weight_kg == 0:
        return None
    return round(feed_kg / weight_kg, 2)


def mortality_series(batch):
    """Serie {jour, morts_du_jour, cumul} pour la courbe de mortalite (paragraphe 4)."""
    series = []
    cumulative = 0
    for day in batch.days:
        daily = day.mortality_count
        cumulative += daily
        series.append({"day": day.day_number, "date": day.date.isoformat(), "daily": daily, "cumulative": cumulative})
    return series


def feed_series(batch):
    """Serie {jour, aliment_du_jour, cumul} pour la courbe de consommation (paragraphe 4)."""
    series = []
    cumulative = Decimal(0)
    for day in batch.days:
        daily = Decimal(day.feed_kg or 0)
        cumulative += daily
        series.append(
            {
                "day": day.day_number,
                "date": day.date.isoformat(),
                "daily": float(daily),
                "cumulative": float(cumulative),
            }
        )
    return series


def growth_curve_comparison(batch):
    """Compare le poids reel enregistre a la courbe de reference (paragraphe 1.3)."""
    reference_points = {}
    if batch.growth_reference:
        reference_points = {p.day_number: float(p.expected_weight) for p in batch.growth_reference.points}

    comparison = []
    for day in batch.days:
        for weight in day.weight_records:
            comparison.append(
                {
                    "day": day.day_number,
                    "actual_weight": float(weight.average_weight),
                    "expected_weight": reference_points.get(day.day_number),
                }
            )
    return comparison


def recompute_batch_finance(batch):
    """Recalcule et met a jour la table poultry_batch_finance pour le lot (paragraphe 2)."""
    finance = batch.finance
    if finance is None:
        finance = BatchFinance(batch_id=batch.id, tenant_id=batch.tenant_id)
        batch.finance = finance

    finance.chick_cost = Decimal(batch.initial_count) * Decimal(batch.chick_unit_price or 0)
    finance.total_feed_cost = sum((r.total_cost for day in batch.days for r in day.feed_records), Decimal(0))
    finance.total_medication_cost = sum(
        (r.total_cost for day in batch.days for r in day.medication_records), Decimal(0)
    )
    finance.total_wood_cost = sum((r.total_cost for day in batch.days for r in day.wood_records), Decimal(0))

    if batch.sales:
        # Ventes detaillees (paragraphe ventes/creances) : source de verite
        # des qu'au moins une vente est enregistree pour ce lot.
        finance.sale_revenue = sum((Decimal(s.total_amount or 0) for s in batch.sales), Decimal(0))
    elif finance.sale_quantity and finance.sale_unit_price:
        # Ancienne saisie manuelle en un seul bloc, conservee pour les lots
        # qui n'utilisent pas le suivi de ventes detaille.
        finance.sale_revenue = Decimal(finance.sale_quantity) * Decimal(finance.sale_unit_price)

    finance.net_result = Decimal(finance.sale_revenue or 0) - finance.total_charges

    weight_kg = produced_weight_kg(batch)
    if weight_kg and weight_kg > 0:
        finance.cost_per_kg = round(finance.total_charges / weight_kg, 2)
    else:
        finance.cost_per_kg = None

    return finance

"""Estimation des besoins en eau/aliment et suivi du calendrier des soins
pour le poulet de chair.

Chaque lot demarre avec un calendrier des soins vide : le proprietaire ou le
responsable y ajoute lui-meme les vaccins/traitements prevus, au jour par
jour, depuis la page du lot (aucun contenu n'est impose automatiquement).

Les estimations de consommation d'eau et d'aliment ci-dessous restent basees
sur : GIZ - NAFA (formation avicole, Cameroun), "Consommation journaliere
d'eau et d'aliment du poulet de chair moderne" (https://nafa-formation.org).
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.poultry import SanitaryProgramItem

# Consommation moyenne par semaine d'age (GIZ-Nafa, poulet de chair moderne) :
# {semaine: (poids_moyen_g, aliment_g_par_jour_par_sujet, eau_ml_par_jour_par_sujet)}
WEEKLY_CONSUMPTION_REFERENCE = {
    1: (160, 30, 50),
    2: (430, 60, 80),
    3: (840, 105, 120),
    4: (1390, 155, 160),
    5: (2010, 185, 190),
    6: (2625, 200, 240),
    7: (3175, 205, 280),
    8: (3640, 200, 320),
}
MAX_REFERENCE_WEEK = max(WEEKLY_CONSUMPTION_REFERENCE)


def _week_for_day(day_number: int) -> int:
    week = ((max(day_number, 1) - 1) // 7) + 1
    return min(week, MAX_REFERENCE_WEEK)


def estimate_daily_water_liters(batch, day_number: int) -> float:
    """Estimation du volume d'eau de boisson (litres) pour tout le lot, un jour donne."""
    _, _, ml_per_bird = WEEKLY_CONSUMPTION_REFERENCE[_week_for_day(day_number)]
    return round((ml_per_bird * (batch.current_count or 0)) / 1000, 1)


def estimate_daily_feed_kg(batch, day_number: int) -> float:
    """Estimation de la quantite d'aliment (kg) pour tout le lot, un jour donne."""
    _, g_per_bird, _ = WEEKLY_CONSUMPTION_REFERENCE[_week_for_day(day_number)]
    return round((g_per_bird * (batch.current_count or 0)) / 1000, 1)


def current_batch_day_number(batch) -> int:
    """Numero de jour du lot a la date du jour (1 = jour de mise en place)."""
    return (date.today() - batch.start_date).days + 1


def get_pending_items(batch, upto_day: int = None):
    """Elements du programme non realises dont le jour est atteint ou depasse."""
    upto_day = upto_day if upto_day is not None else current_batch_day_number(batch)
    return sorted(
        (item for item in batch.sanitary_items if not item.is_done and item.day_number <= upto_day),
        key=lambda item: item.day_number,
    )


def get_worker_reminder(user):
    """Prochaine tache sanitaire en attente pour les lots actifs accessibles
    a l'utilisateur (sa ferme s'il en a une assignee, sinon toutes celles du
    tenant). Retourne None si rien n'est en attente."""
    from app.models.poultry import BATCH_STATUS_ACTIVE, Batch, Farm

    farms_query = Farm.query
    if user.farm_id:
        farms_query = farms_query.filter_by(id=user.farm_id)
    farm_ids = [f.id for f in farms_query.all()]
    if not farm_ids:
        return None

    active_batches = Batch.query.filter(Batch.farm_id.in_(farm_ids), Batch.status == BATCH_STATUS_ACTIVE).all()

    best_item = None
    best_batch = None
    for batch in active_batches:
        pending = get_pending_items(batch)
        if pending and (best_item is None or pending[0].day_number < best_item.day_number):
            best_item = pending[0]
            best_batch = batch

    if best_item is None:
        return None
    return {"item": best_item, "batch": best_batch}

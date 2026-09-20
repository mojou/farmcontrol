"""Situe un lot par rapport aux reperes de son type d'elevage (fiche du type :
voir species_profiles.py) : age dans le cycle, mortalite, indice de
consommation, dernier poids. Chaque indicateur est "ok", "warn" ou "bad"."""
from datetime import date

from app.utils.species import cycle_days_for, get_species
from app.utils.zootechnie import compute_fcr, interpolate_curve, latest_weight_record


def batch_benchmarks(batch):
    species = get_species(batch.species)
    profile = species.profile

    end = batch.end_date or date.today()
    start_age_days = (batch.start_age_weeks or 0) * 7
    age_days = start_age_days + max((end - batch.start_date).days + 1, 1)  # age depuis la naissance
    cycle_days = get_species(batch.species).cycle_days

    mortality_percent = round(batch.total_mortality * 100 / batch.initial_count, 1) if batch.initial_count else 0
    normal = profile.mortality_normal_percent
    if mortality_percent <= normal:
        mortality_status = "ok"
    elif mortality_percent <= normal * 1.5:
        mortality_status = "warn"
    else:
        mortality_status = "bad"

    fcr = compute_fcr(batch)
    fcr_status = None
    if fcr is not None and profile.fcr_range:
        fcr_status = "ok" if float(fcr) <= profile.fcr_range[1] else "warn"

    last_weight = latest_weight_record(batch)
    weight_g = float(last_weight.average_weight) if last_weight else None
    expected_g = None
    weight_status = None
    if weight_g is not None and batch.growth_reference:
        points = [(p.day_number, float(p.expected_weight)) for p in batch.growth_reference.points]
        expected_g = interpolate_curve(points, start_age_days + last_weight.batch_day.day_number)
        if expected_g:
            gap = (weight_g - expected_g) / expected_g
            weight_status = "ok" if gap >= -0.10 else ("warn" if gap >= -0.20 else "bad")

    return {
        "species": species,
        "profile": profile,
        "age_days": age_days,
        "cycle_days": cycle_days,
        "age_percent": min(round(age_days * 100 / cycle_days), 100) if cycle_days else 0,
        "mortality_percent": mortality_percent,
        "mortality_normal": normal,
        "mortality_status": mortality_status,
        "fcr": fcr,
        "fcr_range": profile.fcr_range,
        "fcr_status": fcr_status,
        "weight_g": weight_g,
        "expected_weight_g": expected_g,
        "weight_status": weight_status,
    }

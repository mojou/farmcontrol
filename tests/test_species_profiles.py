"""Fiche de chaque type d'elevage : coherence des reperes, courbes de poids
standard, saisie des poids en kilos (porcs, dindes), page des types, alerte
de mortalite totale."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.core import Tenant
from app.models.poultry import Alert, Batch, BatchDay, GrowthReference
from app.utils.species import ALL_CODES, SPECIES, cycle_days_for, serialize_enabled
from app.utils.species_profiles import PROFILES, SOURCES
from app.utils.tenant import tenant_bypass
from app.utils.zootechnie import growth_curve_comparison, interpolate_curve
from tests.conftest import login


@pytest.fixture(autouse=True)
def _enable_all(app, tenant):
    with app.app_context():
        with tenant_bypass():
            db.session.get(Tenant, tenant.id).enabled_species = serialize_enabled(ALL_CODES)
            db.session.commit()


def _make_batch(client, farm, code, species, count="100", start_age="0", growth="0", days_ago=5):
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": code, "species": species, "breed": "",
            "initial_count": count, "chick_unit_price": "1000", "supplier_id": "0",
            "start_date": (date.today() - timedelta(days=days_ago)).isoformat(), "growth_reference_id": growth,
            "start_age_weeks": start_age, "laying_reference_id": "0",
        },
        follow_redirects=True,
    )


def _batch(app, tenant, code):
    with app.app_context():
        with tenant_bypass():
            return Batch.query.filter_by(tenant_id=tenant.id, code=code).first().id


def _close(app, batch_id):
    """Le plan gratuit n'autorise qu'un lot actif : on cloture pour en creer un autre."""
    with app.app_context():
        with tenant_bypass():
            db.session.get(Batch, batch_id).status = "closed"
            db.session.commit()


def _day(app, client, batch_id):
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            return BatchDay.query.filter_by(batch_id=batch_id).first().id


# ------------------------------------------------------------ coherence des donnees

def test_every_species_has_a_complete_profile():
    for sp in SPECIES:
        p = sp.profile
        assert sp.cycle_days > 0
        assert p.market_weight_g[0] < p.market_weight_g[1], sp.code
        assert p.mortality_normal_percent > 0
        assert p.notes
        assert p.sources_ids and all(i in SOURCES for i in p.sources_ids), sp.code
        if p.fcr_range:
            assert 0 < p.fcr_range[0] < p.fcr_range[1] < 6, sp.code
        assert p.weight_unit in ("g", "kg")
    # les gros animaux se pesent en kilos, les autres en grammes
    assert PROFILES["pig"].weight_unit == "kg" and PROFILES["turkey"].weight_unit == "kg"
    assert PROFILES["broiler"].weight_unit == "g"


def test_standard_curves_are_consistent_with_the_market_weight():
    for sp in SPECIES:
        p = sp.profile
        for curve in p.curves:
            days = [d for d, _ in curve.points]
            weights = [w for _, w in curve.points]
            assert days == sorted(days) and len(set(days)) == len(days), curve.name
            assert weights == sorted(weights), curve.name  # un animal ne maigrit pas
        if p.curves:
            first = p.curves[0]
            at_cycle_end = interpolate_curve(list(first.points), sp.cycle_days)
            low, high = p.market_weight_g
            assert low * 0.9 <= at_cycle_end <= high * 1.1, (sp.code, at_cycle_end)


def test_layer_cycle_ends_at_72_weeks_minus_arrival_age():
    assert cycle_days_for("layer", None, 0) == 72 * 7
    assert cycle_days_for("layer", None, 20) == 52 * 7
    assert cycle_days_for("rabbit") == 84 and cycle_days_for("quail") == 42
    # des porcelets achetes a 8 semaines : il reste 180 - 56 jours
    assert cycle_days_for("pig", None, 8) == 124


# ------------------------------------------------------------------ page des types

def test_species_page_lists_every_type_with_sources(client, owner):
    login(client, owner)
    for lang in ("fr", "en"):
        client.get(f"/langue/{lang}")
        resp = client.get("/elevage/types")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        for sp in SPECIES:
            assert f'id="{sp.code}"' in html
        assert "pmc.ncbi.nlm.nih.gov" in html
    assert "Fattening pig" in html and "Sources consulted" in html


# ---------------------------------------------------------- courbes et kilos

def test_pig_gets_a_standard_curve_in_kilos_and_weighs_in_kilos(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "P-1", "pig", count="30", start_age="8")
    batch_id = _batch(app, tenant, "P-1")
    with app.app_context():
        with tenant_bypass():
            ref = db.session.get(Batch, batch_id).growth_reference
            assert ref is not None and ref.display_unit == "kg"
            assert max(float(p.expected_weight) for p in ref.points) == 122000  # grammes en base

    day_id = _day(app, client, batch_id)
    html = client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)
    assert "en kilos" in html or "kilos" in html
    client.post(f"/elevage/jours/{day_id}/pesees", data={"average_weight": "85", "sample_size": "4", "observation": ""},
                follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            record = db.session.get(Batch, batch_id).days[0].weight_records[0]
            assert float(record.average_weight) == 85000  # stocke en grammes
    html = client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)
    assert "85.0 kg" in html

    with app.app_context():
        with tenant_bypass():
            data = growth_curve_comparison(db.session.get(Batch, batch_id), "kg")
    assert data[0]["actual_weight"] == 85.0
    assert data[0]["expected_weight"] is not None  # courbe interpolee au jour saisi


def test_small_animals_keep_grams(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "Q-1", "quail")
    batch_id = _batch(app, tenant, "Q-1")
    day_id = _day(app, client, batch_id)
    client.post(f"/elevage/jours/{day_id}/pesees", data={"average_weight": "150", "sample_size": "10", "observation": ""},
                follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert float(db.session.get(Batch, batch_id).days[0].weight_records[0].average_weight) == 150
    assert "150 g" in client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)


def test_growth_reference_choices_none_and_standard(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "N-1", "duck", growth="-1")
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.get(_batch(app, tenant, "N-1")).growth_reference_id is None
            assert GrowthReference.query.filter_by(tenant_id=tenant.id).count() == 0
    _close(app, _batch(app, tenant, "N-1"))
    _make_batch(client, farm, "N-2", "duck", growth="0")
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.get(_batch(app, tenant, "N-2")).growth_reference.name.startswith("Canard de Pekin")
    _close(app, _batch(app, tenant, "N-2"))
    _make_batch(client, farm, "N-3", "layer", growth="0")
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.get(_batch(app, tenant, "N-3")).growth_reference_id is None  # les pondeuses suivent la ponte


def test_custom_reference_in_kilos_is_stored_in_grams(app, client, tenant, owner):
    login(client, owner)
    client.post("/elevage/references-croissance", data={"name": "Mon porc", "kind": "weight_kg"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            ref = GrowthReference.query.filter_by(tenant_id=tenant.id, name="Mon porc").first()
            assert ref.kind == "weight" and ref.display_unit == "kg"
            ref_id = ref.id
    client.post(f"/elevage/references-croissance/{ref_id}", data={"day_number": "100", "expected_weight": "55"},
                follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert float(GrowthReference.query.get(ref_id).points[0].expected_weight) == 55000
    assert "55.0 kg" in client.get(f"/elevage/references-croissance/{ref_id}").get_data(as_text=True)


# ------------------------------------------------------------ reperes du lot

def test_batch_page_shows_the_species_benchmarks(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "R-1", "rabbit", count="60")
    batch_id = _batch(app, tenant, "R-1")
    html = client.get(f"/elevage/lots/{batch_id}").get_data(as_text=True)
    assert "Reperes pour ce type d" in html
    assert "jusqu'a 10 %" in html  # mortalite normale du lapin
    assert "2 200 g - 2 700 g" in html
    client.get("/langue/en")
    html = client.get(f"/elevage/lots/{batch_id}").get_data(as_text=True)
    assert "Benchmarks for this type of livestock" in html and "up to 10 %" in html


def test_total_mortality_alert_uses_the_species_norm(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "M-1", "broiler", count="200")
    batch_id = _batch(app, tenant, "M-1")
    day_id = _day(app, client, batch_id)

    def alerts():
        with app.app_context():
            with tenant_bypass():
                return Alert.query.filter_by(batch_id=batch_id, type="mortality_total").count()

    # 4 morts : sous le minimum de 5, pas d'alerte
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "4", "cause": ""}, follow_redirects=True)
    assert alerts() == 0
    # 8 morts sur 200 = 4 % : dans la norme du poulet de chair (4 %), pas d'alerte
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "4", "cause": ""}, follow_redirects=True)
    assert alerts() == 0
    # 12 morts = 6 % > 4 % x 1,25 : alerte, une seule par jour
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "4", "cause": ""}, follow_redirects=True)
    assert alerts() == 1
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "2", "cause": ""}, follow_redirects=True)
    assert alerts() == 1


def test_rabbit_tolerates_more_mortality_than_broiler(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "M-2", "rabbit", count="100")
    batch_id = _batch(app, tenant, "M-2")
    day_id = _day(app, client, batch_id)
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "12", "cause": ""}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            # 12 % <= 10 % x 1,25 : pas d'alerte de mortalite totale pour un lapin
            assert Alert.query.filter_by(batch_id=batch_id, type="mortality_total").count() == 0

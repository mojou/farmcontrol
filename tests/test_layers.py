"""Poules pondeuses : saisie des oeufs, taux de ponte, ventes d'oeufs."""
from datetime import date

import pytest

from app.models.poultry import Batch, BatchDay, EggRecord, Sale
from app.utils.tenant import tenant_bypass
from app.utils.zootechnie import average_laying_rate, egg_production_series
from tests.conftest import login



@pytest.fixture(autouse=True)
def _all_species_enabled(app, tenant):
    """Par defaut une exploitation ne propose que le poulet de chair (voir
    /parametres) : ces tests utilisent les autres types."""
    from app.extensions import db
    from app.models.core import Tenant
    from app.utils.species import ALL_CODES, serialize_enabled

    with app.app_context():
        with tenant_bypass():
            db.session.get(Tenant, tenant.id).enabled_species = serialize_enabled(ALL_CODES)
            db.session.commit()

def _layer_batch_with_day(app, client, tenant, farm, owner, species="layer", code="PON-01"):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": code, "species": species, "breed": "Lohmann",
            "initial_count": "200", "chick_unit_price": "1500", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch_id = Batch.query.filter_by(tenant_id=tenant.id, code=code).first().id
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            day_id = BatchDay.query.filter_by(batch_id=batch_id).first().id
    return batch_id, day_id


def test_egg_collection_is_recorded_and_deleted(app, client, tenant, owner, farm):
    batch_id, day_id = _layer_batch_with_day(app, client, tenant, farm, owner)

    html = client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)
    assert "eggsModal" in html

    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "150", "eggs_broken": "4"}, follow_redirects=True)
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "30", "eggs_broken": "0"}, follow_redirects=True)

    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.get(batch_id)
            assert batch.total_eggs == 180
            assert batch.total_eggs_broken == 4
            # 180 oeufs / 200 poules = 90 %
            assert average_laying_rate(batch) == 90.0
            record_id = EggRecord.query.filter_by(batch_id=batch_id).first().id

    client.post(f"/elevage/oeufs/{record_id}/supprimer", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.get(batch_id).total_eggs == 30


def test_broken_eggs_cannot_exceed_collected(app, client, tenant, owner, farm):
    batch_id, day_id = _layer_batch_with_day(app, client, tenant, farm, owner)
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "10", "eggs_broken": "11"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.get(batch_id).total_eggs == 0


def test_laying_rate_follows_mortality_and_sold_hens(app, client, tenant, owner, farm):
    batch_id, day_id = _layer_batch_with_day(app, client, tenant, farm, owner)
    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "50", "cause": ""}, follow_redirects=True)
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "75", "eggs_broken": "0"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            point = egg_production_series(Batch.query.get(batch_id))[0]
            assert point["hens"] == 150
            assert point["rate"] == 50.0


def test_egg_route_refused_for_non_layer_batch(app, client, tenant, owner, farm):
    _, day_id = _layer_batch_with_day(app, client, tenant, farm, owner, species="broiler", code="CHR-01")
    resp = client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "10"})
    assert resp.status_code == 404
    assert "eggsModal" not in client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)


def test_egg_sales_do_not_reduce_number_of_hens(app, client, tenant, owner, farm):
    batch_id, _ = _layer_batch_with_day(app, client, tenant, farm, owner)
    html = client.get(f"/elevage/lots/{batch_id}/ventes").get_data(as_text=True)
    assert "Plateaux de 30 oeufs" in html

    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={
            "sale_date": date.today().isoformat(), "buyer_name": "Boutique", "buyer_phone": "",
            "quantity": "20", "unit": "tray", "unit_price": "2500", "amount_paid": "50000", "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.get(batch_id)
            sale = Sale.query.filter_by(batch_id=batch_id).first()
            assert sale.unit == "tray"
            assert sale.total_amount == 50000
            assert batch.current_count == 200
            assert batch.finance.sale_revenue == 50000


def test_layer_pages_render_in_both_languages(app, client, tenant, owner, farm):
    batch_id, day_id = _layer_batch_with_day(app, client, tenant, farm, owner)
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "100", "eggs_broken": "2"}, follow_redirects=True)
    for lang in ("fr", "en"):
        client.get(f"/langue/{lang}")
        for url in (f"/elevage/lots/{batch_id}", f"/elevage/lots/{batch_id}/rapport", f"/elevage/jours/{day_id}",
                    f"/elevage/lots/{batch_id}/rapport/csv", f"/elevage/lots/{batch_id}/rapport/pdf",
                    f"/elevage/lots/{batch_id}/rentabilite", f"/elevage/lots/{batch_id}/ventes"):
            assert client.get(url).status_code == 200, (url, lang)
    html = client.get(f"/elevage/lots/{batch_id}").get_data(as_text=True)
    assert "Laying rate" in html and "Eggs collected" in html


# --------------------------------------------------------------------------
# Ponte attendue (courbe par semaine d'age) et alerte de ponte faible
# --------------------------------------------------------------------------

def test_expected_laying_rate_is_interpolated():
    from types import SimpleNamespace

    from app.utils.laying import expected_laying_rate

    ref = SimpleNamespace(points=[
        SimpleNamespace(day_number=20, expected_weight=40),
        SimpleNamespace(day_number=30, expected_weight=90),
    ])
    assert expected_laying_rate(ref, 19) is None  # pas encore en ponte
    assert expected_laying_rate(ref, 25) == 65.0
    assert expected_laying_rate(ref, 50) == 90.0  # au-dela : derniere valeur
    assert expected_laying_rate(None, 25) is None


def test_layer_batch_gets_standard_curve_and_age(app, client, tenant, owner, farm):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "AGE-01", "species": "layer", "breed": "ISA",
            "initial_count": "100", "chick_unit_price": "2500", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
            "start_age_weeks": "30", "laying_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="AGE-01").first()
            assert batch.start_age_weeks == 30
            assert batch.laying_reference.name == "Pondeuse standard (indicatif)"
            assert len(batch.laying_reference.points) > 10
            day_id = None
    client.post(f"/elevage/lots/{batch.id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            day_id = BatchDay.query.filter_by(batch_id=batch.id).first().id
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "90", "eggs_broken": "0"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            point = egg_production_series(Batch.query.get(batch.id))[0]
            assert point["age_weeks"] == 30
            assert point["expected"] == 94.0
    html = client.get(f"/elevage/lots/{batch.id}").get_data(as_text=True)
    assert "attendu : 94.0 %" in html


def test_broiler_batch_has_no_laying_settings(app, client, tenant, owner, farm):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "CHR-02", "species": "broiler", "breed": "Cobb",
            "initial_count": "100", "chick_unit_price": "300", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
            "start_age_weeks": "30", "laying_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="CHR-02").first()
            assert batch.start_age_weeks == 0
            assert batch.laying_reference_id is None


def test_low_laying_raises_an_alert_after_three_days(app, client, tenant, owner, farm):
    from datetime import timedelta

    from app.extensions import db
    from app.models.poultry import Alert

    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "ALR-01", "species": "layer", "breed": "ISA",
            "initial_count": "200", "chick_unit_price": "2500", "supplier_id": "0",
            "start_date": (date.today() - timedelta(days=2)).isoformat(), "growth_reference_id": "0",
            "start_age_weeks": "30", "laying_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch_id = Batch.query.filter_by(tenant_id=tenant.id, code="ALR-01").first().id
            day_ids = []
            for n in (1, 2, 3):
                day = BatchDay(
                    tenant_id=tenant.id, batch_id=batch_id, day_number=n,
                    date=date.today() - timedelta(days=3 - n),
                )
                db.session.add(day)
                db.session.flush()
                day_ids.append(day.id)
            db.session.commit()

    def alerts():
        with app.app_context():
            with tenant_bypass():
                return Alert.query.filter_by(batch_id=batch_id, type="laying").count()

    # 100 oeufs / 200 poules = 50 % contre 94 % attendus
    for i, day_id in enumerate(day_ids):
        client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "100", "eggs_broken": "0"}, follow_redirects=True)
        assert alerts() == (1 if i == 2 else 0)


def test_good_laying_raises_no_alert(app, client, tenant, owner, farm):
    from app.models.poultry import Alert

    batch_id, day_id = _layer_batch_with_day(app, client, tenant, farm, owner)
    client.post(f"/elevage/jours/{day_id}/oeufs", data={"eggs_collected": "10", "eggs_broken": "0"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert Alert.query.filter_by(batch_id=batch_id, type="laying").count() == 0


def test_laying_reference_management(app, client, tenant, owner):
    from app.models.poultry import GrowthReference

    login(client, owner)
    client.post("/elevage/references-croissance", data={"name": "Ma souche", "kind": "laying"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            ref = GrowthReference.query.filter_by(tenant_id=tenant.id, name="Ma souche").first()
            assert ref.kind == "laying"
            ref_id = ref.id
    client.post(f"/elevage/references-croissance/{ref_id}", data={"week": "25", "rate": "90"}, follow_redirects=True)
    # meme semaine deux fois : message clair au lieu d'une erreur 500
    resp = client.post(f"/elevage/references-croissance/{ref_id}", data={"week": "25", "rate": "91"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        with tenant_bypass():
            points = GrowthReference.query.get(ref_id).points
            assert [(p.day_number, float(p.expected_weight)) for p in points] == [(25, 90.0)]


def test_laying_pages_render_in_both_languages(app, client, tenant, owner, farm):
    batch_id, _ = _layer_batch_with_day(app, client, tenant, farm, owner)
    from app.utils.laying import ensure_default_laying_reference

    with app.app_context():
        with tenant_bypass():
            ref_id = Batch.query.get(batch_id).laying_reference_id
    for lang in ("fr", "en"):
        client.get(f"/langue/{lang}")
        for url in (f"/elevage/lots/{batch_id}/modifier", "/elevage/references-croissance",
                    f"/elevage/references-croissance/{ref_id}"):
            assert client.get(url).status_code == 200, (url, lang)
    html = client.get(f"/elevage/references-croissance/{ref_id}").get_data(as_text=True)
    assert "Week of age" in html

"""Poules pondeuses : saisie des oeufs, taux de ponte, ventes d'oeufs."""
from datetime import date

from app.models.poultry import Batch, BatchDay, EggRecord, Sale
from app.utils.tenant import tenant_bypass
from app.utils.zootechnie import average_laying_rate, egg_production_series
from tests.conftest import login


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

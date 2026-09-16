"""Calendrier des soins : demarre vide, "Administre" decompte le stock
comme la saisie quotidienne, et un element ajoute par erreur est supprimable
(les deux points corriges suite a l'audit)."""
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.poultry import Batch, BatchDay, MedicationRecord, SanitaryProgramItem, StockItem
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _setup_batch_with_day(app, client, tenant, farm, owner):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "LOT-S-01", "breed": "Cobb 500",
            "initial_count": "500", "chick_unit_price": "300", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-S-01").first()
            batch_id = batch.id
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            day_id = BatchDay.query.filter_by(batch_id=batch_id).first().id
    return batch_id, day_id


def test_sanitary_item_added_manually_and_deletable(app, client, tenant, owner, farm):
    batch_id, _ = _setup_batch_with_day(app, client, tenant, farm, owner)

    resp = client.post(
        f"/elevage/lots/{batch_id}/programme-sanitaire",
        data={"day_number": "5", "program_type": "vaccination", "product_name": "Newcastle", "notes": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        with tenant_bypass():
            item = SanitaryProgramItem.query.filter_by(batch_id=batch_id, product_name="Newcastle").first()
            assert item is not None
            item_id = item.id

    client.post(f"/elevage/programme-sanitaire/{item_id}/supprimer", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert db.session.get(SanitaryProgramItem, item_id) is None


def test_mark_done_with_quantity_decrements_stock(app, client, tenant, owner, farm):
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)

    with app.app_context():
        with tenant_bypass():
            stock = StockItem(
                tenant_id=tenant.id, farm_id=farm.id, category=StockItem.CATEGORY_MEDICATION,
                name="Vaccin Newcastle", unit="bouteille", quantity_on_hand=Decimal("2.00"),
                min_threshold=Decimal("1"), unit_price=Decimal("6000"), ml_per_unit=Decimal("1000"),
            )
            db.session.add(stock)
            item = SanitaryProgramItem(
                tenant_id=tenant.id, batch_id=batch_id, day_number=1,
                program_type="vaccination", product_name="Newcastle",
            )
            db.session.add(item)
            db.session.commit()
            stock_id, item_id = stock.id, item.id

    client.post(
        f"/elevage/programme-sanitaire/{item_id}/valider",
        data={"quantity_ml": "100", "stock_item_id": str(stock_id)},
        follow_redirects=True,
    )

    with app.app_context():
        with tenant_bypass():
            stock_after = db.session.get(StockItem, stock_id)
            assert stock_after.quantity_on_hand == Decimal("1.90")  # 2 - 0.1 bouteille
            item_after = db.session.get(SanitaryProgramItem, item_id)
            assert item_after.is_done is True
            record = MedicationRecord.query.filter_by(batch_id=batch_id).first()
            assert record is not None
            assert record.quantity == Decimal("100.00")


def test_mark_done_without_quantity_just_completes(app, client, tenant, owner, farm):
    """Un vaccin a dose unique non suivi en stock doit pouvoir se cocher
    "Administre" sans quantite ni article - ca ne doit rien casser."""
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)

    with app.app_context():
        with tenant_bypass():
            item = SanitaryProgramItem(
                tenant_id=tenant.id, batch_id=batch_id, day_number=1,
                program_type="vaccination", product_name="Dose unique",
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

    resp = client.post(f"/elevage/programme-sanitaire/{item_id}/valider", data={}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        with tenant_bypass():
            assert db.session.get(SanitaryProgramItem, item_id).is_done is True

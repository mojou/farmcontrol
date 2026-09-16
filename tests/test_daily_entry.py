"""La saisie quotidienne : conversion d'unite au decompte du stock (kg/sac,
ml/bouteille), et surtout la suppression d'une saisie erronee qui doit
annuler proprement ses effets de bord (paragraphe corrige suite a l'audit -
auparavant, aucune saisie n'etait modifiable ni supprimable)."""
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.poultry import (
    Batch,
    BatchDay,
    FeedRecord,
    MedicationRecord,
    MortalityRecord,
    StockItem,
)
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _setup_batch_with_day(app, client, tenant, farm, owner):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "LOT-J-01", "breed": "Cobb 500",
            "initial_count": "500", "chick_unit_price": "300", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-J-01").first()
            batch_id = batch.id
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            day = BatchDay.query.filter_by(batch_id=batch_id).first()
            day_id = day.id
    return batch_id, day_id


def _make_feed_stock(app, tenant, farm):
    with app.app_context():
        with tenant_bypass():
            item = StockItem(
                tenant_id=tenant.id, farm_id=farm.id, category=StockItem.CATEGORY_FEED,
                name="Aliment", unit="sac", quantity_on_hand=Decimal("20.00"),
                min_threshold=Decimal("2"), unit_price=Decimal("15000"), kg_per_unit=Decimal("50"),
            )
            db.session.add(item)
            db.session.commit()
            return item.id


def _make_medication_stock(app, tenant, farm):
    with app.app_context():
        with tenant_bypass():
            item = StockItem(
                tenant_id=tenant.id, farm_id=farm.id, category=StockItem.CATEGORY_MEDICATION,
                name="Vitamine", unit="bouteille", quantity_on_hand=Decimal("3.00"),
                min_threshold=Decimal("1"), unit_price=Decimal("4500"), ml_per_unit=Decimal("1000"),
            )
            db.session.add(item)
            db.session.commit()
            return item.id


def test_feed_entry_converts_kg_to_sacs_on_stock(app, client, tenant, owner, farm):
    """50 kg d'aliment donnes doivent decompter 1 sac (kg_per_unit=50)."""
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)
    stock_id = _make_feed_stock(app, tenant, farm)
    login(client, owner)

    client.post(
        f"/elevage/jours/{day_id}/aliment",
        data={"feed_type": "Demarrage", "quantity_kg": "50", "stock_item_id": str(stock_id)},
        follow_redirects=True,
    )

    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, stock_id)
            assert item.quantity_on_hand == Decimal("19.00")  # 20 - 1 sac


def test_deleting_feed_entry_restores_stock_and_finance(app, client, tenant, owner, farm):
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)
    stock_id = _make_feed_stock(app, tenant, farm)
    login(client, owner)

    client.post(
        f"/elevage/jours/{day_id}/aliment",
        data={"feed_type": "Demarrage", "quantity_kg": "100", "stock_item_id": str(stock_id)},
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, stock_id)
            assert item.quantity_on_hand == Decimal("18.00")  # 20 - 2 sacs
            record = FeedRecord.query.filter_by(batch_day_id=day_id).first()
            record_id = record.id
            batch = db.session.get(Batch, batch_id)
            assert batch.finance.total_feed_cost > 0

    client.post(f"/elevage/aliment/{record_id}/supprimer", follow_redirects=True)

    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, stock_id)
            assert item.quantity_on_hand == Decimal("20.00")  # restaure
            assert db.session.get(FeedRecord, record_id) is None
            batch = db.session.get(Batch, batch_id)
            assert batch.finance.total_feed_cost == Decimal("0.00")


def test_deleting_medication_entry_restores_ml_stock(app, client, tenant, owner, farm):
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)
    stock_id = _make_medication_stock(app, tenant, farm)
    login(client, owner)

    client.post(
        f"/elevage/jours/{day_id}/medicaments",
        data={"medication_name": "Vitamine C", "quantity": "200", "notes": "", "stock_item_id": str(stock_id)},
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, stock_id)
            assert item.quantity_on_hand == Decimal("2.80")  # 3 - 0.2 bouteille (200ml/1000)
            record = MedicationRecord.query.filter_by(batch_day_id=day_id).first()
            record_id = record.id

    client.post(f"/elevage/medicaments/{record_id}/supprimer", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, stock_id)
            assert item.quantity_on_hand == Decimal("3.00")


def test_deleting_mortality_entry_restores_headcount(app, client, tenant, owner, farm):
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)
    login(client, owner)

    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "15", "cause": "Test"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.current_count == 485
            record = MortalityRecord.query.filter_by(batch_day_id=day_id).first()
            record_id = record.id

    client.post(f"/elevage/mortalite/{record_id}/supprimer", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.current_count == 500


def test_worker_cannot_delete_entries(app, client, tenant, farm, owner, worker):
    """Reserve au proprietaire, comme les autres corrections de saisie."""
    batch_id, day_id = _setup_batch_with_day(app, client, tenant, farm, owner)
    login(client, worker)

    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "5", "cause": ""}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            record = MortalityRecord.query.filter_by(batch_day_id=day_id).first()
            record_id = record.id

    resp = client.post(f"/elevage/mortalite/{record_id}/supprimer", follow_redirects=True)
    assert resp.status_code == 403

    with app.app_context():
        with tenant_bypass():
            assert db.session.get(MortalityRecord, record_id) is not None

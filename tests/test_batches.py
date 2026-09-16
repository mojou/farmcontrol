"""Un lot (Batch) et sa fiche financiere - creation, cloture, et les
corrections ajoutees suite a l'audit (edition tant qu'actif seulement)."""
from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models.poultry import BATCH_STATUS_CLOSED, Batch
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _create_batch(client, farm, code="LOT-TEST-01", initial_count="1000", chick_price="300"):
    return client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id),
            "code": code,
            "breed": "Cobb 500",
            "initial_count": initial_count,
            "chick_unit_price": chick_price,
            "supplier_id": "0",
            "start_date": date.today().isoformat(),
            "growth_reference_id": "0",
        },
        follow_redirects=True,
    )


def test_batch_new_starts_with_empty_sanitary_calendar(app, client, tenant, owner, farm):
    """Suite a la demande explicite : plus de calendrier pre-rempli
    automatiquement (voir app/utils/sanitary.py)."""
    login(client, owner)
    resp = _create_batch(client, farm)
    assert resp.status_code == 200

    from app.models.poultry import SanitaryProgramItem

    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-TEST-01").first()
            assert batch is not None
            assert SanitaryProgramItem.query.filter_by(batch_id=batch.id).count() == 0
            assert batch.finance is not None
            assert batch.finance.chick_cost == Decimal("300000.00")  # 1000 x 300


def test_batch_current_count_decreases_with_mortality_and_sales(app, client, tenant, owner, farm):
    login(client, owner)
    _create_batch(client, farm)

    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-TEST-01").first()
            batch_id = batch.id
            assert batch.current_count == 1000

    # Un jour de suivi est necessaire pour saisir une mortalite.
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            day_id = batch.days[0].id

    client.post(f"/elevage/jours/{day_id}/mortalite", data={"quantity_dead": "10", "cause": "Test"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.current_count == 990

    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={
            "sale_date": date.today().isoformat(),
            "buyer_name": "Test acheteur",
            "buyer_phone": "",
            "quantity": "50",
            "unit": "unit",
            "unit_price": "3000",
            "amount_paid": "100000",
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.current_count == 940  # 990 - 50 vendus
            assert batch.finance.sale_revenue == Decimal("150000.00")  # 50 x 3000


def test_closed_batch_cannot_be_edited(app, client, tenant, owner, farm):
    login(client, owner)
    _create_batch(client, farm)

    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-TEST-01").first()
            batch.status = BATCH_STATUS_CLOSED
            db.session.commit()
            batch_id = batch.id

    resp = client.get(f"/elevage/lots/{batch_id}/modifier", follow_redirects=True)
    assert "ne peut plus etre modifie".encode() in resp.data


def test_active_batch_edit_recomputes_finance(app, client, tenant, owner, farm):
    login(client, owner)
    _create_batch(client, farm)

    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-TEST-01").first()
            batch_id = batch.id

    client.post(
        f"/elevage/lots/{batch_id}/modifier",
        data={
            "farm_id": str(farm.id),
            "code": "LOT-TEST-01",
            "breed": "Ross 308",
            "initial_count": "1200",
            "chick_unit_price": "310",
            "supplier_id": "0",
            "start_date": date.today().isoformat(),
            "growth_reference_id": "0",
        },
        follow_redirects=True,
    )

    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.breed == "Ross 308"
            assert batch.initial_count == 1200
            assert batch.finance.chick_cost == Decimal("372000.00")  # 1200 x 310

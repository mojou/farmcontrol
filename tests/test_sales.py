"""Ventes et creances : encaisse vs reste du, et le paiement d'une creance
doit bien augmenter l'argent recu (paragraphe corrige lors de la revue de
tracabilite des ventes)."""
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.poultry import Batch, Sale
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _create_batch(app, client, tenant, farm, owner):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "LOT-V-01", "breed": "Cobb 500",
            "initial_count": "300", "chick_unit_price": "300", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            return Batch.query.filter_by(tenant_id=tenant.id, code="LOT-V-01").first().id


def test_sale_with_partial_payment_tracks_balance_due(app, client, tenant, owner, farm):
    batch_id = _create_batch(app, client, tenant, farm, owner)

    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={
            "sale_date": date.today().isoformat(), "buyer_name": "Mme Test", "buyer_phone": "",
            "quantity": "40", "unit": "unit", "unit_price": "3500", "amount_paid": "50000", "notes": "",
        },
        follow_redirects=True,
    )

    with app.app_context():
        with tenant_bypass():
            sale = Sale.query.filter_by(batch_id=batch_id).first()
            assert sale.total_amount == Decimal("140000.00")  # 40 x 3500
            assert sale.amount_paid == Decimal("50000.00")
            assert sale.balance_due == Decimal("90000.00")
            assert sale.is_paid is False
            sale_id = sale.id

    client.post(f"/elevage/ventes/{sale_id}/paiement", data={"amount": "90000"}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            sale = db.session.get(Sale, sale_id)
            assert sale.balance_due == Decimal("0.00")
            assert sale.is_paid is True


def test_payment_exceeding_balance_is_rejected(app, client, tenant, owner, farm):
    batch_id = _create_batch(app, client, tenant, farm, owner)
    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={
            "sale_date": date.today().isoformat(), "buyer_name": "Mme Test", "buyer_phone": "",
            "quantity": "10", "unit": "unit", "unit_price": "3500", "amount_paid": "0", "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            sale_id = Sale.query.filter_by(batch_id=batch_id).first().id

    resp = client.post(f"/elevage/ventes/{sale_id}/paiement", data={"amount": "999999"}, follow_redirects=True)
    assert "depasse".encode() in resp.data

    with app.app_context():
        with tenant_bypass():
            sale = db.session.get(Sale, sale_id)
            assert sale.amount_paid == Decimal("0.00")


def test_sale_delete_reverses_finance(app, client, tenant, owner, farm):
    batch_id = _create_batch(app, client, tenant, farm, owner)
    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={
            "sale_date": date.today().isoformat(), "buyer_name": "Mme Test", "buyer_phone": "",
            "quantity": "20", "unit": "unit", "unit_price": "3500", "amount_paid": "70000", "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="LOT-V-01").first()
            assert batch.finance.sale_revenue == Decimal("70000.00")
            assert batch.current_count == 280
            sale_id = Sale.query.filter_by(batch_id=batch_id).first().id

    client.post(f"/elevage/ventes/{sale_id}/supprimer", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.finance.sale_revenue == Decimal("0.00")
            assert batch.current_count == 300

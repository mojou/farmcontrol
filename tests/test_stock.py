"""Le stock est le domaine le plus fragile de l'app : conversions d'unite
(kg/sac, ml/bouteille), decompte automatique, et suivi des achats comme
depenses. Chacun de ces points a deja ete source de bug reel en production."""
from decimal import Decimal

from app.extensions import db
from app.models.poultry import StockItem, StockPurchase
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _make_stock_item(app, tenant, farm, **overrides):
    with app.app_context():
        with tenant_bypass():
            defaults = dict(
                tenant_id=tenant.id,
                farm_id=farm.id,
                category=StockItem.CATEGORY_FEED,
                name="Aliment demarrage",
                unit="sac",
                quantity_on_hand=Decimal("10.00"),
                min_threshold=Decimal("2.00"),
                unit_price=Decimal("15000.00"),
                kg_per_unit=Decimal("50.00"),
            )
            defaults.update(overrides)
            item = StockItem(**defaults)
            db.session.add(item)
            db.session.commit()
            item_id = item.id
    return item_id


def test_stock_item_new_with_initial_quantity_creates_purchase(app, client, tenant, owner, farm):
    login(client, owner)
    resp = client.post(
        "/elevage/stock/nouveau",
        data={
            "farm_id": str(farm.id),
            "category": "feed",
            "name": "Aliment croissance",
            "unit": "sac",
            "quantity_on_hand": "20",
            "min_threshold": "5",
            "unit_price": "16000",
            "kg_per_unit": "50",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        with tenant_bypass():
            item = StockItem.query.filter_by(tenant_id=tenant.id, name="Aliment croissance").first()
            assert item is not None
            purchase = StockPurchase.query.filter_by(stock_item_id=item.id).first()
            assert purchase is not None
            assert purchase.total_cost == Decimal("320000.00")  # 20 x 16000


def test_restock_adds_quantity_and_logs_purchase(app, client, tenant, owner, farm):
    item_id = _make_stock_item(app, tenant, farm)
    login(client, owner)

    resp = client.post(
        f"/elevage/stock/{item_id}/reapprovisionner",
        data={"quantity_added": "5", "unit_price": "17000"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, item_id)
            assert item.quantity_on_hand == Decimal("15.00")
            assert item.unit_price == Decimal("17000.00")
            purchase = StockPurchase.query.filter_by(stock_item_id=item_id).order_by(StockPurchase.id.desc()).first()
            assert purchase.quantity == Decimal("5.00")
            assert purchase.total_cost == Decimal("85000.00")


def test_restock_by_worker_ignores_price_field(app, client, tenant, farm, worker):
    """Le prix ne doit jamais pouvoir etre modifie par un non-proprietaire,
    meme en le glissant manuellement dans la requete."""
    item_id = _make_stock_item(app, tenant, farm)
    login(client, worker)

    client.post(
        f"/elevage/stock/{item_id}/reapprovisionner",
        data={"quantity_added": "3", "unit_price": "999999"},
        follow_redirects=True,
    )

    with app.app_context():
        with tenant_bypass():
            item = db.session.get(StockItem, item_id)
            assert item.quantity_on_hand == Decimal("13.00")
            assert item.unit_price == Decimal("15000.00")  # inchange


def test_stock_item_delete_keeps_history(app, client, tenant, owner, farm):
    """Supprimer un article de stock ne doit pas casser les enregistrements
    de consommation passes qui le referencent (ondelete=SET NULL)."""
    item_id = _make_stock_item(app, tenant, farm)
    login(client, owner)

    resp = client.post(f"/elevage/stock/{item_id}/supprimer", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        with tenant_bypass():
            assert db.session.get(StockItem, item_id) is None

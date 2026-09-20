"""Type d'elevage d'un lot (poulet de chair par defaut, pintade, dinde...)."""
from datetime import date

import pytest

from app.models.poultry import Batch
from app.utils.tenant import tenant_bypass
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

def _post_batch(client, farm, code, **extra):
    data = {
        "farm_id": str(farm.id), "code": code, "breed": "Locale",
        "initial_count": "100", "chick_unit_price": "500", "supplier_id": "0",
        "start_date": date.today().isoformat(), "growth_reference_id": "0",
    }
    data.update(extra)
    return client.post("/elevage/lots/nouveau", data=data, follow_redirects=True)


def _get_batch(app, tenant, code):
    with app.app_context():
        with tenant_bypass():
            return Batch.query.filter_by(tenant_id=tenant.id, code=code).first()


def test_batch_defaults_to_broiler(app, client, tenant, owner, farm):
    login(client, owner)
    _post_batch(client, farm, "DEF-01")
    batch = _get_batch(app, tenant, "DEF-01")
    assert batch.species == "broiler"
    assert batch.is_broiler


def test_guinea_fowl_batch_is_saved_and_listed(app, client, tenant, owner, farm):
    login(client, owner)
    _post_batch(client, farm, "PIN-01", species="guinea_fowl")
    batch = _get_batch(app, tenant, "PIN-01")
    assert batch.species == "guinea_fowl"
    assert not batch.is_broiler

    html = client.get("/elevage/lots").get_data(as_text=True)
    assert "Pintade" in html
    client.get("/langue/en")
    html = client.get("/elevage/lots").get_data(as_text=True)
    assert "Guinea fowl" in html


def test_unknown_species_is_rejected(app, client, tenant, owner, farm):
    login(client, owner)
    _post_batch(client, farm, "BAD-01", species="dragon")
    assert _get_batch(app, tenant, "BAD-01") is None


def test_species_can_be_corrected_on_active_batch(app, client, tenant, owner, farm):
    login(client, owner)
    _post_batch(client, farm, "EDT-01")
    batch = _get_batch(app, tenant, "EDT-01")
    client.post(
        f"/elevage/lots/{batch.id}/modifier",
        data={
            "farm_id": str(farm.id), "code": "EDT-01", "species": "turkey", "breed": "Locale",
            "initial_count": "100", "chick_unit_price": "500", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    assert _get_batch(app, tenant, "EDT-01").species == "turkey"


def test_daily_estimates_only_for_broiler(app, client, tenant, owner, farm):
    login(client, owner)
    _post_batch(client, farm, "EST-01")
    broiler = _get_batch(app, tenant, "EST-01")
    html = client.get(f"/elevage/lots/{broiler.id}/programme-sanitaire").get_data(as_text=True)
    assert "Eau de boisson recommandee" in html

    client.post(
        f"/elevage/lots/{broiler.id}/modifier",
        data={
            "farm_id": str(farm.id), "code": "EST-01", "species": "duck", "breed": "",
            "initial_count": "100", "chick_unit_price": "500", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    html = client.get(f"/elevage/lots/{broiler.id}/programme-sanitaire").get_data(as_text=True)
    assert "Eau de boisson recommandee" not in html

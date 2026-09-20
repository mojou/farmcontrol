"""Parcours complet pour CHAQUE type d'elevage : creation du lot, saisie
quotidienne (aliment, mortalite, pesee, observation, medicament, eau/litiere
selon le type), vente, rentabilite, rapport (page, CSV, PDF), cloture, en
francais et en anglais. Verifie aussi qu'aucun mot de "poulet" ne fuit sur les
pages d'un autre type d'elevage."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.core import Tenant
from app.models.poultry import Batch, BatchDay
from app.utils.species import ALL_CODES, SPECIES_BY_CODE, serialize_enabled
from app.utils.tenant import tenant_bypass
from tests.conftest import login

# poids moyens realistes (grammes) et effectifs par type
WEIGHTS = {"broiler": 1800, "layer": 1700, "guinea_fowl": 1400, "turkey": 9, "duck": 2800, "quail": 220,
           "pig": 85, "rabbit": 2300, "fish": 450}
COUNTS = {"pig": 30, "fish": 3000, "rabbit": 60}


@pytest.fixture(autouse=True)
def _enable_all(app, tenant):
    with app.app_context():
        with tenant_bypass():
            db.session.get(Tenant, tenant.id).enabled_species = serialize_enabled(ALL_CODES)
            db.session.commit()


@pytest.mark.parametrize("species", ALL_CODES)
def test_full_flow(app, client, tenant, owner, farm, species):
    info = SPECIES_BY_CODE[species]
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "FLOW-1", "species": species, "breed": "Test",
            "initial_count": str(COUNTS.get(species, 200)), "chick_unit_price": "1500", "supplier_id": "0",
            "start_date": (date.today() - timedelta(days=5)).isoformat(), "growth_reference_id": "0",
            "start_age_weeks": "20" if species == "layer" else "0", "laying_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="FLOW-1").first()
            assert batch is not None and batch.species == species
            batch_id = batch.id
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            day_id = BatchDay.query.filter_by(batch_id=batch_id).first().id

    d = f"/elevage/jours/{day_id}"
    posts = [
        (f"{d}/aliment", {"feed_type": "Croissance", "quantity_kg": "12.5", "stock_item_id": "0"}),
        (f"{d}/mortalite", {"quantity_dead": "1", "cause": "Test"}),
        (f"{d}/pesees", {"average_weight": str(WEIGHTS[species]), "sample_size": "5", "observation": ""}),
        (f"{d}/observations", {"description": "Un animal a l'ecart", "severity": "normal"}),
        (f"{d}/medicaments", {"medication_name": "Vitamines", "quantity": "10", "notes": "", "stock_item_id": "0"}),
    ]
    if info.drinks_water:
        posts.append((f"{d}/eau", {"quantity_liters": "80"}))
    if info.uses_litter:
        posts.append((f"{d}/bois", {"quantity": "2", "stock_item_id": "0"}))
    if species == "layer":
        posts.append((f"{d}/oeufs", {"eggs_collected": "150", "eggs_broken": "2"}))
    for url, data in posts:
        resp = client.post(url, data=data, follow_redirects=True)
        assert resp.status_code == 200, url
        assert "Erreur dans le formulaire" not in resp.get_data(as_text=True), (url, data)

    with app.app_context():
        with tenant_bypass():
            batch = db.session.get(Batch, batch_id)
            assert batch.total_mortality == 1
            assert float(batch.total_feed_kg) == 12.5

    # vente (au kilo pour tous ; les pondeuses vendent aussi des oeufs)
    client.post(
        f"/elevage/lots/{batch_id}/ventes",
        data={"sale_date": date.today().isoformat(), "buyer_name": "Client", "buyer_phone": "", "quantity": "10",
              "unit": "kg", "unit_price": "1200", "amount_paid": "12000", "notes": ""},
        follow_redirects=True,
    )

    client.post(f"/elevage/lots/{batch_id}/cloturer", data={"end_date": date.today().isoformat()}, follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert db.session.get(Batch, batch_id).status == "closed"

    pages = [f"/elevage/lots/{batch_id}", f"/elevage/lots/{batch_id}/rapport", f"/elevage/lots/{batch_id}/rapport/csv",
             f"/elevage/lots/{batch_id}/rapport/pdf", f"/elevage/lots/{batch_id}/rentabilite",
             f"/elevage/lots/{batch_id}/ventes", f"/elevage/lots/{batch_id}/programme-sanitaire",
             f"/elevage/lots/{batch_id}/jours", d, "/elevage/lots", "/dashboard", "/elevage/depenses",
             f"/elevage/api/lots/{batch_id}/series.json"]
    for lang in ("fr", "en"):
        client.get(f"/langue/{lang}")
        for url in pages:
            resp = client.get(url)
            assert resp.status_code == 200, (species, lang, url)
            if species in ("pig", "rabbit", "fish") and "pdf" not in url and "csv" not in url and "json" not in url:
                text = resp.get_data(as_text=True).lower()
                for word in ("poulet", "chicken", "poussin", "chick "):
                    assert word not in text, (species, lang, url, word)

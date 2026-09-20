"""Chaque page principale doit s'afficher (HTTP 200) en francais ET en
anglais, avec de vraies donnees (lot, saisie du jour, stock, vente,
fournisseur). Attrape les erreurs de gabarit introduites par exemple en
enveloppant des textes dans _() pour la traduction."""
from datetime import date

import pytest

from app.extensions import db
from app.models.poultry import Batch, BatchDay, Sale, StockItem, Supplier
from app.utils.tenant import tenant_bypass
from tests.conftest import login


@pytest.fixture()
def data(app, client, tenant, owner, farm, manager):
    login(client, owner)
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": "SMOKE-01", "breed": "Cobb 500",
            "initial_count": "300", "chick_unit_price": "300", "supplier_id": "0",
            "start_date": date.today().isoformat(), "growth_reference_id": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        with tenant_bypass():
            batch = Batch.query.filter_by(tenant_id=tenant.id, code="SMOKE-01").first()
            day = BatchDay(tenant_id=tenant.id, batch_id=batch.id, day_number=1, date=date.today())
            db.session.add(day)
            supplier = Supplier(tenant_id=tenant.id, name="Fournisseur Test")
            db.session.add(supplier)
            item = StockItem(tenant_id=tenant.id, farm_id=farm.id, category="feed", name="Aliment test",
                             unit="sac", quantity_on_hand=5, min_threshold=1)
            db.session.add(item)
            db.session.commit()
            ids = {"batch": batch.id, "day": day.id, "supplier": supplier.id, "item": item.id}
    client.post(
        f"/elevage/lots/{ids['batch']}/ventes",
        data={
            "sale_date": date.today().isoformat(), "buyer_name": "Mme Test", "buyer_phone": "",
            "quantity": "40", "unit": "unit", "unit_price": "3500", "amount_paid": "50000", "notes": "",
        },
        follow_redirects=True,
    )
    ids["farm"] = farm.id
    return ids


def _pages(ids):
    b, d = ids["batch"], ids["day"]
    return [
        "/dashboard", "/alerts", "/journal", "/profile", "/parametres", "/users",
        "/facturation", "/messages/", "/messages/envoyes", "/messages/nouveau",
        "/elevage/fermes", f"/elevage/fermes/{ids['farm']}",
        f"/elevage/fermes/{ids['farm']}/modifier",
        "/elevage/lots", f"/elevage/lots/{b}", f"/elevage/lots/{b}/modifier",
        f"/elevage/lots/{b}/cloturer", f"/elevage/lots/{b}/jours", f"/elevage/lots/{b}/programme-sanitaire",
        f"/elevage/lots/{b}/rapport", f"/elevage/lots/{b}/rapport/csv", f"/elevage/lots/{b}/rapport/pdf",
        f"/elevage/lots/{b}/rentabilite", f"/elevage/lots/{b}/ventes", f"/elevage/jours/{d}",
        "/elevage/creances", "/elevage/depenses", "/elevage/fournisseurs", "/elevage/fournisseurs/nouveau",
        f"/elevage/fournisseurs/{ids['supplier']}/modifier", "/elevage/references-croissance",
        "/elevage/stock", "/elevage/stock/nouveau", f"/elevage/stock/{ids['item']}/modifier",
        "/auth/mon-compte/mot-de-passe",
    ]


PUBLIC = ["/", "/auth/login", "/auth/inscription", "/auth/mot-de-passe-oublie", "/tarifs", "/documentation",
          "/conditions-generales", "/politique-confidentialite", "/contact", "/hors-ligne"]


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_public_pages_render(client, lang):
    client.get(f"/langue/{lang}")
    for url in PUBLIC:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} ({lang}) -> {resp.status_code}"


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_owner_pages_render(client, owner, data, lang):
    login(client, owner)
    client.get(f"/langue/{lang}")
    for url in _pages(data):
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} ({lang}) -> {resp.status_code}"


def test_english_pages_have_no_leftover_french(client, owner, data):
    """Quelques marqueurs francais courants ne doivent plus apparaitre
    dans le corps des pages quand la langue est l'anglais."""
    login(client, owner)
    client.get("/langue/en")
    for url in ["/dashboard", "/elevage/lots", f"/elevage/lots/{data['batch']}", "/elevage/stock",
                f"/elevage/lots/{data['batch']}/ventes", "/elevage/depenses", "/elevage/fermes"]:
        html = client.get(url).get_data(as_text=True)
        for word in ("Nouveau lot", "Ouvrir", "Aucun ", "Enregistrer", "Supprimer", "Modifier", "Quantite"):
            assert word not in html, f"'{word}' encore en francais sur {url}"


def test_flash_messages_and_forms_are_translated(client, owner, data):
    """Messages flash, libelles de formulaire et boite de confirmation JS
    doivent suivre la langue choisie (pas seulement le menu)."""
    login(client, owner)
    client.get("/langue/en")
    resp = client.post(
        "/elevage/fournisseurs/nouveau",
        data={"name": "Couvoir Test", "category": "chick", "phone": "", "notes": ""},
        follow_redirects=True,
    )
    html = resp.get_data(as_text=True)
    assert "Supplier saved." in html
    assert "Fournisseur enregistre" not in html

    form_html = client.get("/elevage/fournisseurs/nouveau").get_data(as_text=True)
    assert "Supplier name" in form_html and "Mainly supplies" in form_html
    assert "Nom du fournisseur" not in form_html

    day_html = client.get(f"/elevage/jours/{data['day']}").get_data(as_text=True)
    assert "entry(ies) today" in day_html

    client.get("/langue/fr")
    fr = client.post(
        "/elevage/fournisseurs/nouveau",
        data={"name": "Couvoir Test 2", "category": "chick", "phone": "", "notes": ""},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Fournisseur enregistre." in fr

"""Parametres : langue, pays/devise et types d'elevage se conforment apres
enregistrement ; vocabulaire selon le type d'elevage (porcs, poissons...)."""
import re
from datetime import date, timedelta

from app.extensions import db
from app.models.core import Tenant
from app.models.poultry import Batch, BatchDay
from app.utils.tenant import tenant_bypass
from tests.conftest import login


def _settings_data(tenant, **over):
    data = {
        "name": tenant.name, "country": "Cameroun", "default_language": "fr", "currency_label": "FCFA",
        "primary_species": "broiler", "default_breed": "", "default_cycle_days": "",
        "fcr_alert_threshold": "", "mortality_alert_threshold_percent": "3",
        "sanitary_reminder_interval_minutes": "10", "default_stock_low_threshold": "",
        "default_labor_cost_per_day": "", "default_sale_unit": "unit", "max_login_attempts": "5",
        "login_lockout_minutes": "15",
    }
    data.update(over)
    return data


def _tenant(app, tenant):
    with app.app_context():
        with tenant_bypass():
            t = db.session.get(Tenant, tenant.id)
            return t.primary_species, t.enabled_species, t.currency_label, t.default_language


def _batch_form_species(client):
    html = client.get("/elevage/lots/nouveau").get_data(as_text=True)
    return {code for code in ("broiler", "layer", "pig", "rabbit", "fish", "duck") if f'value="{code}"' in html}


def _make_batch(client, farm, code, species):
    client.post(
        "/elevage/lots/nouveau",
        data={
            "farm_id": str(farm.id), "code": code, "species": species, "breed": "",
            "initial_count": "50", "chick_unit_price": "1000", "supplier_id": "0",
            "start_date": (date.today() - timedelta(days=3)).isoformat(), "growth_reference_id": "0",
            "start_age_weeks": "0", "laying_reference_id": "0",
        },
        follow_redirects=True,
    )


def _batch_id(app, tenant, code):
    with app.app_context():
        with tenant_bypass():
            return Batch.query.filter_by(tenant_id=tenant.id, code=code).first().id


def _new_day(app, client, batch_id):
    client.post(f"/elevage/lots/{batch_id}/jours/nouveau", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            return BatchDay.query.filter_by(batch_id=batch_id).first().id


def test_new_tenant_only_offers_broiler(app, client, tenant, owner, farm):
    login(client, owner)
    assert _batch_form_species(client) == {"broiler"}


def test_settings_choose_livestock_types(app, client, tenant, owner, farm):
    login(client, owner)
    client.post(
        "/parametres",
        data=_settings_data(tenant, primary_species="pig", livestock_types=["rabbit", "fish"]),
        follow_redirects=True,
    )
    primary, enabled, _, _ = _tenant(app, tenant)
    assert primary == "pig"
    assert enabled == "pig,rabbit,fish"  # le type principal est toujours actif
    assert _batch_form_species(client) == {"pig", "rabbit", "fish"}
    html = client.get("/elevage/lots/nouveau").get_data(as_text=True)
    assert re.search(r'<option[^>]*selected[^>]*value="pig"|<option[^>]*value="pig"[^>]*selected', html)

    html = client.get("/parametres").get_data(as_text=True)
    assert 'value="rabbit"' in html and "checked" in html


def test_disabled_species_cannot_be_used(app, client, tenant, owner, farm):
    login(client, owner)
    _make_batch(client, farm, "NOPE-1", "pig")
    with app.app_context():
        with tenant_bypass():
            assert Batch.query.filter_by(tenant_id=tenant.id, code="NOPE-1").first() is None


def test_existing_batches_keep_their_species_when_type_is_disabled(app, client, tenant, owner, farm):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, primary_species="fish"), follow_redirects=True)
    _make_batch(client, farm, "FISH-1", "fish")
    batch_id = _batch_id(app, tenant, "FISH-1")
    # on repasse au poulet de chair : le lot de poissons reste consultable et modifiable
    client.post("/parametres", data=_settings_data(tenant, primary_species="broiler"), follow_redirects=True)
    html = client.get(f"/elevage/lots/{batch_id}/modifier").get_data(as_text=True)
    assert re.search(r'<option[^>]*selected[^>]*value="fish"|<option[^>]*value="fish"[^>]*selected', html)
    assert client.get(f"/elevage/lots/{batch_id}").status_code == 200


def test_language_applies_immediately_after_saving(app, client, tenant, owner):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, default_language="en"), follow_redirects=True)
    assert _tenant(app, tenant)[3] == "en"
    assert '<html lang="en"' in client.get("/dashboard").get_data(as_text=True)
    client.post("/parametres", data=_settings_data(tenant, default_language="fr"), follow_redirects=True)
    assert '<html lang="fr"' in client.get("/dashboard").get_data(as_text=True)


def test_currency_follows_country_unless_edited(app, client, tenant, owner):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, country="Nigeria"), follow_redirects=True)
    assert _tenant(app, tenant)[2] == "NGN"
    # devise modifiee a la main en meme temps que le pays : on la respecte
    client.post(
        "/parametres", data=_settings_data(tenant, country="Ghana", currency_label="GHS-perso"), follow_redirects=True
    )
    assert _tenant(app, tenant)[2] == "GHS-perso"


def test_vocabulary_follows_the_species(app, client, tenant, owner, farm):
    login(client, owner)
    client.post(
        "/parametres",
        data=_settings_data(tenant, primary_species="pig", livestock_types=["fish"]),
        follow_redirects=True,
    )
    _make_batch(client, farm, "PORC-1", "pig")
    pig_id = _batch_id(app, tenant, "PORC-1")

    html = client.get(f"/elevage/lots/{pig_id}").get_data(as_text=True)
    assert "Nombre de porcs" in html and "Aliment par porc" in html
    # plusieurs types actifs : les pages qui melangent les lots parlent d'animaux
    assert "Nombre d&#39;animaux" in client.get("/elevage/lots").get_data(as_text=True)

    client.get("/langue/en")
    html = client.get(f"/elevage/lots/{pig_id}").get_data(as_text=True)
    assert "Number of pigs" in html and "Feed per pig" in html


def test_single_type_exploitation_uses_its_own_word(app, client, tenant, owner, farm):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, primary_species="rabbit"), follow_redirects=True)
    html = client.get("/elevage/lots").get_data(as_text=True)
    assert "Nombre de lapins" in html


def test_fish_have_no_water_or_litter_entries(app, client, tenant, owner, farm):
    login(client, owner)
    client.post(
        "/parametres",
        data=_settings_data(tenant, primary_species="fish", livestock_types=["broiler"]),
        follow_redirects=True,
    )
    _make_batch(client, farm, "POIS-1", "fish")
    day_id = _new_day(app, client, _batch_id(app, tenant, "POIS-1"))
    html = client.get(f"/elevage/jours/{day_id}").get_data(as_text=True)
    assert 'data-bs-target="#feedModal"' in html
    assert 'data-bs-target="#waterModal"' not in html
    assert 'data-bs-target="#woodModal"' not in html
    assert "Nombre de poissons restants" in html

    # un poulet de chair garde toutes les rubriques (le plan gratuit n'autorise
    # qu'un lot actif : on cloture d'abord le lot de poissons)
    with app.app_context():
        with tenant_bypass():
            Batch.query.filter_by(tenant_id=tenant.id, code="POIS-1").first().status = "closed"
            db.session.commit()
    _make_batch(client, farm, "CHAIR-1", "broiler")
    day2 = _new_day(app, client, _batch_id(app, tenant, "CHAIR-1"))
    html = client.get(f"/elevage/jours/{day2}").get_data(as_text=True)
    assert 'data-bs-target="#waterModal"' in html and 'data-bs-target="#woodModal"' in html


def test_sales_unit_uses_the_species_word(app, client, tenant, owner, farm):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, primary_species="rabbit"), follow_redirects=True)
    _make_batch(client, farm, "LAP-1", "rabbit")
    html = client.get(f"/elevage/lots/{_batch_id(app, tenant, 'LAP-1')}/ventes").get_data(as_text=True)
    assert ">Lapins<" in html


def test_closing_a_batch_proposes_the_species_cycle(app, client, tenant, owner, farm):
    login(client, owner)
    client.post("/parametres", data=_settings_data(tenant, primary_species="pig"), follow_redirects=True)
    _make_batch(client, farm, "CYC-1", "pig")
    batch_id = _batch_id(app, tenant, "CYC-1")
    with app.app_context():
        with tenant_bypass():
            start = Batch.query.get(batch_id).start_date
    html = client.get(f"/elevage/lots/{batch_id}/cloturer").get_data(as_text=True)
    assert (start + timedelta(days=180)).isoformat() in html  # duree habituelle du porc

    # duree de cycle de l'exploitation : s'applique au type principal
    client.post(
        "/parametres", data=_settings_data(tenant, primary_species="pig", default_cycle_days="150"), follow_redirects=True
    )
    html = client.get(f"/elevage/lots/{batch_id}/cloturer").get_data(as_text=True)
    assert (start + timedelta(days=150)).isoformat() in html


def test_settings_page_renders_in_both_languages(app, client, tenant, owner):
    login(client, owner)
    for lang in ("fr", "en"):
        client.get(f"/langue/{lang}")
        assert client.get("/parametres").status_code == 200

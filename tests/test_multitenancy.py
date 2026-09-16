"""L'isolation entre clients (paragraphe securite) est la garantie la plus
fondamentale de l'app : un client ne doit jamais voir les fermes/lots/stock
d'un autre, meme par erreur applicative (oubli d'un filtre tenant_id)."""
from tests.conftest import login


def test_owner_cannot_see_another_tenant_farm(app, client, owner, farm):
    """La ferme du tenant A ne doit pas apparaitre dans la liste du tenant B."""
    from tests.conftest import _make_user

    # Second tenant totalement independant, avec sa propre ferme.
    from app.extensions import db
    from app.models.core import ROLE_OWNER, Tenant
    from app.models.poultry import Farm
    from app.utils.tenant import tenant_bypass
    import uuid

    with app.app_context():
        with tenant_bypass():
            slug = f"test-{uuid.uuid4().hex[:12]}"
            other_tenant = Tenant(name="Autre exploitation", slug=slug)
            db.session.add(other_tenant)
            db.session.commit()
            other_tenant_id = other_tenant.id
    other_owner = _make_user(app, other_tenant, ROLE_OWNER, email_prefix="other-owner")

    login(client, other_owner)
    resp = client.get("/elevage/fermes")
    assert farm.name.encode() not in resp.data

    resp2 = client.get(f"/elevage/fermes/{farm.id}")
    assert resp2.status_code == 404

    with app.app_context():
        with tenant_bypass():
            db.session.delete(db.session.get(Tenant, other_tenant_id))
            db.session.commit()


def test_worker_scoped_to_own_farm_only(app, client, tenant, owner):
    """Un travailleur assigne a une ferme ne doit pas voir les lots d'une
    autre ferme du meme tenant."""
    from app.extensions import db
    from app.models.poultry import Farm
    from app.utils.tenant import tenant_bypass
    from tests.conftest import _make_user
    from app.models.core import ROLE_WORKER

    with app.app_context():
        with tenant_bypass():
            farm_a = Farm(tenant_id=tenant.id, name="Ferme A", location="")
            farm_b = Farm(tenant_id=tenant.id, name="Ferme B", location="")
            db.session.add_all([farm_a, farm_b])
            db.session.commit()
            farm_a_id, farm_b_id = farm_a.id, farm_b.id

    worker_a = _make_user(app, tenant, ROLE_WORKER, farm_id=farm_a_id, email_prefix="worker-a")

    login(client, worker_a)
    resp = client.get(f"/elevage/fermes/{farm_b_id}")
    assert resp.status_code == 403

    resp2 = client.get(f"/elevage/fermes/{farm_a_id}")
    assert resp2.status_code == 200

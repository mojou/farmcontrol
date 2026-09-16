"""Fixtures partagees pour les tests automatises.

Utilise la meme base Postgres que le developpement local (via
TEST_DATABASE_URL, ou DATABASE_URL par defaut) plutot qu'une base separee :
chaque test cree son propre tenant isole (nom/slug uniques), et le supprime
a la fin - grace aux cascades "all, delete-orphan" deja en place sur Tenant
(voir app/models/core.py), ca nettoie automatiquement tout ce que le test a
cree en dessous (fermes, lots, saisies, stock...). ENFORCE_RLS est desactive
pour les tests : l'isolation multitenant testee ici est le filtrage
applicatif (couche 1), pas la Row Level Security Postgres (couche 2, qui
depend d'un role DB non-superuser non disponible en local).

Important : on n'ouvre PAS un app_context() unique pour toute la session de
tests. Flask-SQLAlchemy associe sa session a l'identite (id()) du contexte
d'application courant ; garder un contexte ouvert en permanence pendant que
le client de test en pousse/depile d'autres pour chaque requete produit des
incoherences difficiles a diagnostiquer (ex : un mot de passe errone qui
semble quand meme connecter l'utilisateur). Chaque fixture ouvre donc son
propre contexte, le temps de creer ses donnees, puis le referme - exactement
comme le fait le client de test pour chaque requete.
"""
import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

from app import create_app
from app.extensions import db as _db
from app.models.core import ROLE_MANAGER, ROLE_OWNER, ROLE_WORKER, Tenant, User
from app.models.poultry import Farm
from app.utils.tenant import tenant_bypass

TEST_PASSWORD = "TestPass1234!"


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        # S'applique a toutes les sessions futures de ce scoped_session,
        # quel que soit le contexte qui les cree ensuite (voir note plus
        # haut) : sans ca, les attributs d'un objet renvoye par une fixture
        # expirent au commit et deviennent illisibles une fois le contexte
        # de la fixture referme.
        _db.session.configure(expire_on_commit=False)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tenant(app):
    with app.app_context():
        with tenant_bypass():
            slug = f"test-{uuid.uuid4().hex[:12]}"
            t = Tenant(name=f"Tenant {slug}", slug=slug)
            _db.session.add(t)
            _db.session.commit()
    yield t
    with app.app_context():
        with tenant_bypass():
            obj = _db.session.get(Tenant, t.id)
            if obj is not None:
                _db.session.delete(obj)
                _db.session.commit()


def _make_user(app, tenant_obj, role, farm_id=None, email_prefix="user"):
    with app.app_context():
        with tenant_bypass():
            user = User(
                tenant_id=tenant_obj.id,
                email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
                first_name="Test",
                last_name=role.capitalize(),
                role=role,
                farm_id=farm_id,
                is_active=True,
            )
            user.set_password(TEST_PASSWORD)
            _db.session.add(user)
            _db.session.commit()
    return user


@pytest.fixture()
def owner(app, tenant):
    return _make_user(app, tenant, ROLE_OWNER, email_prefix="owner")


@pytest.fixture()
def farm(app, tenant):
    with app.app_context():
        with tenant_bypass():
            f = Farm(tenant_id=tenant.id, name="Ferme de test", location="Test")
            _db.session.add(f)
            _db.session.commit()
    return f


@pytest.fixture()
def manager(app, tenant, farm):
    return _make_user(app, tenant, ROLE_MANAGER, farm_id=farm.id, email_prefix="manager")


@pytest.fixture()
def worker(app, tenant, farm):
    return _make_user(app, tenant, ROLE_WORKER, farm_id=farm.id, email_prefix="worker")


def login(client, user):
    """Connecte `user` sur `client`. Se deconnecte d'abord si besoin : la
    route /auth/login redirige silencieusement sans rien faire si le client
    est deja authentifie (comme un utilisateur reel qui rouvrirait la page
    de connexion), ce qui rendrait un changement d'utilisateur sur le meme
    client inoperant."""
    client.get("/auth/logout")
    return client.post(
        "/auth/login",
        data={"email": user.email, "password": TEST_PASSWORD},
        follow_redirects=True,
    )

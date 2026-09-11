"""Decorateurs de controle d'acces bases sur les roles.

Roles (rappel) :
- super_admin : administre la plateforme (tous les tenants).
- owner (proprietaire) : administre son tenant (fermes, lots, finances).
- manager (responsable) : valide les rapports d'une ou plusieurs fermes.
- worker (travailleur) : saisit les donnees quotidiennes de sa ferme.
"""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.has_role(*roles):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def super_admin_required(view_func):
    return roles_required("super_admin")(view_func)


def owner_required(view_func):
    return roles_required("super_admin", "owner")(view_func)


def manager_or_above_required(view_func):
    return roles_required("super_admin", "owner", "manager")(view_func)


def any_role_required(view_func):
    return roles_required("super_admin", "owner", "manager", "worker")(view_func)


def ensure_farm_access(farm):
    """Verifie que l'utilisateur courant peut acceder a la ferme donnee.

    - super_admin : acces a tout (via tenant_bypass, gere ailleurs).
    - owner / manager sans ferme assignee : acces a toutes les fermes de leur tenant.
    - manager avec ferme assignee / worker : acces uniquement a sa ferme.
    """
    if current_user.is_super_admin() or current_user.is_owner():
        return True
    if current_user.farm_id is None:
        return True
    return current_user.farm_id == farm.id


def farm_access_required(get_farm):
    """Decorateur parametre : `get_farm` recoit les kwargs de la vue et doit
    retourner l'objet Farm concerne."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            farm = get_farm(**kwargs)
            if farm is None:
                abort(404)
            if not ensure_farm_access(farm):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator

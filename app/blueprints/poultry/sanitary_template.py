"""Modele de programme sanitaire propre a chaque tenant.

Permet a chaque proprietaire de definir sa propre facon de gerer ses lots :
ses propres produits (au lieu de - ou en plus de - la reference generique
proposee par defaut), ses propres jours, et sa propre posologie/mode
d'administration. Ce modele est ensuite copie automatiquement dans chaque
nouveau lot cree (voir app.utils.sanitary.seed_batch_program_from_template).
"""
from flask import flash, redirect, render_template, url_for
from flask_login import current_user

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import SanitaryProgramItemForm
from app.decorators import owner_required
from app.extensions import db
from app.models.poultry import SanitaryProgramTemplateItem
from app.utils.audit import log_action
from app.utils.sanitary import get_tenant_template, reset_tenant_template


@poultry_bp.route("/modele-sanitaire", methods=["GET", "POST"])
@owner_required
def sanitary_template():
    form = SanitaryProgramItemForm()

    if form.validate_on_submit():
        item = SanitaryProgramTemplateItem(
            tenant_id=current_user.tenant_id,
            day_number=form.day_number.data,
            program_type=form.program_type.data,
            product_name=form.product_name.data,
            notes=form.notes.data,
            sort_order=form.day_number.data,
        )
        db.session.add(item)
        log_action("create", "poultry_sanitary_program_template_items", None, {"product": item.product_name})
        db.session.commit()
        flash(
            f"'{item.product_name}' ajoute a votre modele. Il sera applique a tous les prochains lots.",
            "success",
        )
        return redirect(url_for("poultry.sanitary_template"))

    items = get_tenant_template(current_user.tenant_id)
    return render_template("poultry/sanitary_template.html", items=items, form=form)


@poultry_bp.route("/modele-sanitaire/<int:item_id>/supprimer", methods=["POST"])
@owner_required
def sanitary_template_delete(item_id):
    item = SanitaryProgramTemplateItem.query.get_or_404(item_id)
    db.session.delete(item)
    log_action("delete", "poultry_sanitary_program_template_items", item_id, {"product": item.product_name})
    db.session.commit()
    flash("Element retire de votre modele.", "success")
    return redirect(url_for("poultry.sanitary_template"))


@poultry_bp.route("/modele-sanitaire/reinitialiser", methods=["POST"])
@owner_required
def sanitary_template_reset():
    reset_tenant_template(current_user.tenant_id)
    log_action("update", "poultry_sanitary_program_template_items", None, {"action": "reset"})
    db.session.commit()
    flash("Modele reinitialise sur la reference generique.", "success")
    return redirect(url_for("poultry.sanitary_template"))

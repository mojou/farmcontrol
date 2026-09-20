"""Fournisseurs (poussins, aliment, medicaments) - permet de garder une
trace de qui fournit quoi, pour comparer prix/qualite/fiabilite dans le
temps plutot que de perdre cette information a chaque achat.
"""
from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import SupplierForm
from app.decorators import owner_required
from app.extensions import db
from app.models.poultry import Supplier
from app.utils.audit import log_action

CATEGORY_LABELS = {
    "chick": _l("Jeunes animaux (poussins, porcelets...)"),
    "feed": _l("Aliment"),
    "medication": _l("Medicaments"),
    "other": _l("Autre"),
}


@poultry_bp.route("/fournisseurs")
@owner_required
def suppliers_list():
    page = request.args.get("page", 1, type=int)
    pagination = Supplier.query.order_by(Supplier.name).paginate(page=page, per_page=20)
    return render_template("poultry/suppliers_list.html", pagination=pagination, category_labels=CATEGORY_LABELS)


@poultry_bp.route("/fournisseurs/nouveau", methods=["GET", "POST"])
@owner_required
def supplier_new():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            tenant_id=current_user.tenant_id,
            name=form.name.data,
            category=form.category.data,
            phone=form.phone.data,
            notes=form.notes.data,
        )
        db.session.add(supplier)
        db.session.flush()
        log_action("create", "poultry_suppliers", supplier.id, {"name": supplier.name})
        db.session.commit()
        flash(_("Fournisseur enregistre."), "success")
        return redirect(url_for("poultry.suppliers_list"))

    return render_template("poultry/supplier_form.html", form=form)


@poultry_bp.route("/fournisseurs/<int:supplier_id>/modifier", methods=["GET", "POST"])
@owner_required
def supplier_edit(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    form = SupplierForm(obj=supplier)

    if form.validate_on_submit():
        supplier.name = form.name.data
        supplier.category = form.category.data
        supplier.phone = form.phone.data
        supplier.notes = form.notes.data
        log_action("update", "poultry_suppliers", supplier.id, {"name": supplier.name})
        db.session.commit()
        flash(_("Fournisseur modifie."), "success")
        return redirect(url_for("poultry.suppliers_list"))

    return render_template("poultry/supplier_form.html", form=form, supplier=supplier)


@poultry_bp.route("/fournisseurs/<int:supplier_id>/toggle", methods=["POST"])
@owner_required
def supplier_toggle(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier.is_active = not supplier.is_active
    log_action("update", "poultry_suppliers", supplier.id, {"is_active": supplier.is_active})
    db.session.commit()
    return redirect(url_for("poultry.suppliers_list"))

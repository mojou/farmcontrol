from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import FarmForm
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import Batch, Farm
from app.utils.audit import log_action
from app.utils.plans import get_current_plan


@poultry_bp.route("/fermes")
@login_required
def farms_list():
    query = Farm.query
    if current_user.farm_id:
        query = query.filter_by(id=current_user.farm_id)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Farm.name).paginate(page=page, per_page=20)
    return render_template("poultry/farms_list.html", pagination=pagination)


@poultry_bp.route("/fermes/nouvelle", methods=["GET", "POST"])
@owner_required
def farm_new():
    plan = get_current_plan(current_user.tenant)
    if plan.max_farms is not None and Farm.query.count() >= plan.max_farms:
        flash(
            f"Votre plan {plan.name} est limite a {plan.max_farms} ferme(s). "
            "Passez a un plan superieur pour en ajouter davantage.",
            "warning",
        )
        return redirect(url_for("billing.pricing"))

    form = FarmForm()
    if form.validate_on_submit():
        farm = Farm(
            tenant_id=current_user.tenant_id,
            name=form.name.data,
            location=form.location.data,
        )
        db.session.add(farm)
        db.session.flush()
        log_action("create", "farms", farm.id, {"name": farm.name})
        db.session.commit()
        flash(f"Ferme {farm.name} creee avec succes.", "success")
        return redirect(url_for("poultry.farms_list"))
    return render_template("poultry/farm_form.html", form=form)


@poultry_bp.route("/fermes/<int:farm_id>")
@login_required
def farm_detail(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    if not ensure_farm_access(farm):
        abort(403)
    batches = Batch.query.filter_by(farm_id=farm.id).order_by(Batch.start_date.desc()).all()
    return render_template("poultry/farm_detail.html", farm=farm, batches=batches)


@poultry_bp.route("/fermes/<int:farm_id>/modifier", methods=["GET", "POST"])
@owner_required
def farm_edit(farm_id):
    """Corrige le nom ou la localisation d'une ferme existante (erreur de
    saisie), reserve au proprietaire comme les autres corrections."""
    farm = Farm.query.get_or_404(farm_id)
    form = FarmForm(obj=farm)

    if form.validate_on_submit():
        farm.name = form.name.data
        farm.location = form.location.data
        log_action("update", "farms", farm.id, {"name": farm.name})
        db.session.commit()
        flash(f"Ferme {farm.name} modifiee.", "success")
        return redirect(url_for("poultry.farm_detail", farm_id=farm.id))

    return render_template("poultry/farm_form.html", form=form, farm=farm)


@poultry_bp.route("/fermes/<int:farm_id>/toggle", methods=["POST"])
@owner_required
def farm_toggle(farm_id):
    """Active/desactive une ferme (ex : site ferme temporairement) sans
    perdre son historique de lots, contrairement a une suppression."""
    farm = Farm.query.get_or_404(farm_id)
    farm.is_active = not farm.is_active
    log_action("update", "farms", farm.id, {"is_active": farm.is_active})
    db.session.commit()
    flash(f"Ferme {farm.name} {'activee' if farm.is_active else 'desactivee'}.", "success")
    return redirect(url_for("poultry.farms_list"))

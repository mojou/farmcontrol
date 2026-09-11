from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import FarmForm
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import Batch, Farm
from app.utils.audit import log_action


@poultry_bp.route("/fermes")
@login_required
def farms_list():
    query = Farm.query
    if current_user.farm_id:
        query = query.filter_by(id=current_user.farm_id)
    farms = query.order_by(Farm.name).all()
    return render_template("poultry/farms_list.html", farms=farms)


@poultry_bp.route("/fermes/nouvelle", methods=["GET", "POST"])
@owner_required
def farm_new():
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

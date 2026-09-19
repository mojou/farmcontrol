from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.daily import _apply_stock_consumption, _stock_choices, _stock_entry_price
from app.blueprints.poultry.forms import (
    BatchCloseForm,
    BatchFinanceForm,
    BatchForm,
    GrowthReferenceForm,
    GrowthReferencePointForm,
    SanitaryProgramItemForm,
)
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import (
    BATCH_STATUS_ACTIVE,
    BATCH_STATUS_CLOSED,
    Batch,
    BatchDay,
    Farm,
    GrowthReference,
    GrowthReferencePoint,
    MedicationRecord,
    SanitaryProgramItem,
    StockPurchase,
    Supplier,
)
from app.utils.alerts import check_stock_alert
from app.utils.audit import log_action
from app.utils.plans import get_current_plan
from app.utils.sanitary import (
    current_batch_day_number,
    estimate_daily_feed_kg,
    estimate_daily_water_liters,
    get_pending_items,
)
from app.utils.zootechnie import (
    compute_fcr,
    feed_series,
    growth_curve_comparison,
    mortality_series,
    recompute_batch_finance,
)


def _accessible_farms():
    query = Farm.query
    if current_user.farm_id:
        query = query.filter_by(id=current_user.farm_id)
    return query.order_by(Farm.name).all()


def _get_batch_or_403(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if not ensure_farm_access(batch.farm):
        abort(403)
    return batch


@poultry_bp.route("/lots")
@login_required
def batches_list():
    farms = _accessible_farms()
    farm_ids = [f.id for f in farms]
    status = request.args.get("status", BATCH_STATUS_ACTIVE)
    query = Batch.query.filter(Batch.farm_id.in_(farm_ids)) if farm_ids else Batch.query.filter(False)
    if status in ("active", "closed"):
        query = query.filter_by(status=status)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Batch.start_date.desc()).paginate(page=page, per_page=20)
    return render_template("poultry/batches_list.html", pagination=pagination, status=status)


@poultry_bp.route("/lots/nouveau", methods=["GET", "POST"])
@owner_required
def batch_new():
    plan = get_current_plan(current_user.tenant)
    if plan.max_active_batches is not None:
        active_count = Batch.query.filter_by(status=BATCH_STATUS_ACTIVE).count()
        if active_count >= plan.max_active_batches:
            flash(
                _("Votre plan %(name)s est limite a %(max_active_batches)s lot(s) actif(s). Cloturez un lot existant ou passez a un plan superieur.", name=_(plan.name), max_active_batches=plan.max_active_batches),
                "warning",
            )
            return redirect(url_for("billing.pricing"))

    form = BatchForm()
    form.farm_id.choices = [(f.id, f.name) for f in Farm.query.filter_by(is_active=True).order_by(Farm.name).all()]
    form.growth_reference_id.choices = [(0, _("Aucun"))] + [
        (r.id, r.name) for r in GrowthReference.query.order_by(GrowthReference.name).all()
    ]
    form.supplier_id.choices = [(0, _("Aucun"))] + [
        (s.id, s.name) for s in Supplier.query.filter_by(is_active=True, category=Supplier.CATEGORY_CHICK).order_by(Supplier.name).all()
    ]
    if request.method == "GET" and current_user.tenant and current_user.tenant.default_breed:
        form.breed.data = current_user.tenant.default_breed

    if form.validate_on_submit():
        existing = Batch.query.filter_by(farm_id=form.farm_id.data, code=form.code.data).first()
        if existing:
            flash(_("Un lot avec ce code existe deja pour cette ferme."), "danger")
            return render_template("poultry/batch_form.html", form=form)

        batch = Batch(
            tenant_id=current_user.tenant_id,
            farm_id=form.farm_id.data,
            code=form.code.data,
            species=form.species.data,
            breed=form.breed.data,
            initial_count=form.initial_count.data,
            chick_unit_price=form.chick_unit_price.data,
            supplier_id=form.supplier_id.data or None,
            start_date=form.start_date.data,
            growth_reference_id=form.growth_reference_id.data or None,
            created_by=current_user.id,
        )
        db.session.add(batch)
        db.session.flush()
        recompute_batch_finance(batch)
        log_action("create", "poultry_batches", batch.id, {"code": batch.code})
        db.session.commit()
        flash(
            _("Lot %(code)s cree avec succes. Ajoutez vous-meme les vaccins et traitements prevus dans son calendrier des soins.", code=batch.code),
            "success",
        )
        return redirect(url_for("poultry.sanitary_program", batch_id=batch.id))

    return render_template("poultry/batch_form.html", form=form)


@poultry_bp.route("/lots/<int:batch_id>/modifier", methods=["GET", "POST"])
@owner_required
def batch_edit(batch_id):
    """Corrige les informations de base d'un lot (erreur de saisie a la
    creation : nombre de poulets, souche, prix du poussin...). Reserve aux
    lots encore actifs : un lot cloture garde son bilan final tel quel."""
    batch = _get_batch_or_403(batch_id)
    if not batch.is_active:
        flash(_("Un lot cloture ne peut plus etre modifie."), "warning")
        return redirect(url_for("poultry.batch_detail", batch_id=batch.id))

    form = BatchForm(obj=batch)
    farm_choices = [(f.id, f.name) for f in Farm.query.filter_by(is_active=True).order_by(Farm.name).all()]
    if batch.farm_id not in [f[0] for f in farm_choices]:
        farm_choices = [(batch.farm_id, batch.farm.name)] + farm_choices
    form.farm_id.choices = farm_choices
    form.growth_reference_id.choices = [(0, _("Aucun"))] + [
        (r.id, r.name) for r in GrowthReference.query.order_by(GrowthReference.name).all()
    ]
    form.supplier_id.choices = [(0, _("Aucun"))] + [
        (s.id, s.name) for s in Supplier.query.filter_by(is_active=True, category=Supplier.CATEGORY_CHICK).order_by(Supplier.name).all()
    ]
    if request.method == "GET":
        form.supplier_id.data = batch.supplier_id or 0
        form.growth_reference_id.data = batch.growth_reference_id or 0

    if form.validate_on_submit():
        existing = (
            Batch.query.filter_by(farm_id=form.farm_id.data, code=form.code.data)
            .filter(Batch.id != batch.id)
            .first()
        )
        if existing:
            flash(_("Un lot avec ce code existe deja pour cette ferme."), "danger")
            return render_template("poultry/batch_form.html", form=form, batch=batch)

        batch.farm_id = form.farm_id.data
        batch.code = form.code.data
        batch.species = form.species.data
        batch.breed = form.breed.data
        batch.initial_count = form.initial_count.data
        batch.chick_unit_price = form.chick_unit_price.data
        batch.supplier_id = form.supplier_id.data or None
        batch.start_date = form.start_date.data
        batch.growth_reference_id = form.growth_reference_id.data or None
        recompute_batch_finance(batch)
        log_action("update", "poultry_batches", batch.id, {"code": batch.code})
        db.session.commit()
        flash(_("Lot %(code)s modifie.", code=batch.code), "success")
        return redirect(url_for("poultry.batch_detail", batch_id=batch.id))

    return render_template("poultry/batch_form.html", form=form, batch=batch)


@poultry_bp.route("/lots/<int:batch_id>")
@login_required
def batch_detail(batch_id):
    batch = _get_batch_or_403(batch_id)
    fcr = compute_fcr(batch)
    return render_template("poultry/batch_detail.html", batch=batch, fcr=fcr)


@poultry_bp.route("/lots/<int:batch_id>/cloturer", methods=["GET", "POST"])
@owner_required
def batch_close(batch_id):
    batch = _get_batch_or_403(batch_id)
    form = BatchCloseForm()
    if request.method == "GET" and current_user.tenant and current_user.tenant.default_cycle_days:
        from datetime import timedelta

        form.end_date.data = batch.start_date + timedelta(days=current_user.tenant.default_cycle_days)
    if form.validate_on_submit():
        batch.status = BATCH_STATUS_CLOSED
        batch.end_date = form.end_date.data
        recompute_batch_finance(batch)
        log_action("update", "poultry_batches", batch.id, {"status": "closed"})
        db.session.commit()
        flash(_("Lot %(code)s cloture.", code=batch.code), "success")
        return redirect(url_for("poultry.batch_report", batch_id=batch.id))
    return render_template("poultry/batch_close.html", batch=batch, form=form)


@poultry_bp.route("/lots/<int:batch_id>/rentabilite", methods=["GET", "POST"])
@owner_required
def batch_finance(batch_id):
    batch = _get_batch_or_403(batch_id)
    finance = batch.finance
    form = BatchFinanceForm(obj=finance)
    # Pre-remplit avec les valeurs par defaut du tenant (/parametres) tant
    # que ce formulaire n'a jamais ete rempli pour ce lot (sale_quantity
    # encore vide) - evite d'ecraser une valeur deja enregistree volontairement.
    if request.method == "GET" and finance is not None and finance.sale_quantity is None and current_user.tenant:
        if current_user.tenant.default_labor_cost_per_day is not None:
            form.labor_cost.data = current_user.tenant.default_labor_cost_per_day
        if current_user.tenant.default_sale_unit:
            form.sale_unit.data = current_user.tenant.default_sale_unit

    if form.validate_on_submit():
        if finance is None:
            recompute_batch_finance(batch)
            finance = batch.finance
        finance.labor_cost = form.labor_cost.data or 0
        finance.sale_quantity = form.sale_quantity.data
        finance.sale_unit = form.sale_unit.data
        finance.sale_unit_price = form.sale_unit_price.data
        recompute_batch_finance(batch)
        log_action("update", "poultry_batch_finance", finance.id, {"sale_quantity": finance.sale_quantity})
        db.session.commit()
        flash(_("Informations sur ce que vous gagnez mises a jour."), "success")
        return redirect(url_for("poultry.batch_report", batch_id=batch.id))

    stock_purchases_total, _unused = _stock_purchases_during(batch)
    return render_template(
        "poultry/batch_finance_form.html", batch=batch, form=form, stock_purchases_total=stock_purchases_total
    )


def _stock_purchases_during(batch):
    """Achats de stock de la ferme du lot, sur sa periode (mise en place ->
    cloture ou aujourd'hui). Purement informatif sur le rapport : contrairement
    au cout aliment/medicaments/bois du lot (ce qui a ete consomme par CE
    lot), ce total couvre tout ce qui a ete achete pour la ferme pendant la
    periode, y compris ce qui a servi a d'autres lots actifs en meme temps -
    les deux chiffres repondent a des questions differentes et ne doivent
    jamais etre additionnes."""
    end = batch.end_date or date.today()
    purchases = (
        StockPurchase.query.filter(
            StockPurchase.farm_id == batch.farm_id,
            StockPurchase.purchase_date >= batch.start_date,
            StockPurchase.purchase_date <= end,
        )
        .all()
    )
    total = sum((p.total_cost or 0) for p in purchases)
    return total, purchases


@poultry_bp.route("/lots/<int:batch_id>/rapport")
@login_required
def batch_report(batch_id):
    batch = _get_batch_or_403(batch_id)
    fcr = compute_fcr(batch)
    # "Revenu de vente" (batch.finance.sale_revenue) est le chiffre d'affaires
    # facture (comptabilite d'engagement) : compte une vente des sa creation,
    # meme si elle est encore a credit. On calcule ici, en plus, ce qui est
    # reellement rentre en caisse (encaissements) et ce qui reste du, pour
    # que le paiement d'une creance se voie concretement (paragraphe
    # tracabilite des ventes).
    cash_collected = sum((s.amount_paid or 0) for s in batch.sales)
    cash_outstanding = sum((s.balance_due or 0) for s in batch.sales)
    stock_purchases_total, _unused = _stock_purchases_during(batch)
    return render_template(
        "poultry/batch_report.html",
        batch=batch,
        fcr=fcr,
        mortality_data=mortality_series(batch),
        feed_data=feed_series(batch),
        growth_data=growth_curve_comparison(batch),
        cash_collected=cash_collected,
        cash_outstanding=cash_outstanding,
        stock_purchases_total=stock_purchases_total,
    )


# --------------------------------------------------------------------------
# Feuille de route sanitaire (vaccins, traitements, alimentation, eau)
# --------------------------------------------------------------------------

@poultry_bp.route("/lots/<int:batch_id>/programme-sanitaire", methods=["GET", "POST"])
@login_required
def sanitary_program(batch_id):
    batch = _get_batch_or_403(batch_id)
    form = SanitaryProgramItemForm()

    if current_user.has_role("owner", "manager") and form.validate_on_submit():
        item = SanitaryProgramItem(
            tenant_id=current_user.tenant_id,
            batch_id=batch.id,
            day_number=form.day_number.data,
            program_type=form.program_type.data,
            product_name=form.product_name.data,
            notes=form.notes.data,
        )
        db.session.add(item)
        db.session.commit()
        flash(_("Element du programme sanitaire ajoute."), "success")
        return redirect(url_for("poultry.sanitary_program", batch_id=batch.id))

    items = (
        SanitaryProgramItem.query.filter_by(batch_id=batch.id)
        .order_by(SanitaryProgramItem.day_number)
        .all()
    )
    today_day_number = current_batch_day_number(batch)
    pending_items = get_pending_items(batch, upto_day=today_day_number)
    return render_template(
        "poultry/sanitary_program.html",
        batch=batch,
        items=items,
        form=form,
        today_day_number=today_day_number,
        pending_items=pending_items,
        water_today=estimate_daily_water_liters(batch, today_day_number) if batch.is_broiler else None,
        feed_today=estimate_daily_feed_kg(batch, today_day_number) if batch.is_broiler else None,
        medication_stock_choices=_stock_choices(batch.farm_id, "medication"),
    )


@poultry_bp.route("/programme-sanitaire/<int:item_id>/valider", methods=["POST"])
@login_required
def sanitary_program_mark_done(item_id):
    """Marque un element de la feuille de route comme realise. Si une
    quantite et un article de stock sont fournis, cree aussi une entree
    Medicament sur le jour de suivi le plus recent du lot et decompte le
    stock - sans cela, cocher "Administre" depuis la feuille de route ne
    laissait aucune trace et ne faisait jamais bouger le stock (paragraphe
    tracabilite/gestion du stock), contrairement a la case "Medicaments"
    de la saisie quotidienne."""
    from datetime import datetime, timezone
    from decimal import Decimal, InvalidOperation

    item = SanitaryProgramItem.query.get_or_404(item_id)
    if not ensure_farm_access(item.batch.farm):
        abort(403)

    raw_quantity_ml = request.form.get("quantity_ml", type=str)
    stock_item_id = request.form.get("stock_item_id", type=int)
    try:
        quantity_ml = Decimal(raw_quantity_ml) if raw_quantity_ml else None
    except InvalidOperation:
        quantity_ml = None

    if quantity_ml and quantity_ml > 0:
        batch_day = (
            BatchDay.query.filter_by(batch_id=item.batch_id)
            .order_by(BatchDay.day_number.desc())
            .first()
        )
        if batch_day is None:
            flash(
                _("Impossible d'enregistrer la quantite : creez d'abord un jour de suivi pour ce lot "
                "(Saisie quotidienne)."),
                "danger",
            )
            return redirect(url_for("poultry.sanitary_program", batch_id=item.batch_id))

        record = MedicationRecord(
            tenant_id=current_user.tenant_id,
            batch_id=item.batch_id,
            batch_day_id=batch_day.id,
            stock_item_id=stock_item_id or None,
            medication_name=item.product_name,
            quantity=quantity_ml,
            unit_price=_stock_entry_price(stock_item_id, price_is_ml=True),
            notes=f"Administre depuis le calendrier des soins (jour {item.day_number}).",
            created_by=current_user.id,
        )
        db.session.add(record)
        stock_item = _apply_stock_consumption(stock_item_id, quantity_ml, quantity_is_ml=True)
        recompute_batch_finance(item.batch)
        db.session.flush()
        if stock_item:
            check_stock_alert(stock_item)
        log_action("create", "poultry_medication_records", None, {"medication_name": item.product_name, "via": "feuille_de_route"})

    item.is_done = True
    item.done_at = datetime.now(timezone.utc)
    item.done_by = current_user.id
    log_action("update", "poultry_sanitary_program_items", item.id, {"is_done": True})
    db.session.commit()
    flash(_("Element marque comme realise."), "success")
    return redirect(url_for("poultry.sanitary_program", batch_id=item.batch_id))


@poultry_bp.route("/programme-sanitaire/<int:item_id>/supprimer", methods=["POST"])
@login_required
def sanitary_program_item_delete(item_id):
    """Retire un element ajoute par erreur au calendrier des soins (le
    calendrier demarre vide et est rempli entierement a la main, une
    saisie en trop ou un jour errone doit pouvoir se corriger)."""
    item = SanitaryProgramItem.query.get_or_404(item_id)
    if not current_user.has_role("owner", "manager"):
        abort(403)
    if not ensure_farm_access(item.batch.farm):
        abort(403)
    batch_id = item.batch_id
    log_action("delete", "poultry_sanitary_program_items", item.id, {"product_name": item.product_name})
    db.session.delete(item)
    db.session.commit()
    flash(_("Element retire du calendrier des soins."), "success")
    return redirect(url_for("poultry.sanitary_program", batch_id=batch_id))


# --------------------------------------------------------------------------
# Courbes de reference de croissance (paragraphe 1.3)
# --------------------------------------------------------------------------

@poultry_bp.route("/references-croissance", methods=["GET", "POST"])
@owner_required
def growth_references():
    form = GrowthReferenceForm()
    if form.validate_on_submit():
        reference = GrowthReference(
            tenant_id=current_user.tenant_id, name=form.name.data, created_by=current_user.id
        )
        db.session.add(reference)
        db.session.commit()
        flash(_("Poids de reference pour %(name)s cree.", name=reference.name), "success")
        return redirect(url_for("poultry.growth_references"))

    references = GrowthReference.query.order_by(GrowthReference.name).all()
    return render_template("poultry/growth_references.html", references=references, form=form)


@poultry_bp.route("/references-croissance/<int:reference_id>", methods=["GET", "POST"])
@owner_required
def growth_reference_detail(reference_id):
    reference = GrowthReference.query.get_or_404(reference_id)
    form = GrowthReferencePointForm()
    if form.validate_on_submit():
        point = GrowthReferencePoint(
            tenant_id=current_user.tenant_id,
            reference_id=reference.id,
            day_number=form.day_number.data,
            expected_weight=form.expected_weight.data,
        )
        db.session.add(point)
        db.session.commit()
        flash(_("Point de courbe ajoute."), "success")
        return redirect(url_for("poultry.growth_reference_detail", reference_id=reference.id))

    return render_template("poultry/growth_reference_detail.html", reference=reference, form=form)

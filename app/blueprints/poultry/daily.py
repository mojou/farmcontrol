from datetime import date, datetime, timezone
from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import (
    DailyReportReviewForm,
    DailyReportSubmitForm,
    FeedRecordForm,
    MedicationRecordForm,
    MortalityRecordForm,
    ObservationForm,
    WaterRecordForm,
    WeightRecordForm,
    WoodRecordForm,
)
from app.decorators import ensure_farm_access
from app.extensions import db
from app.models.core import User
from app.models.poultry import (
    REPORT_STATUS_DRAFT,
    REPORT_STATUS_REVIEWED,
    REPORT_STATUS_SUBMITTED,
    Batch,
    BatchDay,
    DailyReport,
    FeedRecord,
    MedicationRecord,
    MortalityRecord,
    Observation,
    StockItem,
    WaterRecord,
    WeightRecord,
    WoodRecord,
)
from app.utils.alerts import check_fcr_alert, check_mortality_alert, check_stock_alert, check_urgent_observation_alert
from app.utils.audit import log_action
from app.utils.sanitary import get_pending_items
from app.utils.uploads import save_observation_photo
from app.utils.zootechnie import recompute_batch_finance


def _get_batch_or_403(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if not ensure_farm_access(batch.farm):
        abort(403)
    return batch


def _get_day_or_403(day_id):
    day = BatchDay.query.get_or_404(day_id)
    if not ensure_farm_access(day.batch.farm):
        abort(403)
    return day


def _stock_choices(farm_id, category):
    items = StockItem.query.filter_by(farm_id=farm_id, category=category, is_active=True).order_by(StockItem.name).all()
    choices = [(0, "Aucun (saisie libre)")]
    for i in items:
        label = f"{i.name} ({i.quantity_on_hand} {i.unit} en stock)"
        if i.kg_per_unit:
            label += f" - 1 {i.unit} = {i.kg_per_unit} kg"
        elif i.ml_per_unit:
            label += f" - 1 {i.unit} = {i.ml_per_unit} ml"
        choices.append((i.id, label))
    return choices


def _stock_entry_price(stock_item_id, price_is_kg=False, price_is_ml=False):
    """Prix par unite de saisie (kg/ml/unite de stock) pour un seul article,
    calcule cote serveur a partir du prix d'achat deja renseigne dans le
    Stock (StockItem.unit_price + conversion) - jamais saisi ni modifiable
    depuis la saisie quotidienne : c'est une information reservee au
    proprietaire, definie une seule fois dans /elevage/stock (paragraphe
    parametres). Sans article de stock lie ("saisie libre"), le prix est
    inconnu et reste a 0 - le cout de cette entree n'est simplement pas
    suivi, ce qui reste coherent (ex : un vaccin a dose unique)."""
    if not stock_item_id:
        return Decimal(0)
    stock_item = db.session.get(StockItem, stock_item_id)
    if stock_item is None:
        return Decimal(0)
    unit_price = Decimal(stock_item.unit_price or 0)
    if price_is_kg and stock_item.kg_per_unit:
        return round(unit_price / Decimal(stock_item.kg_per_unit), 2)
    if price_is_ml and stock_item.ml_per_unit:
        return round(unit_price / Decimal(stock_item.ml_per_unit), 2)
    return unit_price


def _farm_has_manager(farm):
    return (
        User.query.filter_by(tenant_id=farm.tenant_id, role="manager", is_active=True)
        .filter(or_(User.farm_id == farm.id, User.farm_id.is_(None)))
        .first()
        is not None
    )


def _apply_stock_consumption(stock_item_id, quantity, quantity_is_kg=False, quantity_is_ml=False):
    """Decompte une consommation du stock enregistre.

    Le bois/litiere est saisi directement dans l'unite de stock (morceau...)
    donc `quantity` s'y soustrait telle quelle. L'aliment est saisi en kg
    (necessaire pour le calcul du FCR) et les medicaments/complements
    liquides en ml (dose administree), alors que leur stock se gere
    respectivement en sacs et en litres/bouteilles : si l'article de stock
    precise une conversion (`kg_per_unit` ou `ml_per_unit`), on convertit la
    quantite donnee dans l'unite de stock avant de decompter, pour ne pas
    melanger les unites.
    """
    if not stock_item_id:
        return None
    stock_item = db.session.get(StockItem, stock_item_id)
    if stock_item is None:
        return None
    if quantity_is_kg and stock_item.kg_per_unit:
        quantity = Decimal(quantity) / Decimal(stock_item.kg_per_unit)
    elif quantity_is_ml and stock_item.ml_per_unit:
        quantity = Decimal(quantity) / Decimal(stock_item.ml_per_unit)
    stock_item.quantity_on_hand = max((stock_item.quantity_on_hand or 0) - quantity, 0)
    return stock_item


@poultry_bp.route("/lots/<int:batch_id>/jours")
@login_required
def batch_days_list(batch_id):
    batch = _get_batch_or_403(batch_id)
    page = request.args.get("page", 1, type=int)
    pagination = (
        BatchDay.query.filter_by(batch_id=batch.id)
        .order_by(BatchDay.day_number.desc())
        .paginate(page=page, per_page=20)
    )
    return render_template("poultry/batch_days_list.html", batch=batch, pagination=pagination)


@poultry_bp.route("/lots/<int:batch_id>/jours/nouveau", methods=["POST"])
@login_required
def batch_day_new(batch_id):
    batch = _get_batch_or_403(batch_id)
    last_day_number = batch.days[-1].day_number if batch.days else 0
    day = BatchDay(
        tenant_id=current_user.tenant_id,
        batch_id=batch.id,
        day_number=last_day_number + 1,
        date=date.today(),
    )
    db.session.add(day)
    db.session.flush()

    report = DailyReport(
        tenant_id=current_user.tenant_id,
        batch_id=batch.id,
        batch_day_id=day.id,
        status=REPORT_STATUS_DRAFT,
    )
    db.session.add(report)
    log_action("create", "poultry_batch_days", day.id, {"day_number": day.day_number})
    db.session.commit()
    flash(f"Jour {day.day_number} cree.", "success")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>")
@login_required
def batch_day_detail(day_id):
    day = _get_day_or_403(day_id)

    feed_form = FeedRecordForm()
    feed_form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "feed")
    wood_form = WoodRecordForm()
    wood_form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "wood")
    medication_form = MedicationRecordForm()
    medication_form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "medication")

    pending_today = get_pending_items(day.batch, upto_day=day.day_number)

    return render_template(
        "poultry/batch_day_detail.html",
        day=day,
        batch=day.batch,
        feed_form=feed_form,
        water_form=WaterRecordForm(),
        mortality_form=MortalityRecordForm(),
        wood_form=wood_form,
        medication_form=medication_form,
        observation_form=ObservationForm(),
        weight_form=WeightRecordForm(),
        submit_form=DailyReportSubmitForm(),
        review_form=DailyReportReviewForm(),
        pending_today=pending_today,
        total_feed_kg=day.feed_kg,
        total_water_liters=sum((r.quantity_liters or 0) for r in day.water_records),
        total_mortality=day.mortality_count,
    )


# --------------------------------------------------------------------------
# Suivi quotidien : aliment / eau / mortalite / bois / medicaments /
# observations (+ photo) / pesees (Phase 10)
# --------------------------------------------------------------------------

@poultry_bp.route("/jours/<int:day_id>/aliment", methods=["POST"])
@login_required
def feed_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = FeedRecordForm()
    form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "feed")

    if form.validate_on_submit():
        record = FeedRecord(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            stock_item_id=form.stock_item_id.data or None,
            feed_type=form.feed_type.data,
            quantity_kg=form.quantity_kg.data,
            unit_price=_stock_entry_price(form.stock_item_id.data, price_is_kg=True),
            created_by=current_user.id,
        )
        db.session.add(record)
        stock_item = _apply_stock_consumption(form.stock_item_id.data, form.quantity_kg.data, quantity_is_kg=True)
        recompute_batch_finance(day.batch)
        db.session.flush()
        if stock_item:
            check_stock_alert(stock_item)
        log_action("create", "poultry_feed_records", None, {"quantity_kg": str(form.quantity_kg.data)})
        db.session.commit()
        flash("Consommation d'aliment enregistree.", "success")
    else:
        flash("Erreur dans le formulaire aliment.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/eau", methods=["POST"])
@login_required
def water_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = WaterRecordForm()
    if form.validate_on_submit():
        record = WaterRecord(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            quantity_liters=form.quantity_liters.data,
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.flush()
        log_action("create", "poultry_water_records", None, {"quantity_liters": str(form.quantity_liters.data)})
        db.session.commit()
        flash("Consommation d'eau enregistree.", "success")
    else:
        flash("Erreur dans le formulaire eau.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/mortalite", methods=["POST"])
@login_required
def mortality_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = MortalityRecordForm()
    if form.validate_on_submit():
        record = MortalityRecord(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            quantity_dead=form.quantity_dead.data,
            cause=form.cause.data,
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.flush()
        check_mortality_alert(day.batch, day)
        log_action("create", "poultry_mortality_records", None, {"quantity_dead": form.quantity_dead.data})
        db.session.commit()
        flash("Mortalite enregistree.", "success")
    else:
        flash("Erreur dans le formulaire mortalite.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/bois", methods=["POST"])
@login_required
def wood_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = WoodRecordForm()
    form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "wood")

    if form.validate_on_submit():
        record = WoodRecord(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            stock_item_id=form.stock_item_id.data or None,
            quantity=form.quantity.data,
            unit_price=_stock_entry_price(form.stock_item_id.data),
            created_by=current_user.id,
        )
        db.session.add(record)
        stock_item = _apply_stock_consumption(form.stock_item_id.data, form.quantity.data)
        recompute_batch_finance(day.batch)
        db.session.flush()
        if stock_item:
            check_stock_alert(stock_item)
        log_action("create", "poultry_wood_records", None, {"quantity": str(form.quantity.data)})
        db.session.commit()
        flash("Consommation de bois/litiere enregistree.", "success")
    else:
        flash("Erreur dans le formulaire bois.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/medicaments", methods=["POST"])
@login_required
def medication_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = MedicationRecordForm()
    form.stock_item_id.choices = _stock_choices(day.batch.farm_id, "medication")

    if form.validate_on_submit():
        record = MedicationRecord(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            stock_item_id=form.stock_item_id.data or None,
            medication_name=form.medication_name.data,
            quantity=form.quantity.data,
            unit_price=_stock_entry_price(form.stock_item_id.data, price_is_ml=True),
            notes=form.notes.data,
            created_by=current_user.id,
        )
        db.session.add(record)
        stock_item = _apply_stock_consumption(form.stock_item_id.data, form.quantity.data, quantity_is_ml=True)
        recompute_batch_finance(day.batch)
        db.session.flush()
        if stock_item:
            check_stock_alert(stock_item)
        log_action("create", "poultry_medication_records", None, {"medication_name": form.medication_name.data})
        db.session.commit()
        flash("Traitement medical enregistre.", "success")
    else:
        flash("Erreur dans le formulaire medicaments.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/observations", methods=["POST"])
@login_required
def observation_new(day_id):
    day = _get_day_or_403(day_id)
    form = ObservationForm()
    if form.validate_on_submit():
        photo_path = None
        if form.photo.data:
            try:
                photo_path = save_observation_photo(form.photo.data, current_user.tenant_id)
            except ValueError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("poultry.batch_day_detail", day_id=day.id))

        record = Observation(
            tenant_id=current_user.tenant_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            description=form.description.data,
            severity=form.severity.data,
            photo_path=photo_path,
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.flush()
        check_urgent_observation_alert(record, day.batch)
        log_action("create", "poultry_observations", record.id, {"severity": record.severity})
        db.session.commit()
        flash("Observation enregistree.", "success")
    else:
        flash("Erreur dans le formulaire observation.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/pesees", methods=["POST"])
@login_required
def weight_record_new(day_id):
    day = _get_day_or_403(day_id)
    form = WeightRecordForm()
    if form.validate_on_submit():
        record = WeightRecord(
            tenant_id=current_user.tenant_id,
            farm_id=day.batch.farm_id,
            batch_id=day.batch_id,
            batch_day_id=day.id,
            average_weight=form.average_weight.data,
            sample_size=form.sample_size.data,
            observation=form.observation.data,
            created_by=current_user.id,
        )
        db.session.add(record)
        recompute_batch_finance(day.batch)
        db.session.flush()
        check_fcr_alert(day.batch)
        log_action("create", "poultry_weight_records", record.id, {"average_weight": str(form.average_weight.data)})
        db.session.commit()
        flash("Pesee enregistree.", "success")
    else:
        flash("Erreur dans le formulaire pesee.", "danger")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


# --------------------------------------------------------------------------
# Workflow de validation du rapport journalier (Phase 9 / paragraphe 9)
# --------------------------------------------------------------------------

@poultry_bp.route("/jours/<int:day_id>/rapport/soumettre", methods=["POST"])
@login_required
def daily_report_submit(day_id):
    day = _get_day_or_403(day_id)
    report = day.report
    form = DailyReportSubmitForm()
    if report.status != REPORT_STATUS_DRAFT:
        flash("Ce rapport a deja ete soumis.", "warning")
        return redirect(url_for("poultry.batch_day_detail", day_id=day.id))

    report.notes = form.notes.data
    report.submitted_by = current_user.id
    report.submitted_at = datetime.now(timezone.utc)
    report.status = REPORT_STATUS_SUBMITTED

    # Si aucun responsable n'est assigne a la ferme, le rapport passe
    # directement en "reviewed" pour ne pas bloquer le flux (paragraphe 9).
    if not _farm_has_manager(day.batch.farm):
        report.status = REPORT_STATUS_REVIEWED
        report.reviewed_at = datetime.now(timezone.utc)

    log_action("update", "poultry_daily_reports", report.id, {"status": report.status})
    db.session.commit()
    flash("Rapport journalier soumis.", "success")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))


@poultry_bp.route("/jours/<int:day_id>/rapport/valider", methods=["POST"])
@login_required
def daily_report_review(day_id):
    day = _get_day_or_403(day_id)
    if not current_user.has_role("owner", "manager", "super_admin"):
        abort(403)

    report = day.report
    form = DailyReportReviewForm()
    if report.status != REPORT_STATUS_SUBMITTED:
        flash("Ce rapport n'est pas en attente de validation.", "warning")
        return redirect(url_for("poultry.batch_day_detail", day_id=day.id))

    report.notes = form.notes.data or report.notes
    report.reviewed_by = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)
    report.status = REPORT_STATUS_REVIEWED

    log_action("update", "poultry_daily_reports", report.id, {"status": "reviewed"})
    db.session.commit()
    flash("Rapport journalier valide.", "success")
    return redirect(url_for("poultry.batch_day_detail", day_id=day.id))

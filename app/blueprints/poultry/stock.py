from datetime import date

from sqlalchemy import func

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from wtforms import DecimalField
from wtforms.validators import DataRequired, NumberRange, Optional
from flask_wtf import FlaskForm

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import StockItemForm
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import Farm, StockItem, StockPurchase
from app.utils.audit import log_action


class RestockForm(FlaskForm):
    quantity_added = DecimalField(
        "Quantite ajoutee", validators=[DataRequired(), NumberRange(min=0.01)], places=2
    )
    unit_price = DecimalField(
        "Prix paye cette fois (FCFA, facultatif)",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
    )


@poultry_bp.route("/stock")
@login_required
def stock_list():
    query = StockItem.query
    if current_user.farm_id:
        query = query.filter_by(farm_id=current_user.farm_id)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(StockItem.category, StockItem.name).paginate(page=page, per_page=20)

    purchases_month = None
    purchases_total = None
    if current_user.has_role("owner"):
        purchase_query = StockPurchase.query
        if current_user.farm_id:
            purchase_query = purchase_query.filter_by(farm_id=current_user.farm_id)
        purchases_total = purchase_query.with_entities(func.coalesce(func.sum(StockPurchase.total_cost), 0)).scalar()
        purchases_month = (
            purchase_query.filter(
                func.extract("year", StockPurchase.purchase_date) == date.today().year,
                func.extract("month", StockPurchase.purchase_date) == date.today().month,
            )
            .with_entities(func.coalesce(func.sum(StockPurchase.total_cost), 0))
            .scalar()
        )

    return render_template(
        "poultry/stock_list.html", pagination=pagination,
        purchases_month=purchases_month, purchases_total=purchases_total,
    )


@poultry_bp.route("/stock/nouveau", methods=["GET", "POST"])
@owner_required
def stock_item_new():
    form = StockItemForm()
    form.farm_id.choices = [(f.id, f.name) for f in Farm.query.filter_by(is_active=True).order_by(Farm.name).all()]
    if request.method == "GET" and current_user.tenant and current_user.tenant.default_stock_low_threshold is not None:
        form.min_threshold.data = current_user.tenant.default_stock_low_threshold

    if form.validate_on_submit():
        item = StockItem(
            tenant_id=current_user.tenant_id,
            farm_id=form.farm_id.data,
            category=form.category.data,
            name=form.name.data,
            unit=form.unit.data,
            quantity_on_hand=form.quantity_on_hand.data,
            min_threshold=form.min_threshold.data,
            unit_price=form.unit_price.data,
            kg_per_unit=form.kg_per_unit.data if form.category.data == StockItem.CATEGORY_FEED else None,
            ml_per_unit=form.ml_per_unit.data if form.category.data == StockItem.CATEGORY_MEDICATION else None,
        )
        db.session.add(item)
        db.session.flush()
        if item.quantity_on_hand and item.quantity_on_hand > 0:
            purchase = StockPurchase(
                tenant_id=current_user.tenant_id,
                farm_id=item.farm_id,
                stock_item_id=item.id,
                category=item.category,
                item_name=item.name,
                quantity=item.quantity_on_hand,
                unit_price=item.unit_price,
                total_cost=item.quantity_on_hand * (item.unit_price or 0),
                purchase_date=date.today(),
                created_by=current_user.id,
            )
            db.session.add(purchase)
            log_action("create", "poultry_stock_purchases", None, {"item_name": item.name, "total_cost": str(purchase.total_cost)})
        log_action("create", "poultry_stock_items", item.id, {"name": item.name})
        db.session.commit()
        flash(f"Article de stock {item.name} cree.", "success")
        return redirect(url_for("poultry.stock_list"))

    return render_template("poultry/stock_item_form.html", form=form)


@poultry_bp.route("/stock/<int:item_id>/reapprovisionner", methods=["POST"])
@login_required
def stock_item_restock(item_id):
    item = StockItem.query.get_or_404(item_id)
    if not ensure_farm_access(item.farm):
        abort(403)

    form = RestockForm()
    if form.validate_on_submit():
        paid_price = form.unit_price.data if (form.unit_price.data is not None and current_user.has_role("owner")) else None
        purchase_price = paid_price if paid_price is not None else (item.unit_price or 0)

        item.quantity_on_hand = (item.quantity_on_hand or 0) + form.quantity_added.data
        if paid_price is not None:
            item.unit_price = paid_price

        purchase = StockPurchase(
            tenant_id=current_user.tenant_id,
            farm_id=item.farm_id,
            stock_item_id=item.id,
            category=item.category,
            item_name=item.name,
            quantity=form.quantity_added.data,
            unit_price=purchase_price,
            total_cost=form.quantity_added.data * purchase_price,
            purchase_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(purchase)
        log_action("create", "poultry_stock_purchases", None, {"item_name": item.name, "total_cost": str(purchase.total_cost)})
        log_action("update", "poultry_stock_items", item.id, {"quantity_added": str(form.quantity_added.data)})
        db.session.commit()
        flash(f"Stock de {item.name} ajoute.", "success")
    else:
        flash("Quantite invalide.", "danger")
    return redirect(url_for("poultry.stock_list"))


@poultry_bp.route("/stock/<int:item_id>/modifier", methods=["GET", "POST"])
@owner_required
def stock_item_edit(item_id):
    """Corrige un article de stock existant (nom, unite, quantite, seuil,
    prix, conversion) en cas d'erreur de saisie. Reserve au proprietaire,
    comme la creation."""
    item = StockItem.query.get_or_404(item_id)
    if not ensure_farm_access(item.farm):
        abort(403)

    form = StockItemForm(obj=item)
    form.farm_id.choices = [(f.id, f.name) for f in Farm.query.order_by(Farm.name).all()]

    if form.validate_on_submit():
        item.farm_id = form.farm_id.data
        item.category = form.category.data
        item.name = form.name.data
        item.unit = form.unit.data
        item.quantity_on_hand = form.quantity_on_hand.data
        item.min_threshold = form.min_threshold.data
        item.unit_price = form.unit_price.data
        item.kg_per_unit = form.kg_per_unit.data if form.category.data == StockItem.CATEGORY_FEED else None
        item.ml_per_unit = form.ml_per_unit.data if form.category.data == StockItem.CATEGORY_MEDICATION else None

        log_action("update", "poultry_stock_items", item.id, {"name": item.name})
        db.session.commit()
        flash(f"Article de stock {item.name} modifie.", "success")
        return redirect(url_for("poultry.stock_list"))

    return render_template("poultry/stock_item_form.html", form=form, item=item)


@poultry_bp.route("/stock/<int:item_id>/supprimer", methods=["POST"])
@owner_required
def stock_item_delete(item_id):
    """Supprime definitivement un article de stock (erreur de saisie,
    doublon, produit qu'on n'achete plus...). Les enregistrements
    quotidiens qui y faisaient reference sont conserves (leur lien au
    stock est simplement retire, voir ondelete=SET NULL sur les modeles
    FeedRecord/WoodRecord/MedicationRecord)."""
    item = StockItem.query.get_or_404(item_id)
    if not ensure_farm_access(item.farm):
        abort(403)

    name = item.name
    log_action("delete", "poultry_stock_items", item.id, {"name": name})
    db.session.delete(item)
    db.session.commit()
    flash(f"Article de stock {name} supprime.", "success")
    return redirect(url_for("poultry.stock_list"))

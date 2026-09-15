from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from wtforms import DecimalField
from wtforms.validators import DataRequired, NumberRange
from flask_wtf import FlaskForm

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.forms import StockItemForm
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import Farm, StockItem
from app.utils.audit import log_action


class RestockForm(FlaskForm):
    quantity_added = DecimalField(
        "Quantite ajoutee", validators=[DataRequired(), NumberRange(min=0.01)], places=2
    )


@poultry_bp.route("/stock")
@login_required
def stock_list():
    query = StockItem.query
    if current_user.farm_id:
        query = query.filter_by(farm_id=current_user.farm_id)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(StockItem.category, StockItem.name).paginate(page=page, per_page=20)
    return render_template("poultry/stock_list.html", pagination=pagination)


@poultry_bp.route("/stock/nouveau", methods=["GET", "POST"])
@owner_required
def stock_item_new():
    form = StockItemForm()
    form.farm_id.choices = [(f.id, f.name) for f in Farm.query.order_by(Farm.name).all()]

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
        item.quantity_on_hand = (item.quantity_on_hand or 0) + form.quantity_added.data
        log_action("update", "poultry_stock_items", item.id, {"quantity_added": str(form.quantity_added.data)})
        db.session.commit()
        flash(f"Stock de {item.name} reapprovisionne.", "success")
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

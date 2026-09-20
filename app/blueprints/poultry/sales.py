"""Ventes multiples par lot et suivi des creances (paiement partiel/a
credit) - remplace le champ unique historique de BatchFinance pour les
eleveurs qui vendent progressivement, a plusieurs acheteurs.
"""
from flask_babel import gettext as _
from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.batches import _get_batch_or_403
from app.blueprints.poultry.forms import SaleForm, SalePaymentForm
from app.decorators import ensure_farm_access, owner_required
from app.extensions import db
from app.models.poultry import Batch, BatchFinance, Sale, StockPurchase
from app.utils.audit import log_action
from app.utils.zootechnie import recompute_batch_finance


@poultry_bp.route("/lots/<int:batch_id>/ventes", methods=["GET", "POST"])
@owner_required
def sales_list(batch_id):
    batch = _get_batch_or_403(batch_id)
    form = SaleForm(sale_date=date.today())
    if request.method == "GET" and current_user.tenant and current_user.tenant.default_sale_unit:
        form.unit.data = current_user.tenant.default_sale_unit

    if form.validate_on_submit():
        total_amount = form.quantity.data * form.unit_price.data
        amount_paid = form.amount_paid.data or 0
        if amount_paid > total_amount:
            flash(_("Le montant recu ne peut pas depasser le montant total de la vente."), "danger")
            return render_template(
                "poultry/sales_list.html", batch=batch, form=form, sales=batch.sales,
                cash_collected=sum((s.amount_paid or 0) for s in batch.sales),
                cash_outstanding=sum((s.balance_due or 0) for s in batch.sales),
            )

        sale = Sale(
            tenant_id=current_user.tenant_id,
            batch_id=batch.id,
            sale_date=form.sale_date.data,
            buyer_name=form.buyer_name.data,
            buyer_phone=form.buyer_phone.data,
            quantity=form.quantity.data,
            unit=form.unit.data,
            unit_price=form.unit_price.data,
            total_amount=total_amount,
            amount_paid=amount_paid,
            notes=form.notes.data,
            created_by=current_user.id,
        )
        db.session.add(sale)
        db.session.flush()
        recompute_batch_finance(batch)
        log_action("create", "poultry_sales", sale.id, {"buyer_name": sale.buyer_name, "total_amount": str(total_amount)})
        db.session.commit()
        flash(_("Vente a %(buyer_name)s enregistree.", buyer_name=sale.buyer_name), "success")
        return redirect(url_for("poultry.sales_list", batch_id=batch.id))

    sales = sorted(batch.sales, key=lambda s: s.sale_date, reverse=True)
    payment_form = SalePaymentForm()
    return render_template(
        "poultry/sales_list.html", batch=batch, form=form, sales=sales, payment_form=payment_form,
        cash_collected=sum((s.amount_paid or 0) for s in sales),
        cash_outstanding=sum((s.balance_due or 0) for s in sales),
    )


def _get_sale_or_403(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    if not ensure_farm_access(sale.batch.farm):
        abort(403)
    return sale


@poultry_bp.route("/ventes/<int:sale_id>/paiement", methods=["POST"])
@owner_required
def sale_payment(sale_id):
    sale = _get_sale_or_403(sale_id)
    form = SalePaymentForm()

    if form.validate_on_submit():
        amount = form.amount.data
        if amount > sale.balance_due:
            flash(
                _("Ce paiement (%(amount)s FCFA) depasse le solde restant du (%(balance_due)s FCFA). Verifiez le montant.", amount=amount, balance_due=sale.balance_due),
                "danger",
            )
        else:
            sale.amount_paid = (sale.amount_paid or 0) + amount
            log_action("update", "poultry_sales", sale.id, {"payment": str(amount)})
            db.session.commit()
            flash(_("Paiement enregistre."), "success")
    else:
        flash(_("Montant invalide."), "danger")

    return redirect(request.referrer or url_for("poultry.sales_list", batch_id=sale.batch_id))


@poultry_bp.route("/ventes/<int:sale_id>/supprimer", methods=["POST"])
@owner_required
def sale_delete(sale_id):
    sale = _get_sale_or_403(sale_id)
    batch = sale.batch
    log_action("delete", "poultry_sales", sale.id, {"buyer_name": sale.buyer_name})
    db.session.delete(sale)
    db.session.flush()
    recompute_batch_finance(batch)
    db.session.commit()
    flash(_("Vente supprimee."), "success")
    return redirect(url_for("poultry.sales_list", batch_id=batch.id))


@poultry_bp.route("/creances")
@owner_required
def credits_list():
    """Vue transversale (tous lots confondus) des ventes dont le solde
    n'est pas entierement regle - pour savoir en un coup d'oeil qui doit
    encore de l'argent a l'eleveur."""
    farm_ids = [f.id for f in current_user.tenant.farms] if current_user.tenant else []
    all_sales = (
        Sale.query.join(Batch, Sale.batch_id == Batch.id)
        .filter(Batch.farm_id.in_(farm_ids))
        .order_by(Sale.sale_date.desc())
        .all()
        if farm_ids
        else []
    )
    unpaid = [s for s in all_sales if not s.is_paid]
    total_due = sum((s.balance_due for s in unpaid), 0)
    return render_template("poultry/credits_list.html", sales=unpaid, total_due=total_due)


@poultry_bp.route("/depenses")
@owner_required
def expenses_summary():
    """Vue consolidee de toutes les depenses de l'exploitation, tous lots et
    toutes fermes confondus : les achats de stock (StockPurchase - de
    l'argent reellement sorti pour acheter aliment/bois/medicaments) d'une
    part, et les couts sans lien au stock (poussins, main d'oeuvre, saisis
    directement par lot) d'autre part. Ne pas additionner les couts de
    consommation du rapport de lot (total_feed_cost etc.) ici : ils ne font
    que revaloriser un stock deja compte comme depense a l'achat, ce qui
    compterait deux fois le meme argent depense."""
    farm_ids = [f.id for f in current_user.tenant.farms] if current_user.tenant else []

    purchases_by_category = {}
    purchases_total = 0
    if farm_ids:
        rows = (
            StockPurchase.query.filter(StockPurchase.farm_id.in_(farm_ids))
            .with_entities(StockPurchase.category, func.coalesce(func.sum(StockPurchase.total_cost), 0))
            .group_by(StockPurchase.category)
            .all()
        )
        purchases_by_category = {category: total for category, total in rows}
        purchases_total = sum(purchases_by_category.values())

    chick_cost_total = 0
    labor_cost_total = 0
    if farm_ids:
        batch_ids = [b.id for b in Batch.query.filter(Batch.farm_id.in_(farm_ids)).with_entities(Batch.id)]
        if batch_ids:
            chick_cost_total, labor_cost_total = (
                BatchFinance.query.filter(BatchFinance.batch_id.in_(batch_ids))
                .with_entities(
                    func.coalesce(func.sum(BatchFinance.chick_cost), 0),
                    func.coalesce(func.sum(BatchFinance.labor_cost), 0),
                )
                .first()
            )

    grand_total = purchases_total + chick_cost_total + labor_cost_total

    return render_template(
        "poultry/expenses_summary.html",
        purchases_by_category=purchases_by_category,
        purchases_total=purchases_total,
        chick_cost_total=chick_cost_total,
        labor_cost_total=labor_cost_total,
        grand_total=grand_total,
        category_labels={"feed": _("Aliment"), "wood": _("Bois / litiere"), "medication": _("Medicament")},
    )

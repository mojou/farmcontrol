"""Abonnement et paiement (CinetPay - Mobile Money / carte, tarifs en FCFA).

Parcours :
  1. Le proprietaire choisit un plan sur /tarifs ou /facturation.
  2. POST /facturation/souscrire/<code> cree une transaction et redirige
     vers la page de paiement CinetPay (ou simule le succes si CinetPay
     n'est pas configure, en mode demonstration).
  3. CinetPay redirige l'utilisateur vers /facturation/retour (confirmation
     visuelle) ET notifie le serveur en arriere-plan sur /facturation/notify
     (source de verite : ne jamais activer un abonnement sur la seule foi
     de la redirection navigateur).
"""
import uuid
from datetime import timedelta

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.blueprints.billing import billing_bp
from app.decorators import owner_required
from app.extensions import csrf, db
from app.models import utcnow
from app.models.billing import (
    PAYMENT_STATUS_COMPLETED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PENDING,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_TRIALING,
    PaymentTransaction,
    Plan,
    Subscription,
)
from app.utils.audit import log_action
from app.utils.cinetpay import CinetPayError, init_payment, verify_payment
from app.utils.plans import ensure_plans_seeded
from app.utils.tenant import tenant_bypass


@billing_bp.route("/tarifs")
def pricing():
    ensure_plans_seeded()
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order).all()
    current_plan_code = None
    if current_user.is_authenticated and current_user.tenant and current_user.tenant.subscription:
        current_plan_code = current_user.tenant.subscription.plan.code
    return render_template("billing/pricing.html", plans=plans, current_plan_code=current_plan_code)


@billing_bp.route("/facturation")
@owner_required
def billing_home():
    ensure_plans_seeded()
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order).all()
    subscription = current_user.tenant.subscription if current_user.tenant else None
    current_plan_code = subscription.plan.code if subscription else None
    transactions = (
        PaymentTransaction.query.order_by(PaymentTransaction.created_at.desc()).limit(20).all()
    )
    return render_template(
        "billing/billing_home.html",
        plans=plans,
        subscription=subscription,
        transactions=transactions,
        current_plan_code=current_plan_code,
    )


@billing_bp.route("/facturation/souscrire/<plan_code>", methods=["POST"])
@owner_required
def subscribe(plan_code):
    plan = Plan.query.filter_by(code=plan_code, is_active=True).first_or_404()
    tenant = current_user.tenant

    if plan.price_xaf == 0:
        _activate_subscription(tenant, plan)
        flash(f"Plan {plan.name} active.", "success")
        return redirect(url_for("billing.billing_home"))

    transaction_id = f"fc-{tenant.id}-{uuid.uuid4().hex[:12]}"
    payment_tx = PaymentTransaction(
        tenant_id=tenant.id,
        plan_id=plan.id,
        provider="cinetpay",
        provider_transaction_id=transaction_id,
        amount_xaf=plan.price_xaf,
        status=PAYMENT_STATUS_PENDING,
    )
    db.session.add(payment_tx)
    db.session.commit()

    try:
        result = init_payment(
            transaction_id=transaction_id,
            amount_xaf=plan.price_xaf,
            description=f"Abonnement Farm Control - {plan.name}",
            customer_email=current_user.email,
            customer_name=current_user.full_name,
            notify_url=url_for("billing.payment_notify", _external=True),
            return_url=url_for("billing.payment_return", transaction_id=transaction_id, _external=True),
        )
    except CinetPayError as exc:
        payment_tx.status = PAYMENT_STATUS_FAILED
        db.session.commit()
        flash(f"Erreur lors de l'initialisation du paiement : {exc}", "danger")
        return redirect(url_for("billing.billing_home"))

    if result["simulated"]:
        # CinetPay non configure : simule un paiement reussi pour permettre
        # de demontrer le parcours complet avant la mise en production.
        payment_tx.status = PAYMENT_STATUS_COMPLETED
        payment_tx.payment_method = "SIMULATION"
        db.session.commit()
        _activate_subscription(tenant, plan)
        flash(
            f"Mode demonstration : paiement simule et plan {plan.name} active "
            "(CinetPay n'est pas encore configure).",
            "warning",
        )
        return redirect(url_for("billing.billing_home"))

    payment_tx.raw_response = result["raw"]
    db.session.commit()
    return redirect(result["payment_url"])


@billing_bp.route("/facturation/retour")
def payment_return():
    transaction_id = request.args.get("transaction_id")
    with tenant_bypass():
        payment_tx = PaymentTransaction.query.filter_by(provider_transaction_id=transaction_id).first()

    if payment_tx is None:
        abort(404)

    if payment_tx.status == PAYMENT_STATUS_PENDING:
        _confirm_payment(payment_tx)

    return render_template("billing/payment_return.html", payment_tx=payment_tx)


@billing_bp.route("/facturation/notify", methods=["POST"])
@csrf.exempt
def payment_notify():
    """Webhook serveur-a-serveur CinetPay : source de verite du paiement."""
    transaction_id = request.form.get("cpm_trans_id") or request.args.get("cpm_trans_id")
    if not transaction_id:
        return "missing transaction_id", 400

    with tenant_bypass():
        payment_tx = PaymentTransaction.query.filter_by(provider_transaction_id=transaction_id).first()

    if payment_tx is None:
        return "unknown transaction", 404

    if payment_tx.status == PAYMENT_STATUS_PENDING:
        _confirm_payment(payment_tx)

    return "OK", 200


def _confirm_payment(payment_tx):
    """Verifie aupres de CinetPay et active l'abonnement si le paiement est accepte."""
    try:
        with tenant_bypass():
            result = verify_payment(payment_tx.provider_transaction_id)
    except CinetPayError:
        current_app.logger.exception("Echec de verification du paiement CinetPay")
        return

    with tenant_bypass():
        payment_tx.raw_response = result["raw"]
        payment_tx.payment_method = result.get("payment_method")

        if result["status"] == "ACCEPTED":
            payment_tx.status = PAYMENT_STATUS_COMPLETED
            db.session.commit()
            tenant = payment_tx.tenant
            _activate_subscription(tenant, payment_tx.plan)
        else:
            payment_tx.status = PAYMENT_STATUS_FAILED
            db.session.commit()


def _activate_subscription(tenant, plan):
    with tenant_bypass():
        subscription = tenant.subscription
        if subscription is None:
            subscription = Subscription(tenant_id=tenant.id, plan_id=plan.id)
            db.session.add(subscription)

        subscription.plan_id = plan.id
        subscription.status = SUBSCRIPTION_STATUS_ACTIVE if plan.price_xaf > 0 else SUBSCRIPTION_STATUS_TRIALING
        subscription.current_period_start = utcnow()
        subscription.current_period_end = (
            None if plan.price_xaf == 0 else utcnow() + timedelta(days=plan.billing_period_days)
        )
        tenant.plan = plan.code
        log_action("update", "billing_subscriptions", subscription.id, {"plan": plan.code})
        db.session.commit()

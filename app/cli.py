"""Commandes CLI Flask personnalisees.

Usage :
    flask create-superadmin --email admin@farmcontrol.app --password ...
    flask seed-demo
"""
import random
from datetime import date, timedelta
from decimal import Decimal

import click

from app.extensions import db
from app.models.core import ROLE_OWNER, ROLE_SUPER_ADMIN, Tenant, User
from app.models.poultry import (
    Batch,
    BatchDay,
    DailyReport,
    Farm,
    FeedRecord,
    MortalityRecord,
    REPORT_STATUS_REVIEWED,
    Sale,
    StockItem,
    Supplier,
    WaterRecord,
    WeightRecord,
)
from app.utils.tenant import tenant_bypass
from app.utils.zootechnie import recompute_batch_finance


def register_cli(app):
    app.cli.add_command(create_superadmin)
    app.cli.add_command(seed_demo)


@click.command("create-superadmin")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--first-name", default="Super", show_default=True)
@click.option("--last-name", default="Admin", show_default=True)
def create_superadmin(email, password, first_name, last_name):
    """Cree un compte super administrateur de la plateforme."""
    with tenant_bypass():
        existing = User.query.filter_by(email=email.strip().lower()).first()
        if existing:
            click.echo("Un utilisateur existe deja avec cet email.")
            return

        user = User(
            tenant_id=None,
            email=email.strip().lower(),
            first_name=first_name,
            last_name=last_name,
            role=ROLE_SUPER_ADMIN,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    click.echo(f"Super administrateur {email} cree avec succes.")


@click.command("seed-demo")
def seed_demo():
    """Cree/reinitialise le tenant de demonstration (paragraphe 10).

    Comprend 2 fermes fictives, 1 lot en cours avec plusieurs jours deja
    remplis, quelques alertes et un stock partiellement consomme.
    """
    from app.utils.alerts import create_alert
    from app.models.poultry import ALERT_PRIORITY_URGENT, ALERT_PRIORITY_NORMAL

    slug = "demo"
    with tenant_bypass():
        existing_tenant = Tenant.query.filter_by(slug=slug).first()
        if existing_tenant:
            click.echo("Suppression de l'ancien tenant de demonstration...")
            db.session.delete(existing_tenant)
            db.session.commit()

        tenant = Tenant(name="Ferme Demo", slug=slug, is_demo=True, plan="standard")
        db.session.add(tenant)
        db.session.flush()

        owner = User(
            tenant_id=tenant.id,
            email="demo@farmcontrol.app",
            first_name="Amina",
            last_name="Traore",
            role=ROLE_OWNER,
        )
        owner.set_password("Demo1234!")
        db.session.add(owner)
        db.session.flush()

        from app.utils.tenant import tenant_context

        with tenant_context(tenant.id):
            farm1 = Farm(tenant_id=tenant.id, name="Ferme Nord", location="Route de Ziguinchor")
            farm2 = Farm(tenant_id=tenant.id, name="Ferme Sud", location="Route de Thies")
            db.session.add_all([farm1, farm2])
            db.session.flush()

            supplier_chicks = Supplier(
                tenant_id=tenant.id, name="Couvoir Regional", category=Supplier.CATEGORY_CHICK,
                phone="677000000", notes="Livraison fiable, poussins vaccines a la naissance.",
            )
            db.session.add(supplier_chicks)
            db.session.flush()

            batch = Batch(
                tenant_id=tenant.id,
                farm_id=farm1.id,
                code="LOT-DEMO-01",
                breed="Ross 308",
                initial_count=1000,
                chick_unit_price=Decimal("300"),
                supplier_id=supplier_chicks.id,
                start_date=date.today() - timedelta(days=14),
                created_by=owner.id,
            )
            db.session.add(batch)
            db.session.flush()

            random.seed(42)
            for day_number in range(1, 15):
                day = BatchDay(
                    tenant_id=tenant.id,
                    batch_id=batch.id,
                    day_number=day_number,
                    date=batch.start_date + timedelta(days=day_number - 1),
                )
                db.session.add(day)
                db.session.flush()

                feed_kg = Decimal(str(round(15 + day_number * 2.3, 1)))
                db.session.add(
                    FeedRecord(
                        tenant_id=tenant.id,
                        batch_id=batch.id,
                        batch_day_id=day.id,
                        feed_type="Demarrage" if day_number <= 10 else "Croissance",
                        quantity_kg=feed_kg,
                        unit_price=Decimal("450"),
                        created_by=owner.id,
                    )
                )
                db.session.add(
                    WaterRecord(
                        tenant_id=tenant.id,
                        batch_id=batch.id,
                        batch_day_id=day.id,
                        quantity_liters=Decimal(str(round(20 + day_number * 3, 1))),
                        created_by=owner.id,
                    )
                )
                deaths = random.choice([0, 0, 0, 1, 1, 2])
                if deaths:
                    db.session.add(
                        MortalityRecord(
                            tenant_id=tenant.id,
                            batch_id=batch.id,
                            batch_day_id=day.id,
                            quantity_dead=deaths,
                            cause="Cause naturelle",
                            created_by=owner.id,
                        )
                    )
                if day_number in (7, 14):
                    db.session.add(
                        WeightRecord(
                            tenant_id=tenant.id,
                            farm_id=farm1.id,
                            batch_id=batch.id,
                            batch_day_id=day.id,
                            average_weight=Decimal(str(150 + day_number * 55)),
                            sample_size=20,
                            created_by=owner.id,
                        )
                    )

                report = DailyReport(
                    tenant_id=tenant.id,
                    batch_id=batch.id,
                    batch_day_id=day.id,
                    status=REPORT_STATUS_REVIEWED,
                )
                db.session.add(report)

            sale_paid = Sale(
                tenant_id=tenant.id, batch_id=batch.id,
                sale_date=date.today() - timedelta(days=2),
                buyer_name="Mme Njoya (restauratrice)", buyer_phone="699111222",
                quantity=Decimal("50"), unit=Sale.UNIT_SUBJECT, unit_price=Decimal("3500"),
                total_amount=Decimal("175000"), amount_paid=Decimal("175000"),
                created_by=owner.id,
            )
            sale_credit = Sale(
                tenant_id=tenant.id, batch_id=batch.id,
                sale_date=date.today() - timedelta(days=1),
                buyer_name="M. Talla (revendeur)", buyer_phone="655333444",
                quantity=Decimal("30"), unit=Sale.UNIT_SUBJECT, unit_price=Decimal("3500"),
                total_amount=Decimal("105000"), amount_paid=Decimal("50000"),
                notes="Reste a payer sous 1 semaine", created_by=owner.id,
            )
            db.session.add_all([sale_paid, sale_credit])
            db.session.flush()

            recompute_batch_finance(batch)

            stock_feed = StockItem(
                tenant_id=tenant.id,
                farm_id=farm1.id,
                category=StockItem.CATEGORY_FEED,
                name="Aliment demarrage",
                unit="sac",
                quantity_on_hand=Decimal("2"),
                min_threshold=Decimal("3"),
                unit_price=Decimal("22500"),
                kg_per_unit=Decimal("50"),
            )
            stock_wood = StockItem(
                tenant_id=tenant.id,
                farm_id=farm1.id,
                category=StockItem.CATEGORY_WOOD,
                name="Copeaux de bois",
                unit="morceau",
                quantity_on_hand=Decimal("300"),
                min_threshold=Decimal("100"),
                unit_price=Decimal("50"),
            )
            stock_medication = StockItem(
                tenant_id=tenant.id,
                farm_id=farm1.id,
                category=StockItem.CATEGORY_MEDICATION,
                name="Belgo Protect",
                unit="L",
                quantity_on_hand=Decimal("3"),
                min_threshold=Decimal("1"),
                unit_price=Decimal("4500"),
                ml_per_unit=Decimal("1000"),
            )
            db.session.add_all([stock_feed, stock_wood, stock_medication])
            db.session.flush()

            create_alert(
                title="Stock faible : Aliment demarrage",
                message="Le stock d'aliment demarrage est descendu sous le seuil d'alerte.",
                alert_type="stock",
                priority=ALERT_PRIORITY_URGENT,
                farm=farm1,
            )
            create_alert(
                title="Rapport journalier recu",
                message="Le rapport du jour 14 a ete valide.",
                alert_type="report_missing",
                priority=ALERT_PRIORITY_NORMAL,
                batch=batch,
            )

            db.session.commit()

    click.echo("Tenant de demonstration cree : email demo@farmcontrol.app / mot de passe Demo1234!")

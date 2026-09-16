"""Modeles du module Poulets de chair.

Conventions :
- Toutes les quantites d'aliment/bois/medicaments sont stockees avec leur
  cout unitaire au moment de la saisie (le prix peut changer dans le temps,
  on ne veut pas fausser l'historique).
- BatchDay materialise "un jour" d'un lot et sert de point d'ancrage a tous
  les enregistrements quotidiens (aliment, eau, mortalite, bois,
  medicaments, observations, pesees).
"""
from decimal import Decimal

from app.extensions import db
from app.models import TenantMixin, TimestampMixin
from app.models.core import User

# -- Constantes -----------------------------------------------------------

BATCH_STATUS_ACTIVE = "active"
BATCH_STATUS_CLOSED = "closed"
BATCH_STATUSES = [BATCH_STATUS_ACTIVE, BATCH_STATUS_CLOSED]

OBS_SEVERITY_NORMAL = "normal"
OBS_SEVERITY_URGENT = "urgent"
OBS_SEVERITIES = [OBS_SEVERITY_NORMAL, OBS_SEVERITY_URGENT]

ALERT_TYPE_STOCK = "stock"
ALERT_TYPE_MORTALITY = "mortality"
ALERT_TYPE_SANITARY = "sanitary"
ALERT_TYPE_OBSERVATION = "observation"
ALERT_TYPE_REPORT_MISSING = "report_missing"
ALERT_TYPE_FCR = "fcr"
ALERT_TYPES = [
    ALERT_TYPE_STOCK,
    ALERT_TYPE_MORTALITY,
    ALERT_TYPE_SANITARY,
    ALERT_TYPE_OBSERVATION,
    ALERT_TYPE_REPORT_MISSING,
    ALERT_TYPE_FCR,
]

ALERT_PRIORITY_NORMAL = "normal"
ALERT_PRIORITY_IMPORTANT = "important"
ALERT_PRIORITY_URGENT = "urgent"
ALERT_PRIORITIES = [ALERT_PRIORITY_NORMAL, ALERT_PRIORITY_IMPORTANT, ALERT_PRIORITY_URGENT]

REPORT_STATUS_DRAFT = "draft"
REPORT_STATUS_SUBMITTED = "submitted"
REPORT_STATUS_REVIEWED = "reviewed"
REPORT_STATUSES = [REPORT_STATUS_DRAFT, REPORT_STATUS_SUBMITTED, REPORT_STATUS_REVIEWED]


class Farm(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "farms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    tenant = db.relationship("Tenant", back_populates="farms")
    batches = db.relationship("Batch", back_populates="farm", cascade="all, delete-orphan")
    workers = db.relationship(
        "User", back_populates="farm", foreign_keys="User.farm_id"
    )
    stock_items = db.relationship(
        "StockItem", back_populates="farm", cascade="all, delete-orphan"
    )
    alerts = db.relationship(
        "Alert", back_populates="farm", cascade="all, delete-orphan",
        foreign_keys="Alert.farm_id",
    )
    stock_purchases = db.relationship(
        "StockPurchase", back_populates="farm", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Farm {self.name}>"


class Supplier(TimestampMixin, TenantMixin, db.Model):
    """Fournisseur (poussins, aliment, medicaments...) - permet de suivre
    dans le temps la fiabilite d'un fournisseur (prix, retards, qualite)
    plutot que de perdre cette information a chaque achat."""

    __tablename__ = "poultry_suppliers"

    CATEGORY_CHICK = "chick"
    CATEGORY_FEED = "feed"
    CATEGORY_MEDICATION = "medication"
    CATEGORY_OTHER = "other"
    CATEGORIES = [CATEGORY_CHICK, CATEGORY_FEED, CATEGORY_MEDICATION, CATEGORY_OTHER]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(20), nullable=False, default=CATEGORY_OTHER)
    phone = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Supplier {self.name}>"


class Batch(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_batches"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False, index=True)

    code = db.Column(db.String(50), nullable=False)
    breed = db.Column(db.String(100), nullable=True)  # souche
    initial_count = db.Column(db.Integer, nullable=False)
    chick_unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("poultry_suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=BATCH_STATUS_ACTIVE)
    growth_reference_id = db.Column(
        db.Integer, db.ForeignKey("poultry_growth_references.id", ondelete="SET NULL"), nullable=True
    )

    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    farm = db.relationship("Farm", back_populates="batches")
    growth_reference = db.relationship("GrowthReference")
    supplier = db.relationship("Supplier")
    sales = db.relationship("Sale", back_populates="batch", cascade="all, delete-orphan")
    days = db.relationship(
        "BatchDay", back_populates="batch", cascade="all, delete-orphan",
        order_by="BatchDay.day_number",
    )
    finance = db.relationship(
        "BatchFinance", back_populates="batch", uselist=False, cascade="all, delete-orphan"
    )
    sanitary_items = db.relationship(
        "SanitaryProgramItem", back_populates="batch", cascade="all, delete-orphan"
    )
    alerts = db.relationship(
        "Alert", back_populates="batch", cascade="all, delete-orphan",
        foreign_keys="Alert.batch_id",
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "farm_id", "code", name="uq_batch_tenant_farm_code"),
    )

    @property
    def is_active(self) -> bool:
        return self.status == BATCH_STATUS_ACTIVE

    @property
    def total_mortality(self) -> int:
        return sum(r.quantity_dead for day in self.days for r in day.mortality_records)

    @property
    def total_sold_subjects(self) -> int:
        """Nombre de sujets vendus (paragraphe ventes/effectif). Seules les
        ventes "au sujet" (Sale.unit == UNIT_SUBJECT) sont comptees : une
        vente "au kg" ne precise pas combien d'animaux ont ete preleves du
        cheptel, donc ne peut pas etre convertie en effectif sans supposer
        un poids moyen - on ne devine pas, on ne decompte que ce qui est
        sans ambiguite."""
        return int(sum(s.quantity for s in self.sales if s.unit == Sale.UNIT_SUBJECT))

    @property
    def current_count(self) -> int:
        return max(self.initial_count - self.total_mortality - self.total_sold_subjects, 0)

    @property
    def total_feed_kg(self):
        return sum(r.quantity_kg for day in self.days for r in day.feed_records)

    @property
    def contributors(self):
        """Utilisateurs ayant reellement saisi une donnee sur ce lot (aliment,
        eau, mortalite, bois, medicaments, pesee, observation) - pour savoir
        qui a travaille sur ce lot precis, pas seulement qui est rattache a
        la ferme en general."""
        user_ids = set()
        for day in self.days:
            for records in (
                day.feed_records, day.water_records, day.mortality_records,
                day.wood_records, day.medication_records, day.observations,
                day.weight_records,
            ):
                for record in records:
                    if record.created_by:
                        user_ids.add(record.created_by)
        if not user_ids:
            return []
        users = User.query.filter(User.id.in_(user_ids)).order_by(User.first_name, User.last_name).all()
        return users

    def __repr__(self):
        return f"<Batch {self.code}>"


class BatchDay(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_batch_days"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    day_number = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)

    batch = db.relationship("Batch", back_populates="days")
    feed_records = db.relationship("FeedRecord", back_populates="batch_day", cascade="all, delete-orphan")
    water_records = db.relationship("WaterRecord", back_populates="batch_day", cascade="all, delete-orphan")
    mortality_records = db.relationship("MortalityRecord", back_populates="batch_day", cascade="all, delete-orphan")
    wood_records = db.relationship("WoodRecord", back_populates="batch_day", cascade="all, delete-orphan")
    medication_records = db.relationship("MedicationRecord", back_populates="batch_day", cascade="all, delete-orphan")
    observations = db.relationship("Observation", back_populates="batch_day", cascade="all, delete-orphan")
    weight_records = db.relationship("WeightRecord", back_populates="batch_day", cascade="all, delete-orphan")
    report = db.relationship("DailyReport", back_populates="batch_day", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("batch_id", "day_number", name="uq_batchday_batch_daynumber"),
    )

    @property
    def mortality_count(self) -> int:
        return sum(r.quantity_dead for r in self.mortality_records)

    @property
    def feed_kg(self):
        return sum(r.quantity_kg for r in self.feed_records)


class StockItem(TimestampMixin, TenantMixin, db.Model):
    """Article de stock (aliment, bois/litiere, medicament) par ferme.

    Rattache aux enregistrements de consommation quotidienne pour permettre
    la detection automatique de stock faible (Phase 14, alerte "stock").
    """

    __tablename__ = "poultry_stock_items"

    CATEGORY_FEED = "feed"
    CATEGORY_WOOD = "wood"
    CATEGORY_MEDICATION = "medication"
    CATEGORIES = [CATEGORY_FEED, CATEGORY_WOOD, CATEGORY_MEDICATION]

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False, index=True)

    category = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    unit = db.Column(db.String(20), nullable=False, default="sac")
    quantity_on_hand = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    min_threshold = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Poids en kg d'une unite de stock (ex : 50 pour un sac d'aliment de 50kg).
    # Necessaire car la saisie quotidienne d'aliment se fait en kg (pour le
    # calcul de l'indice de consommation/FCR) alors que le stock d'aliment
    # se gere en sacs : on convertit les kg consommes en sacs a decompter.
    kg_per_unit = db.Column(db.Numeric(10, 2), nullable=True)
    # Volume en ml d'une unite de stock (ex : 1000 si vous stockez en litres,
    # 3000 pour une bouteille/boite de 3 litres comme les produits Belgo).
    # Les medicaments/complements liquides s'achetent en litres mais
    # s'administrent en ml : on convertit les ml donnes en unites de stock
    # a decompter, comme pour l'aliment (kg_per_unit) ci-dessus.
    ml_per_unit = db.Column(db.Numeric(10, 2), nullable=True)

    farm = db.relationship("Farm", back_populates="stock_items")

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "farm_id", "category", "name", name="uq_stockitem_tenant_farm_cat_name"),
    )

    @property
    def is_low(self) -> bool:
        return Decimal(self.quantity_on_hand or 0) <= Decimal(self.min_threshold or 0)


class StockPurchase(TimestampMixin, TenantMixin, db.Model):
    """Trace un achat de stock (creation d'article ou reapprovisionnement) en
    tant que depense reelle - independamment de la consommation, qui elle
    est deja suivie par lot via FeedRecord/WoodRecord/MedicationRecord.total_cost.
    Un achat de stock n'est jamais rattache a un lot precis (le stock est
    partage par ferme, entre lots actifs) : ces depenses apparaissent donc
    au niveau de la ferme (page Stock), separement de la rentabilite d'un
    lot qui ne reflete que ce qui a ete reellement consomme par ce lot."""

    __tablename__ = "poultry_stock_purchases"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False, index=True)
    stock_item_id = db.Column(
        db.Integer, db.ForeignKey("poultry_stock_items.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category = db.Column(db.String(20), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    purchase_date = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    farm = db.relationship("Farm", back_populates="stock_purchases")
    stock_item = db.relationship("StockItem")


class FeedRecord(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_feed_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)
    stock_item_id = db.Column(
        db.Integer, db.ForeignKey("poultry_stock_items.id", ondelete="SET NULL"), nullable=True, index=True
    )

    feed_type = db.Column(db.String(100), nullable=False)
    quantity_kg = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="feed_records")
    stock_item = db.relationship("StockItem", foreign_keys=[stock_item_id])

    @property
    def total_cost(self):
        return (self.quantity_kg or 0) * (self.unit_price or 0)


class WaterRecord(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_water_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)

    quantity_liters = db.Column(db.Numeric(10, 2), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="water_records")


class MortalityRecord(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_mortality_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)

    quantity_dead = db.Column(db.Integer, nullable=False)
    cause = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="mortality_records")


class WoodRecord(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_wood_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)
    stock_item_id = db.Column(
        db.Integer, db.ForeignKey("poultry_stock_items.id", ondelete="SET NULL"), nullable=True, index=True
    )

    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="wood_records")
    stock_item = db.relationship("StockItem", foreign_keys=[stock_item_id])

    @property
    def total_cost(self):
        return (self.quantity or 0) * (self.unit_price or 0)


class MedicationRecord(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_medication_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)
    stock_item_id = db.Column(
        db.Integer, db.ForeignKey("poultry_stock_items.id", ondelete="SET NULL"), nullable=True, index=True
    )

    medication_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="medication_records")
    stock_item = db.relationship("StockItem", foreign_keys=[stock_item_id])

    @property
    def total_cost(self):
        return (self.quantity or 0) * (self.unit_price or 0)


class Observation(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "poultry_observations"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)

    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default=OBS_SEVERITY_NORMAL)
    photo_path = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="observations")


class WeightRecord(TimestampMixin, TenantMixin, db.Model):
    """Pesees (paragraphe 1.1)."""

    __tablename__ = "poultry_weight_records"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, index=True)

    average_weight = db.Column(db.Numeric(10, 2), nullable=False)  # grammes
    sample_size = db.Column(db.Integer, nullable=False)
    observation = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch_day = db.relationship("BatchDay", back_populates="weight_records")


class Sale(TimestampMixin, TenantMixin, db.Model):
    """Une vente de volailles a un acheteur, a une date donnee.

    Remplace/complete l'ancien champ unique de BatchFinance (sale_quantity/
    sale_unit_price) : un eleveur vend generalement son lot progressivement,
    a plusieurs acheteurs, parfois a credit (paiement partiel). Chaque vente
    garde son propre solde du (balance_due) pour le suivi des creances.
    """

    __tablename__ = "poultry_sales"

    UNIT_KG = "kg"
    UNIT_SUBJECT = "unit"
    UNITS = [UNIT_KG, UNIT_SUBJECT]

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)

    sale_date = db.Column(db.Date, nullable=False)
    buyer_name = db.Column(db.String(150), nullable=False)
    buyer_phone = db.Column(db.String(30), nullable=True)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(10), nullable=False, default=UNIT_SUBJECT)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch = db.relationship("Batch", back_populates="sales")

    @property
    def balance_due(self):
        return (self.total_amount or 0) - (self.amount_paid or 0)

    @property
    def is_paid(self) -> bool:
        return self.balance_due <= 0


class BatchFinance(TimestampMixin, TenantMixin, db.Model):
    """Rentabilite du lot (paragraphe 2)."""

    __tablename__ = "poultry_batch_finance"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, unique=True, index=True)

    chick_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_feed_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_medication_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_wood_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    labor_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    sale_quantity = db.Column(db.Integer, nullable=True)
    sale_unit = db.Column(db.String(10), nullable=False, default="kg")  # kg ou unite
    sale_unit_price = db.Column(db.Numeric(10, 2), nullable=True)
    sale_revenue = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    net_result = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cost_per_kg = db.Column(db.Numeric(10, 2), nullable=True)

    batch = db.relationship("Batch", back_populates="finance")

    @property
    def total_charges(self):
        return (
            (self.chick_cost or 0)
            + (self.total_feed_cost or 0)
            + (self.total_medication_cost or 0)
            + (self.total_wood_cost or 0)
            + (self.labor_cost or 0)
        )


class Alert(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=True, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=True, index=True)

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default=ALERT_PRIORITY_NORMAL)
    is_read = db.Column(db.Boolean, nullable=False, default=False)

    email_sent = db.Column(db.Boolean, nullable=False, default=False)
    email_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    farm = db.relationship("Farm", back_populates="alerts", foreign_keys=[farm_id])
    batch = db.relationship("Batch", back_populates="alerts", foreign_keys=[batch_id])

    @property
    def requires_email(self) -> bool:
        return self.priority in (ALERT_PRIORITY_URGENT, ALERT_PRIORITY_IMPORTANT)


class SanitaryProgramItem(TimestampMixin, TenantMixin, db.Model):
    """Programme sanitaire (vaccinations / traitements planifies par lot)."""

    __tablename__ = "poultry_sanitary_program_items"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)

    day_number = db.Column(db.Integer, nullable=False)
    program_type = db.Column(db.String(30), nullable=False, default="vaccination")
    product_name = db.Column(db.String(150), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    is_done = db.Column(db.Boolean, nullable=False, default=False)
    done_at = db.Column(db.DateTime(timezone=True), nullable=True)
    done_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    batch = db.relationship("Batch", back_populates="sanitary_items")


class SanitaryProgramTemplateItem(TimestampMixin, TenantMixin, db.Model):
    """Modele de programme sanitaire propre a chaque tenant.

    Chaque proprietaire definit ici SA propre facon de gerer ses lots (ses
    produits, ses jours, sa posologie). Ce modele est copie automatiquement
    dans poultry_sanitary_program_items a la creation de chaque nouveau lot
    (voir app.utils.sanitary.seed_batch_program_from_template). Independant
    de tout lot en particulier : modifier le modele n'affecte pas les lots
    deja crees.
    """

    __tablename__ = "poultry_sanitary_program_template_items"

    id = db.Column(db.Integer, primary_key=True)

    day_number = db.Column(db.Integer, nullable=False)
    program_type = db.Column(db.String(30), nullable=False, default="vaccination")
    product_name = db.Column(db.String(150), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class DailyReport(TimestampMixin, TenantMixin, db.Model):
    """Workflow de validation du rapport journalier (paragraphe 9)."""

    __tablename__ = "poultry_daily_reports"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("poultry_batches.id"), nullable=False, index=True)
    batch_day_id = db.Column(db.Integer, db.ForeignKey("poultry_batch_days.id"), nullable=False, unique=True, index=True)

    status = db.Column(db.String(20), nullable=False, default=REPORT_STATUS_DRAFT)
    notes = db.Column(db.Text, nullable=True)

    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    batch = db.relationship("Batch")
    batch_day = db.relationship("BatchDay", back_populates="report")


class GrowthReference(TimestampMixin, TenantMixin, db.Model):
    """Courbe de croissance de reference, parametrable par souche (paragraphe 1.3)."""

    __tablename__ = "poultry_growth_references"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # ex: "Ross 308"
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    points = db.relationship(
        "GrowthReferencePoint", back_populates="reference", cascade="all, delete-orphan",
        order_by="GrowthReferencePoint.day_number",
    )


class GrowthReferencePoint(TenantMixin, db.Model):
    __tablename__ = "poultry_growth_reference_points"

    id = db.Column(db.Integer, primary_key=True)
    reference_id = db.Column(db.Integer, db.ForeignKey("poultry_growth_references.id"), nullable=False, index=True)
    day_number = db.Column(db.Integer, nullable=False)
    expected_weight = db.Column(db.Numeric(10, 2), nullable=False)  # grammes

    reference = db.relationship("GrowthReference", back_populates="points")

    __table_args__ = (
        db.UniqueConstraint("reference_id", "day_number", name="uq_growthpoint_ref_day"),
    )

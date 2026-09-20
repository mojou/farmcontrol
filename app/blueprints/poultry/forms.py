from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional

from app.utils.species import DEFAULT_SPECIES, SPECIES_CHOICES


class FarmForm(FlaskForm):
    name = StringField(_l("Nom de la ferme"), validators=[DataRequired()])
    location = StringField(_l("Localisation"), validators=[Optional()])
    submit = SubmitField(_l("Enregistrer"))


class BatchForm(FlaskForm):
    farm_id = SelectField(_l("Ferme"), coerce=int, validators=[DataRequired()])
    species = SelectField(_l("Type d'elevage"), choices=SPECIES_CHOICES, default=DEFAULT_SPECIES)
    code = StringField(_l("Code / nom du lot"), validators=[DataRequired()])
    breed = StringField(_l("Souche"), validators=[Optional()])
    initial_count = IntegerField(_l("Nombre d'animaux au depart"), validators=[DataRequired(), NumberRange(min=1)])
    chick_unit_price = DecimalField(_l("Prix d'achat unitaire (poussin, porcelet, alevin...)"), validators=[DataRequired(), NumberRange(min=0)], places=2)
    supplier_id = SelectField(_l("Fournisseur des jeunes animaux (facultatif)"), coerce=int, validators=[Optional()])
    start_date = DateField(_l("Date de mise en place"), validators=[DataRequired()])
    growth_reference_id = SelectField(_l("Poids normal attendu (souche)"), coerce=int, validators=[Optional()])
    start_age_weeks = IntegerField(
        _l("Age des poules a la mise en place (en semaines)"),
        validators=[Optional(), NumberRange(min=0, max=120)],
        default=0,
        render_kw={"placeholder": _l("Ex : 18 (0 si poussins d'un jour)")},
    )
    laying_reference_id = SelectField(_l("Ponte attendue (courbe)"), coerce=int, validators=[Optional()])
    submit = SubmitField(_l("Enregistrer"))


class SupplierForm(FlaskForm):
    name = StringField(
        _l("Nom du fournisseur"),
        validators=[DataRequired()],
        render_kw={"placeholder": _l("Ex : Couvoir Nord, Ferme Avicole du Littoral...")},
    )
    category = SelectField(
        _l("Fournit principalement"),
        choices=[
            ("chick", _l("Jeunes animaux (poussins, porcelets...)")),
            ("feed", _l("Aliment")),
            ("medication", _l("Medicaments")),
            ("other", _l("Autre")),
        ],
    )
    phone = StringField(_l("Telephone (facultatif)"), validators=[Optional()], render_kw={"placeholder": _l("Ex : 6XX XXX XXX")})
    notes = TextAreaField(_l("Notes (facultatif)"), validators=[Optional()], render_kw={"placeholder": _l("Fiabilite, delais, qualite...")})
    submit = SubmitField(_l("Enregistrer"))


class SaleForm(FlaskForm):
    sale_date = DateField(_l("Date de la vente"), validators=[DataRequired()])
    buyer_name = StringField(
        _l("Nom de l'acheteur"), validators=[DataRequired()], render_kw={"placeholder": _l("Ex : Mme Njoya")}
    )
    buyer_phone = StringField(_l("Telephone de l'acheteur (facultatif)"), validators=[Optional()])
    quantity = DecimalField(
        _l("Quantite vendue"), validators=[DataRequired(), NumberRange(min=0.01)], places=2,
        render_kw={"placeholder": _l("Ex : 50")},
    )
    unit = SelectField(_l("Unite"), choices=[("unit", _l("Poulets")), ("kg", _l("Kilogrammes"))], default="unit")
    unit_price = DecimalField(
        _l("Prix unitaire (FCFA)"), validators=[DataRequired(), NumberRange(min=0)], places=2,
        render_kw={"placeholder": _l("Ex : 3500")},
    )
    amount_paid = DecimalField(
        _l("Montant deja recu (FCFA)"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0,
        render_kw={"placeholder": _l("Ex : 0 si tout est a credit, ou le montant total si tout est paye")},
    )
    notes = TextAreaField(_l("Notes (facultatif)"), validators=[Optional()])
    submit = SubmitField(_l("Enregistrer la vente"))


class SalePaymentForm(FlaskForm):
    amount = DecimalField(
        _l("Montant recu"), validators=[DataRequired(), NumberRange(min=0.01)], places=2,
        render_kw={"placeholder": _l("Ex : 20000")},
    )
    submit = SubmitField(_l("Enregistrer le paiement"))


class BatchCloseForm(FlaskForm):
    end_date = DateField(_l("Date de cloture"), validators=[DataRequired()])
    submit = SubmitField(_l("Cloturer le lot"))


class FeedRecordForm(FlaskForm):
    feed_type = StringField(
        _l("Type d'aliment donne"),
        validators=[DataRequired()],
        render_kw={"placeholder": _l("Ex : Demarrage, Croissance, Finition")},
    )
    quantity_kg = DecimalField(
        _l("Quantite donnee (kg)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 25")},
    )
    stock_item_id = SelectField(
        _l("Prelever depuis un stock enregistre (le prix est calcule automatiquement)"),
        coerce=int, validators=[Optional()],
    )
    submit = SubmitField(_l("Enregistrer"))


class EggRecordForm(FlaskForm):
    eggs_collected = IntegerField(
        _l("Oeufs ramasses (casses inclus)"),
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"placeholder": _l("Ex : 250")},
    )
    eggs_broken = IntegerField(
        _l("Dont oeufs casses ou fendus (facultatif)"),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
        render_kw={"placeholder": _l("Ex : 3")},
    )
    submit = SubmitField(_l("Enregistrer"))


class WaterRecordForm(FlaskForm):
    quantity_liters = DecimalField(
        _l("Quantite d'eau donnee (litres)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 80")},
    )
    submit = SubmitField(_l("Enregistrer"))


class MortalityRecordForm(FlaskForm):
    quantity_dead = IntegerField(
        _l("Nombre d'animaux morts aujourd'hui"),
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"placeholder": _l("Ex : 2 (mettre 0 si aucun mort)")},
    )
    cause = StringField(
        _l("Cause probable (si connue)"),
        validators=[Optional()],
        render_kw={"placeholder": _l("Ex : Chaleur, ecrasement, maladie...")},
    )
    submit = SubmitField(_l("Enregistrer"))


class WoodRecordForm(FlaskForm):
    quantity = DecimalField(
        _l("Quantite de bois / litiere ajoutee"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 10")},
    )
    stock_item_id = SelectField(
        _l("Prelever depuis un stock enregistre (le prix est calcule automatiquement)"),
        coerce=int, validators=[Optional()],
    )
    submit = SubmitField(_l("Enregistrer"))


class MedicationRecordForm(FlaskForm):
    medication_name = StringField(
        _l("Nom du medicament / vaccin"),
        validators=[DataRequired()],
        render_kw={"placeholder": _l("Ex : Newcastle, Vitamines, Anticoccidien...")},
    )
    quantity = DecimalField(
        _l("Quantite administree (en ml)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 50 (pour 50 ml, verse dans l'eau de boisson)")},
    )
    notes = TextAreaField(
        _l("Comment l'avez-vous administre ? (facultatif)"),
        validators=[Optional()],
        render_kw={"placeholder": _l("Ex : dans l'eau de boisson, en injection...")},
    )
    stock_item_id = SelectField(
        _l("Prelever depuis un stock enregistre (le prix est calcule automatiquement)"),
        coerce=int, validators=[Optional()],
    )
    submit = SubmitField(_l("Enregistrer"))


class ObservationForm(FlaskForm):
    description = TextAreaField(
        _l("Que remarquez-vous ?"),
        validators=[DataRequired()],
        render_kw={"placeholder": _l("Ex : 3 animaux faibles dans le coin nord de la ferme")},
    )
    severity = SelectField(
        _l("Est-ce urgent ?"),
        choices=[("normal", _l("Non, simple remarque")), ("urgent", _l("Oui, prevenir immediatement le proprietaire"))],
        default="normal",
    )
    photo = FileField(
        _l("Ajouter une photo (facultatif)"),
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], _l("Format d'image non autorise."))],
    )
    submit = SubmitField(_l("Enregistrer"))


class WeightRecordForm(FlaskForm):
    average_weight = DecimalField(
        _l("Poids moyen d'un animal (grammes)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=1,
        render_kw={"placeholder": _l("Ex : 450")},
    )
    sample_size = IntegerField(
        _l("Nombre d'animaux peses"),
        validators=[DataRequired(), NumberRange(min=1)],
        render_kw={"placeholder": _l("Ex : 10")},
    )
    observation = TextAreaField(_l("Remarque (facultatif)"), validators=[Optional()])
    submit = SubmitField(_l("Enregistrer"))


class BatchFinanceForm(FlaskForm):
    labor_cost = DecimalField(_l("Cout main d'oeuvre"), validators=[Optional(), NumberRange(min=0)], places=2, default=0)
    sale_quantity = IntegerField(_l("Quantite vendue"), validators=[Optional(), NumberRange(min=0)])
    sale_unit = SelectField(_l("Unite de vente"), choices=[("kg", _l("Kilogramme")), ("unit", _l("A la piece (par animal)"))], default="kg")
    sale_unit_price = DecimalField(_l("Prix de vente unitaire"), validators=[Optional(), NumberRange(min=0)], places=2)
    submit = SubmitField(_l("Enregistrer"))


class StockItemForm(FlaskForm):
    farm_id = SelectField(_l("Ferme"), coerce=int, validators=[DataRequired()])
    category = SelectField(
        _l("Categorie"),
        choices=[("feed", _l("Aliment")), ("wood", _l("Bois / litiere")), ("medication", _l("Medicament"))],
    )
    name = StringField(
        _l("Nom de l'article"),
        validators=[DataRequired()],
        render_kw={"placeholder": _l("Ex : Aliment demarrage, Copeaux de bois, Vitamines...")},
    )
    unit = StringField(
        _l("Unite de mesure"),
        validators=[DataRequired()],
        default="sac",
        render_kw={"placeholder": _l("Ex : sac, morceau, L (litre), kg...")},
        id="stock-unit",
    )
    quantity_on_hand = DecimalField(
        _l("Quantite actuellement en stock"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 10")},
    )
    min_threshold = DecimalField(
        _l("Seuil d'alerte (stock faible)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 2")},
    )
    unit_price = DecimalField(
        _l("Prix par unite (FCFA)"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 15000")},
    )
    kg_per_unit = DecimalField(
        _l("Poids en kg d'une unite (uniquement pour l'aliment)"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 50 (un sac de 50 kg)")},
        id="stock-kg-per-unit",
    )
    ml_per_unit = DecimalField(
        _l("Volume en ml d'une unite (uniquement pour les medicaments liquides)"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 1000 (1 litre) ou 3000 (bouteille de 3 litres)")},
        id="stock-ml-per-unit",
    )
    submit = SubmitField(_l("Enregistrer"))


class GrowthReferenceForm(FlaskForm):
    name = StringField(_l("Nom de la souche"), validators=[DataRequired()])
    kind = SelectField(
        _l("Type de courbe"),
        choices=[("weight", _l("Poids attendu (croissance)")), ("laying", _l("Ponte attendue (pondeuses)"))],
        default="weight",
    )
    submit = SubmitField(_l("Enregistrer"))


class LayingPointForm(FlaskForm):
    week = IntegerField(_l("Semaine d'age"), validators=[DataRequired(), NumberRange(min=0, max=120)])
    rate = DecimalField(_l("Taux de ponte attendu (%)"), validators=[DataRequired(), NumberRange(min=0, max=100)], places=1)
    submit = SubmitField(_l("Ajouter le point"))


class GrowthReferencePointForm(FlaskForm):
    day_number = IntegerField(_l("Jour"), validators=[DataRequired(), NumberRange(min=0)])
    expected_weight = DecimalField(_l("Poids attendu (grammes)"), validators=[DataRequired(), NumberRange(min=0)], places=1)
    submit = SubmitField(_l("Ajouter le point"))


class SanitaryProgramItemForm(FlaskForm):
    day_number = IntegerField(_l("Jour"), validators=[DataRequired(), NumberRange(min=0)])
    program_type = SelectField(
        _l("Type"),
        choices=[
            ("vaccination", _l("Vaccination")),
            ("traitement", _l("Traitement")),
            ("alimentation", _l("Alimentation")),
            ("complement", _l("Complement (probiotique, anti-stress, litiere...)")),
        ],
        default="vaccination",
    )
    product_name = StringField(_l("Produit"), validators=[DataRequired()])
    notes = TextAreaField(_l("Notes"), validators=[Optional()])
    submit = SubmitField(_l("Ajouter"))


class DailyReportSubmitForm(FlaskForm):
    notes = TextAreaField(_l("Notes"), validators=[Optional()])
    submit = SubmitField(_l("Soumettre le rapport"))


class DailyReportReviewForm(FlaskForm):
    notes = TextAreaField(_l("Commentaire du responsable"), validators=[Optional()])
    submit = SubmitField(_l("Valider le rapport"))

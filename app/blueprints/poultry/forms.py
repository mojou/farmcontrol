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


class FarmForm(FlaskForm):
    name = StringField("Nom de la ferme", validators=[DataRequired()])
    location = StringField("Localisation", validators=[Optional()])
    submit = SubmitField("Enregistrer")


class BatchForm(FlaskForm):
    farm_id = SelectField("Ferme", coerce=int, validators=[DataRequired()])
    code = StringField("Code / nom du lot", validators=[DataRequired()])
    breed = StringField("Souche", validators=[Optional()])
    initial_count = IntegerField("Effectif initial", validators=[DataRequired(), NumberRange(min=1)])
    chick_unit_price = DecimalField("Prix unitaire poussin", validators=[DataRequired(), NumberRange(min=0)], places=2)
    start_date = DateField("Date de mise en place", validators=[DataRequired()])
    growth_reference_id = SelectField("Courbe de reference (souche)", coerce=int, validators=[Optional()])
    submit = SubmitField("Enregistrer")


class BatchCloseForm(FlaskForm):
    end_date = DateField("Date de cloture", validators=[DataRequired()])
    submit = SubmitField("Cloturer le lot")


class FeedRecordForm(FlaskForm):
    feed_type = StringField(
        "Type d'aliment donne",
        validators=[DataRequired()],
        render_kw={"placeholder": "Ex : Demarrage, Croissance, Finition"},
    )
    quantity_kg = DecimalField(
        "Quantite donnee (kg)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 25"},
    )
    unit_price = DecimalField(
        "Prix par kg (FCFA)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 450"},
    )
    stock_item_id = SelectField("Prelever depuis un stock enregistre (facultatif)", coerce=int, validators=[Optional()])
    submit = SubmitField("Enregistrer")


class WaterRecordForm(FlaskForm):
    quantity_liters = DecimalField(
        "Quantite d'eau donnee (litres)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 80"},
    )
    submit = SubmitField("Enregistrer")


class MortalityRecordForm(FlaskForm):
    quantity_dead = IntegerField(
        "Nombre de poulets morts aujourd'hui",
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"placeholder": "Ex : 2 (mettre 0 si aucun mort)"},
    )
    cause = StringField(
        "Cause probable (si connue)",
        validators=[Optional()],
        render_kw={"placeholder": "Ex : Chaleur, ecrasement, maladie..."},
    )
    submit = SubmitField("Enregistrer")


class WoodRecordForm(FlaskForm):
    quantity = DecimalField(
        "Quantite de bois / litiere ajoutee",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 10"},
    )
    unit_price = DecimalField(
        "Prix unitaire (FCFA)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 50"},
    )
    stock_item_id = SelectField("Prelever depuis un stock enregistre (facultatif)", coerce=int, validators=[Optional()])
    submit = SubmitField("Enregistrer")


class MedicationRecordForm(FlaskForm):
    medication_name = StringField(
        "Nom du medicament / vaccin",
        validators=[DataRequired()],
        render_kw={"placeholder": "Ex : Newcastle, Vitamines, Anticoccidien..."},
    )
    quantity = DecimalField(
        "Quantite administree (en ml)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 50 (pour 50 ml, verse dans l'eau de boisson)"},
    )
    unit_price = DecimalField(
        "Prix (FCFA)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 3000"},
    )
    notes = TextAreaField(
        "Comment l'avez-vous administre ? (facultatif)",
        validators=[Optional()],
        render_kw={"placeholder": "Ex : dans l'eau de boisson, en injection..."},
    )
    stock_item_id = SelectField("Prelever depuis un stock enregistre (facultatif)", coerce=int, validators=[Optional()])
    submit = SubmitField("Enregistrer")


class ObservationForm(FlaskForm):
    description = TextAreaField(
        "Que remarquez-vous ?",
        validators=[DataRequired()],
        render_kw={"placeholder": "Ex : 3 poussins faibles dans le coin nord de la ferme"},
    )
    severity = SelectField(
        "Est-ce urgent ?",
        choices=[("normal", "Non, simple remarque"), ("urgent", "Oui, prevenir immediatement le proprietaire")],
        default="normal",
    )
    photo = FileField(
        "Ajouter une photo (facultatif)",
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Format d'image non autorise.")],
    )
    submit = SubmitField("Enregistrer")


class WeightRecordForm(FlaskForm):
    average_weight = DecimalField(
        "Poids moyen d'un poulet (grammes)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=1,
        render_kw={"placeholder": "Ex : 450"},
    )
    sample_size = IntegerField(
        "Nombre de poulets peses",
        validators=[DataRequired(), NumberRange(min=1)],
        render_kw={"placeholder": "Ex : 10"},
    )
    observation = TextAreaField("Remarque (facultatif)", validators=[Optional()])
    submit = SubmitField("Enregistrer")


class BatchFinanceForm(FlaskForm):
    labor_cost = DecimalField("Cout main d'oeuvre", validators=[Optional(), NumberRange(min=0)], places=2, default=0)
    sale_quantity = IntegerField("Quantite vendue", validators=[Optional(), NumberRange(min=0)])
    sale_unit = SelectField("Unite de vente", choices=[("kg", "Kilogramme"), ("unit", "Unite (par sujet)")], default="kg")
    sale_unit_price = DecimalField("Prix de vente unitaire", validators=[Optional(), NumberRange(min=0)], places=2)
    submit = SubmitField("Enregistrer la rentabilite")


class StockItemForm(FlaskForm):
    farm_id = SelectField("Ferme", coerce=int, validators=[DataRequired()])
    category = SelectField(
        "Categorie",
        choices=[("feed", "Aliment"), ("wood", "Bois / litiere"), ("medication", "Medicament")],
    )
    name = StringField(
        "Nom de l'article",
        validators=[DataRequired()],
        render_kw={"placeholder": "Ex : Aliment demarrage, Copeaux de bois, Vitamines..."},
    )
    unit = StringField(
        "Unite de mesure",
        validators=[DataRequired()],
        default="sac",
        render_kw={"placeholder": "Ex : sac, morceau, L (litre), kg..."},
        id="stock-unit",
    )
    quantity_on_hand = DecimalField(
        "Quantite actuellement en stock",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 10"},
    )
    min_threshold = DecimalField(
        "Seuil d'alerte (stock faible)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 2"},
    )
    unit_price = DecimalField(
        "Prix par unite (FCFA)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 15000"},
    )
    kg_per_unit = DecimalField(
        "Poids en kg d'une unite (uniquement pour l'aliment)",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 50 (un sac de 50 kg)"},
        id="stock-kg-per-unit",
    )
    ml_per_unit = DecimalField(
        "Volume en ml d'une unite (uniquement pour les medicaments liquides)",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 1000 (1 litre) ou 3000 (bouteille de 3 litres)"},
        id="stock-ml-per-unit",
    )
    submit = SubmitField("Enregistrer")


class GrowthReferenceForm(FlaskForm):
    name = StringField("Nom de la souche", validators=[DataRequired()])
    submit = SubmitField("Enregistrer")


class GrowthReferencePointForm(FlaskForm):
    day_number = IntegerField("Jour", validators=[DataRequired(), NumberRange(min=0)])
    expected_weight = DecimalField("Poids attendu (grammes)", validators=[DataRequired(), NumberRange(min=0)], places=1)
    submit = SubmitField("Ajouter le point")


class SanitaryProgramItemForm(FlaskForm):
    day_number = IntegerField("Jour", validators=[DataRequired(), NumberRange(min=0)])
    program_type = SelectField(
        "Type",
        choices=[
            ("vaccination", "Vaccination"),
            ("traitement", "Traitement"),
            ("alimentation", "Alimentation"),
            ("complement", "Complement (probiotique, anti-stress, litiere...)"),
        ],
        default="vaccination",
    )
    product_name = StringField("Produit", validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Ajouter")


class DailyReportSubmitForm(FlaskForm):
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Soumettre le rapport")


class DailyReportReviewForm(FlaskForm):
    notes = TextAreaField("Commentaire du responsable", validators=[Optional()])
    submit = SubmitField("Valider le rapport")

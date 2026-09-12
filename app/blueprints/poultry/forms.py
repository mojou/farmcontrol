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
    stock_item_id = SelectField("Article de stock (optionnel)", coerce=int, validators=[Optional()])
    feed_type = StringField("Type d'aliment", validators=[DataRequired()])
    quantity_kg = DecimalField("Quantite (kg)", validators=[DataRequired(), NumberRange(min=0)], places=2)
    unit_price = DecimalField("Prix unitaire (par kg)", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Enregistrer")


class WaterRecordForm(FlaskForm):
    quantity_liters = DecimalField("Quantite d'eau (litres)", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Enregistrer")


class MortalityRecordForm(FlaskForm):
    quantity_dead = IntegerField("Nombre de morts", validators=[DataRequired(), NumberRange(min=0)])
    cause = StringField("Cause probable", validators=[Optional()])
    submit = SubmitField("Enregistrer")


class WoodRecordForm(FlaskForm):
    stock_item_id = SelectField("Article de stock (optionnel)", coerce=int, validators=[Optional()])
    quantity = DecimalField("Quantite", validators=[DataRequired(), NumberRange(min=0)], places=2)
    unit_price = DecimalField("Prix unitaire", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Enregistrer")


class MedicationRecordForm(FlaskForm):
    stock_item_id = SelectField("Article de stock (optionnel)", coerce=int, validators=[Optional()])
    medication_name = StringField("Medicament", validators=[DataRequired()])
    quantity = DecimalField("Quantite", validators=[DataRequired(), NumberRange(min=0)], places=2)
    unit_price = DecimalField("Prix unitaire", validators=[DataRequired(), NumberRange(min=0)], places=2)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Enregistrer")


class ObservationForm(FlaskForm):
    description = TextAreaField("Description", validators=[DataRequired()])
    severity = SelectField(
        "Gravite", choices=[("normal", "Normale"), ("urgent", "Urgente")], default="normal"
    )
    photo = FileField(
        "Photo (optionnelle)",
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Format d'image non autorise.")],
    )
    submit = SubmitField("Enregistrer")


class WeightRecordForm(FlaskForm):
    average_weight = DecimalField("Poids moyen (grammes)", validators=[DataRequired(), NumberRange(min=0)], places=1)
    sample_size = IntegerField("Nombre de sujets peses", validators=[DataRequired(), NumberRange(min=1)])
    observation = TextAreaField("Observation", validators=[Optional()])
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
    name = StringField("Nom de l'article", validators=[DataRequired()])
    unit = StringField("Unite", validators=[DataRequired()], default="kg")
    quantity_on_hand = DecimalField("Quantite en stock", validators=[DataRequired(), NumberRange(min=0)], places=2)
    min_threshold = DecimalField("Seuil d'alerte", validators=[DataRequired(), NumberRange(min=0)], places=2)
    unit_price = DecimalField("Prix unitaire", validators=[DataRequired(), NumberRange(min=0)], places=2)
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

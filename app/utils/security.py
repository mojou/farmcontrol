"""Politique de mot de passe et aides de securite (paragraphe 8)."""
import re
import secrets
import unicodedata

from flask import current_app


def slugify(value: str) -> str:
    """Convertit un nom libre en identifiant (slug) URL-safe et minuscule."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "exploitation"


def generate_unique_slug(base_name: str, exists_fn) -> str:
    """Genere un slug unique a partir d'un nom libre, en ajoutant si besoin un
    court suffixe aleatoire tant que `exists_fn(slug)` renvoie True.
    """
    base = slugify(base_name)
    slug = base
    while exists_fn(slug):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


def validate_password_policy(raw_password: str) -> list:
    """Retourne la liste des erreurs de politique de mot de passe (vide = OK).

    Regles minimales V1 : longueur minimale configurable + au moins une
    majuscule, une minuscule et un chiffre.
    """
    errors = []
    min_length = current_app.config.get("PASSWORD_MIN_LENGTH", 10)

    if len(raw_password) < min_length:
        errors.append(f"Le mot de passe doit contenir au moins {min_length} caracteres.")
    if not re.search(r"[a-z]", raw_password):
        errors.append("Le mot de passe doit contenir au moins une lettre minuscule.")
    if not re.search(r"[A-Z]", raw_password):
        errors.append("Le mot de passe doit contenir au moins une lettre majuscule.")
    if not re.search(r"\d", raw_password):
        errors.append("Le mot de passe doit contenir au moins un chiffre.")

    return errors

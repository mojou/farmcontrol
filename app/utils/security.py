"""Politique de mot de passe et aides de securite (paragraphe 8)."""
import re

from flask import current_app


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

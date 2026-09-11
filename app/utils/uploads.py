"""Gestion des photos jointes aux observations (paragraphe 5).

Stockage local dans /uploads pour la V1 (migration vers un stockage cloud
possible plus tard sans changer le modele : seul photo_path est stocke en
base, relatif au dossier UPLOAD_FOLDER).
"""
import os
import uuid

from flask import current_app
from PIL import Image
from werkzeug.utils import secure_filename

MAX_DIMENSION = 1600  # px, redimensionnement automatique cote serveur


def allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_observation_photo(file_storage, tenant_id: int) -> str:
    """Enregistre la photo sur disque, la redimensionne si besoin et retourne
    le chemin relatif (a stocker dans Observation.photo_path).
    """
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_image(file_storage.filename):
        raise ValueError("Format d'image non autorise. Formats acceptes : png, jpg, jpeg, webp.")

    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    relative_dir = os.path.join("observations", str(tenant_id))
    absolute_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    absolute_path = os.path.join(absolute_dir, unique_name)
    file_storage.save(absolute_path)

    try:
        with Image.open(absolute_path) as image:
            image = image.convert("RGB") if image.mode not in ("RGB", "RGBA") else image
            if max(image.size) > MAX_DIMENSION:
                image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
            image.save(absolute_path)
    except Exception:
        current_app.logger.warning("Redimensionnement de l'image impossible pour %s", absolute_path)

    return os.path.join(relative_dir, unique_name).replace("\\", "/")


def delete_photo(relative_path: str):
    if not relative_path:
        return
    absolute_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    if os.path.exists(absolute_path):
        os.remove(absolute_path)

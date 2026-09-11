"""Instances des extensions Flask, creees ici pour eviter les imports circulaires."""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect

# expire_on_commit=False : evite qu'un objet ne redemande une lecture en base
# juste apres un commit(). Important ici car la RLS PostgreSQL (couche 2,
# paragraphe 7.2) peut legitimement bloquer cette re-lecture si le contexte
# tenant/bypass a change entre le commit et l'acces suivant a l'attribut
# (ex. : commit fait sous tenant_bypass(), acces a l'attribut juste apres,
# une fois le bypass referme) - ce qui provoquerait une ObjectDeletedError
# trompeuse au lieu d'un simple acces a une valeur deja connue en memoire.
db = SQLAlchemy(session_options={"expire_on_commit": False})
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Veuillez vous connecter pour acceder a cette page."
login_manager.login_message_category = "warning"

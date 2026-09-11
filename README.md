# Farm Control - Plateforme multitenant de gestion d'elevage

Module initial : **Poulets de chair**. Backend Python Flask + PostgreSQL, conforme au
cahier des charges technique v1.1.

## Fonctionnalites principales

- Multitenant avec isolation stricte des donnees, protegee a deux niveaux :
  filtrage applicatif systematique par `tenant_id` (SQLAlchemy) **et** Row Level
  Security PostgreSQL (voir `scripts/enable_rls.sql`).
- Roles : super administrateur, proprietaire, responsable, travailleur.
- Suivi quotidien : aliment, eau, mortalite, bois/litiere, medicaments,
  observations (avec photo), pesees.
- Performance zootechnique : indice de consommation (FCR) calcule automatiquement,
  courbe de croissance comparee a une reference parametrable par souche.
- Rentabilite par lot (charges vs revenu, resultat net, cout de revient au kg).
- Alertes avec notification email automatique pour les priorites urgente/importante
  (Flask-Mail), desactivables par utilisateur.
- Dashboard avec courbes Chart.js (mortalite cumulee, consommation d'aliment cumulee).
- Export PDF du rapport de lot (WeasyPrint).
- Journal d'audit (creation/modification/suppression, avant/apres).
- Authentification renforcee : politique de mot de passe, verrouillage apres
  echecs, reinitialisation par email.
- Workflow de validation des rapports journaliers (brouillon / soumis / valide).
- Mode demo (tenant d'essai preconfigure).

## Architecture

```
app/
  config.py              Configuration (variables d'environnement)
  extensions.py           Instances Flask (db, migrate, login, mail, csrf)
  decorators.py           Controle d'acces par role
  cli.py                  Commandes Flask (create-superadmin, seed-demo)
  models/
    core.py               Tenant, User, AuditLog, PasswordResetToken
    poultry.py             Farm, Batch, BatchDay, enregistrements quotidiens,
                            finance, alertes, stock, references de croissance
  blueprints/
    auth/                  Connexion, mot de passe oublie, changement de mdp
    core/                  Dashboards, administration, profil, alertes
    poultry/                Fermes, lots, saisie quotidienne, rapports, stock
  utils/
    tenant.py               Contexte tenant courant (couche 1 de securite)
    rls.py                   Synchronisation des variables de session RLS
    zootechnie.py            Calculs FCR, series graphiques, rentabilite
    alerts.py                Creation d'alertes + envoi email
    emailing.py              Templates email
    uploads.py               Photos d'observations
    pdf.py                   Export PDF (WeasyPrint)
    security.py              Politique de mot de passe
    audit.py                 Journal d'audit
  templates/                Bootstrap 5 + Bootstrap Icons, sans emoji
  static/                   CSS et JS (Chart.js charge en CDN)
scripts/
  enable_rls.sql            Activation Row Level Security PostgreSQL
migrations/                 Migrations Flask-Migrate / Alembic
```

L'architecture Core/Module permet d'ajouter plus tard d'autres types d'elevage
(porcs, pisciculture...) sans toucher au coeur de la plateforme (tenants,
utilisateurs, audit, authentification).

## Installation

### 1. Prerequis systeme

- Python 3.11+ (teste avec 3.14)
- PostgreSQL 14+
- Windows : le runtime **GTK3 64 bits** est necessaire pour l'export PDF
  (WeasyPrint s'appuie sur Pango/Cairo). Telecharger et installer :
  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
  (installation silencieuse : `gtk3-runtime-*.exe /S /D=C:\GTK3-Runtime64`,
  puis ajouter `C:\GTK3-Runtime64\bin` au PATH systeme). Sur Linux/macOS,
  suivre https://doc.courtbouillon.org/weasyprint/stable/first_steps.html.

### 2. Environnement Python

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 3. Configuration

```bash
copy .env.example .env
```

Renseigner au minimum `SECRET_KEY`, `DATABASE_URL` et les parametres SMTP
(`MAIL_*`) dans `.env`.

### 4. Base de donnees PostgreSQL

Creer le role et la base (a executer avec un utilisateur superuser PostgreSQL) :

```sql
CREATE ROLE farmcontrol WITH LOGIN PASSWORD 'un-mot-de-passe-fort';
CREATE DATABASE farmcontrol OWNER farmcontrol;
```

Puis appliquer les migrations et activer la Row Level Security :

```bash
flask db upgrade
psql -U postgres -d farmcontrol -f scripts/enable_rls.sql
```

Important : le role applicatif (`farmcontrol`) ne doit pas avoir l'attribut
`BYPASSRLS`, et ne doit pas non plus etre proprietaire des tables si l'on
veut que `FORCE ROW LEVEL SECURITY` s'applique aussi a lui (voir le script
pour le detail). Executez `scripts/enable_rls.sql` avec un role superuser
distinct du role applicatif.

### 5. Comptes initiaux

```bash
flask create-superadmin --email admin@farmcontrol.app --password ...
flask seed-demo   # optionnel : cree le tenant de demonstration (paragraphe 10)
```

### 6. Lancer l'application

```bash
flask run
# ou en production :
gunicorn wsgi:app
```

## Migrations (Flask-Migrate)

```bash
flask db init        # une seule fois
flask db migrate -m "description du changement"
flask db upgrade
```

Apres chaque migration ajoutant une nouvelle table sensible, mettre a jour
`scripts/enable_rls.sql` et le reappliquer.

## Notes de conception importantes

- **Isolation multitenant a deux niveaux** (paragraphe 7) : le filtre
  applicatif (`app/models/__init__.py`, `register_tenant_filter`) s'appuie
  sur un evenement SQLAlchemy `do_orm_execute` qui injecte automatiquement
  `WHERE tenant_id = <tenant courant>` sur toute requete portant sur un
  modele heritant de `TenantMixin`. En absence de tenant courant, aucune
  ligne n'est retournee (deny by default). La RLS PostgreSQL (`scripts/
  enable_rls.sql`) est le filet de securite au niveau base de donnees.
- **Connexion partagee** : la page de connexion est commune a tous les
  clients (email suppose unique sur l'ensemble de la plateforme). Un
  utilisateur cree par un proprietaire est donc rejete si l'email existe
  deja pour un autre tenant.
- **FCR** (paragraphe 1.2) : `aliment total consomme (kg) / poids total
  produit (kg)`, le poids produit etant estime a partir de la derniere
  pesee x effectif courant (ou des donnees de vente si le lot est cloture).
- **WeasyPrint** : l'import de la librairie est differe au moment de
  l'export PDF (et non au demarrage de l'application) pour eviter qu'une
  installation GTK manquante ne bloque tout le serveur.
- **Photos d'observations** : stockees localement dans `uploads/`, servies
  via une route authentifiee qui verifie que le tenant du fichier
  correspond au tenant de l'utilisateur courant.

## Hors perimetre V1 (paragraphe 14)

Application mobile native, intelligence artificielle, paiement en ligne,
notifications SMS/WhatsApp, mode hors connexion complet, comptabilite
complete, authentification a deux facteurs, autres types d'elevage.

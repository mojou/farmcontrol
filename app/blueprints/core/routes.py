from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import safe_join
from werkzeug.exceptions import NotFound
from flask import send_from_directory

from app.blueprints.core import core_bp
from app.blueprints.core.forms import ProfileForm, TenantForm, UserForm
from app.decorators import owner_required, super_admin_required
from app.extensions import db
from app.models import utcnow
from app.models.billing import SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_TRIALING, Plan, Subscription
from app.models.core import ROLE_OWNER, Tenant, User
from app.models.poultry import Alert, Batch, Farm
from app.utils.audit import log_action
from app.utils.plans import ensure_plans_seeded, get_current_plan
from app.utils.security import validate_password_policy
from app.utils.tenant import tenant_bypass
from app.utils.uploads import delete_photo, save_avatar_photo
from app.utils.zootechnie import compute_fcr


@core_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_super_admin():
            return redirect(url_for("core.admin_dashboard"))
        return redirect(url_for("core.dashboard"))
    return render_template("home.html")


# --------------------------------------------------------------------------
# Tableaux de bord par role
# --------------------------------------------------------------------------

@core_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_super_admin():
        return redirect(url_for("core.admin_dashboard"))

    farms_query = Farm.query
    if current_user.farm_id:
        farms_query = farms_query.filter_by(id=current_user.farm_id)
    farms = farms_query.order_by(Farm.name).all()
    farm_ids = [f.id for f in farms]

    active_batches = (
        Batch.query.filter(Batch.farm_id.in_(farm_ids), Batch.status == "active").all()
        if farm_ids
        else []
    )

    selected_batch_id = request.args.get("batch_id", type=int)
    selected_batch = None
    if active_batches:
        selected_batch = next((b for b in active_batches if b.id == selected_batch_id), active_batches[0])

    unread_alerts = (
        Alert.query.filter_by(is_read=False)
        .order_by(Alert.priority.desc(), Alert.created_at.desc())
        .limit(10)
        .all()
    )

    pending_reports = []
    if current_user.has_role("owner", "manager"):
        from app.models.poultry import DailyReport, REPORT_STATUS_SUBMITTED

        pending_reports = (
            DailyReport.query.filter_by(status=REPORT_STATUS_SUBMITTED)
            .order_by(DailyReport.submitted_at.desc())
            .limit(10)
            .all()
        )

    if current_user.is_worker():
        template = "core/dashboard_worker.html"
    elif current_user.is_manager():
        template = "core/dashboard_manager.html"
    else:
        template = "core/dashboard_owner.html"

    selected_batch_fcr = compute_fcr(selected_batch) if selected_batch else None

    return render_template(
        template,
        farms=farms,
        active_batches=active_batches,
        selected_batch=selected_batch,
        selected_batch_fcr=selected_batch_fcr,
        unread_alerts=unread_alerts,
        pending_reports=pending_reports,
    )


@core_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        new_email = form.email.data.strip().lower()
        if new_email != current_user.email:
            with tenant_bypass():
                existing = User.query.filter(
                    User.email == new_email, User.id != current_user.id
                ).first()
            if existing:
                flash("Un utilisateur existe deja avec cet email.", "danger")
                return render_template("core/profile.html", form=form)
            current_user.email = new_email

        if form.avatar.data:
            try:
                new_avatar = save_avatar_photo(form.avatar.data, current_user.tenant_id or 0)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("core/profile.html", form=form)
            delete_photo(current_user.avatar_path)
            current_user.avatar_path = new_avatar

        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email_notifications_enabled = form.email_notifications_enabled.data
        log_action("update", "users", current_user.id, {"action": "profile_update"})
        db.session.commit()
        flash("Profil mis a jour.", "success")
        return redirect(url_for("core.profile"))
    return render_template("core/profile.html", form=form)


@core_bp.route("/profile/avatar/remove", methods=["POST"])
@login_required
def profile_avatar_remove():
    delete_photo(current_user.avatar_path)
    current_user.avatar_path = None
    db.session.commit()
    flash("Photo de profil supprimee.", "success")
    return redirect(url_for("core.profile"))


# --------------------------------------------------------------------------
# Alertes
# --------------------------------------------------------------------------

@core_bp.route("/alerts")
@login_required
def alerts_list():
    page = request.args.get("page", 1, type=int)
    pagination = Alert.query.order_by(Alert.created_at.desc()).paginate(page=page, per_page=20)
    return render_template("core/alerts.html", pagination=pagination)


@core_bp.route("/alerts/<int:alert_id>/read", methods=["POST"])
@login_required
def mark_alert_read(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("core.alerts_list"))


# --------------------------------------------------------------------------
# Gestion des utilisateurs (proprietaire)
# --------------------------------------------------------------------------

@core_bp.route("/users")
@owner_required
def users_list():
    users = User.query.order_by(User.role, User.last_name).all()
    return render_template("core/users_list.html", users=users)


@core_bp.route("/users/new", methods=["GET", "POST"])
@owner_required
def user_new():
    plan = get_current_plan(current_user.tenant)
    if plan.max_users is not None and User.query.count() >= plan.max_users:
        flash(
            f"Votre plan {plan.name} est limite a {plan.max_users} utilisateur(s). "
            "Passez a un plan superieur pour en ajouter davantage.",
            "warning",
        )
        return redirect(url_for("billing.pricing"))

    form = UserForm()
    form.farm_id.choices = [(0, "Toutes les fermes")] + [
        (f.id, f.name) for f in Farm.query.order_by(Farm.name).all()
    ]

    if form.validate_on_submit():
        errors = validate_password_policy(form.password.data)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("core/user_form.html", form=form)

        with tenant_bypass():
            existing = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing:
            flash("Un utilisateur existe deja avec cet email.", "danger")
            return render_template("core/user_form.html", form=form)

        user = User(
            tenant_id=current_user.tenant_id,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data.strip().lower(),
            role=form.role.data,
            farm_id=form.farm_id.data or None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_action("create", "users", user.id, {"email": user.email, "role": user.role})
        db.session.commit()
        flash(f"Utilisateur {user.full_name} cree avec succes.", "success")
        return redirect(url_for("core.users_list"))

    return render_template("core/user_form.html", form=form)


@core_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@owner_required
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_OWNER:
        flash("Impossible de desactiver un compte proprietaire.", "danger")
        return redirect(url_for("core.users_list"))
    user.is_active = not user.is_active
    log_action("update", "users", user.id, {"is_active": user.is_active})
    db.session.commit()
    flash("Statut de l'utilisateur mis a jour.", "success")
    return redirect(url_for("core.users_list"))


# --------------------------------------------------------------------------
# Administration de la plateforme (super_admin)
# --------------------------------------------------------------------------

@core_bp.route("/admin")
@super_admin_required
def admin_dashboard():
    with tenant_bypass():
        tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    return render_template("core/admin_dashboard.html", tenants=tenants)


@core_bp.route("/admin/tenants/new", methods=["GET", "POST"])
@super_admin_required
def tenant_new():
    form = TenantForm()
    if form.validate_on_submit():
        with tenant_bypass():
            slug_taken = Tenant.query.filter_by(slug=form.slug.data.strip().lower()).first()
            email_taken = User.query.filter_by(email=form.owner_email.data.strip().lower()).first()

        if slug_taken:
            flash("Cet identifiant (slug) est deja utilise.", "danger")
            return render_template("core/tenant_form.html", form=form)
        if email_taken:
            flash("Un utilisateur existe deja avec cet email.", "danger")
            return render_template("core/tenant_form.html", form=form)

        errors = validate_password_policy(form.owner_password.data)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("core/tenant_form.html", form=form)

        with tenant_bypass():
            tenant = Tenant(
                name=form.name.data,
                slug=form.slug.data.strip().lower(),
                plan=form.plan.data,
                is_demo=form.is_demo.data,
            )
            db.session.add(tenant)
            db.session.flush()

            owner = User(
                tenant_id=tenant.id,
                first_name=form.owner_first_name.data,
                last_name=form.owner_last_name.data,
                email=form.owner_email.data.strip().lower(),
                role=ROLE_OWNER,
            )
            owner.set_password(form.owner_password.data)
            db.session.add(owner)
            db.session.flush()

            ensure_plans_seeded()
            selected_plan = Plan.query.filter_by(code=form.plan.data).first()
            db.session.add(
                Subscription(
                    tenant_id=tenant.id,
                    plan_id=selected_plan.id,
                    status=SUBSCRIPTION_STATUS_ACTIVE if selected_plan.price_xaf > 0 else SUBSCRIPTION_STATUS_TRIALING,
                    current_period_start=utcnow(),
                    current_period_end=None,
                )
            )

            log_action("create", "tenants", tenant.id, {"name": tenant.name, "slug": tenant.slug})
            db.session.commit()

        flash(f"Client {tenant.name} cree avec succes.", "success")
        return redirect(url_for("core.admin_dashboard"))

    return render_template("core/tenant_form.html", form=form)


@core_bp.route("/admin/tenants/<int:tenant_id>/toggle", methods=["POST"])
@super_admin_required
def tenant_toggle(tenant_id):
    with tenant_bypass():
        tenant = Tenant.query.get_or_404(tenant_id)
        tenant.is_active = not tenant.is_active
        log_action("update", "tenants", tenant.id, {"is_active": tenant.is_active})
        db.session.commit()
    flash("Statut du client mis a jour.", "success")
    return redirect(url_for("core.admin_dashboard"))


# --------------------------------------------------------------------------
# Diffusion des fichiers uploades (photos d'observations, paragraphe 5)
# --------------------------------------------------------------------------

@core_bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    # Le chemin est de la forme "observations/<tenant_id>/<fichier>" : on
    # verifie que le tenant du fichier correspond bien au tenant courant
    # avant de le servir (isolation multitenant sur les fichiers uploades).
    parts = filename.split("/")
    if len(parts) < 2 or not parts[1].isdigit():
        abort(404)
    file_tenant_id = int(parts[1])
    if not current_user.is_super_admin() and file_tenant_id != current_user.tenant_id:
        abort(403)

    safe_path = safe_join(current_app.config["UPLOAD_FOLDER"], filename)
    if safe_path is None:
        raise NotFound()

    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

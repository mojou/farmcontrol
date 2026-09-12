"""Messagerie interne (paragraphe communication) entre les utilisateurs
d'un meme tenant - typiquement entre un travailleur et son proprietaire/
responsable, mais ouverte a tous les roles d'un meme tenant.
"""
from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.messaging import messaging_bp
from app.blueprints.messaging.forms import ComposeMessageForm, ReplyMessageForm
from app.extensions import db
from app.models import utcnow
from app.models.core import Message, User


def _recipient_choices():
    users = (
        User.query.filter(User.id != current_user.id, User.is_active.is_(True))
        .order_by(User.role, User.last_name)
        .all()
    )
    return [(u.id, f"{u.full_name} ({u.role_label})") for u in users]


@messaging_bp.route("/")
@login_required
def inbox():
    messages = (
        Message.query.filter_by(recipient_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("messaging/inbox.html", messages=messages)


@messaging_bp.route("/envoyes")
@login_required
def sent():
    messages = (
        Message.query.filter_by(sender_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("messaging/sent.html", messages=messages)


@messaging_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def compose():
    form = ComposeMessageForm()
    form.recipient_id.choices = _recipient_choices()

    if not form.recipient_id.choices:
        flash("Aucun autre utilisateur a qui envoyer un message pour le moment.", "warning")
        return redirect(url_for("messaging.inbox"))

    if form.validate_on_submit():
        message = Message(
            tenant_id=current_user.tenant_id,
            sender_id=current_user.id,
            recipient_id=form.recipient_id.data,
            subject=form.subject.data,
            body=form.body.data,
        )
        db.session.add(message)
        db.session.commit()
        flash("Message envoye.", "success")
        return redirect(url_for("messaging.sent"))

    return render_template("messaging/compose.html", form=form)


@messaging_bp.route("/<int:message_id>")
@login_required
def view(message_id):
    message = Message.query.get_or_404(message_id)
    if current_user.id not in (message.sender_id, message.recipient_id):
        abort(403)

    if message.recipient_id == current_user.id and not message.is_read:
        message.is_read = True
        message.read_at = utcnow()
        db.session.commit()

    reply_form = ReplyMessageForm()
    can_reply = message.recipient_id == current_user.id and message.sender_id is not None
    return render_template("messaging/view.html", message=message, reply_form=reply_form, can_reply=can_reply)


@messaging_bp.route("/<int:message_id>/repondre", methods=["POST"])
@login_required
def reply(message_id):
    original = Message.query.get_or_404(message_id)
    if current_user.id != original.recipient_id or original.sender_id is None:
        abort(403)

    form = ReplyMessageForm()
    if form.validate_on_submit():
        subject = original.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        reply_message = Message(
            tenant_id=current_user.tenant_id,
            sender_id=current_user.id,
            recipient_id=original.sender_id,
            subject=subject,
            body=form.body.data,
        )
        db.session.add(reply_message)
        db.session.commit()
        flash("Reponse envoyee.", "success")
    else:
        flash("Impossible d'envoyer la reponse (message vide ?).", "danger")

    return redirect(url_for("messaging.view", message_id=message_id))

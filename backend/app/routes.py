from functools import wraps
from datetime import datetime
from io import BytesIO
import os
import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)

from .extensions import db
from .models import Guest, Memory, Portrait, RSVPStatus, User, Wedding
from werkzeug.utils import secure_filename

web = Blueprint("web", __name__)


def admin_required(view):
    @wraps(view)
    @jwt_required()
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)
    return wrapped


def current_wedding():
    user = db.session.get(User, int(get_jwt_identity()))
    return Wedding.query.filter_by(organization_id=user.organization_id).first()


@web.get("/")
def home():
    return redirect(url_for("web.dashboard"))


@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"].lower().strip()).first()
        if user and user.check_password(request.form["password"]):
            response = redirect(url_for("web.dashboard"))
            set_access_cookies(response, create_access_token(identity=str(user.id)))
            return response
        flash("Correo o contraseña incorrectos.", "danger")
    return render_template("login.html")


@web.get("/logout")
def logout():
    response = redirect(url_for("web.login"))
    unset_jwt_cookies(response)
    return response


@web.get("/dashboard")
@admin_required
def dashboard():
    wedding = current_wedding()
    guests = Guest.query.filter_by(wedding_id=wedding.id)
    
    # Conteo total incluyendo acompañantes
    total_con_acompanantes = 0
    confirmed_con_acompanantes = 0
    pending_con_acompanantes = 0
    declined_con_acompanantes = 0
    
    for guest in guests:
        total_personas = 1 + (guest.companions or 0)
        total_con_acompanantes += total_personas
        
        if guest.rsvp_status == RSVPStatus.CONFIRMED:
            confirmed_con_acompanantes += total_personas
        elif guest.rsvp_status == RSVPStatus.PENDING:
            pending_con_acompanantes += total_personas
        elif guest.rsvp_status == RSVPStatus.DECLINED:
            declined_con_acompanantes += total_personas
    
    stats = {
        "total": guests.count(),
        "total_personas": total_con_acompanantes,
        "confirmed": guests.filter_by(rsvp_status=RSVPStatus.CONFIRMED).count(),
        "confirmed_personas": confirmed_con_acompanantes,
        "pending": guests.filter_by(rsvp_status=RSVPStatus.PENDING).count(),
        "pending_personas": pending_con_acompanantes,
        "declined": guests.filter_by(rsvp_status=RSVPStatus.DECLINED).count(),
        "declined_personas": declined_con_acompanantes,
        "tables": db.session.query(Guest.table_number).filter_by(wedding_id=wedding.id).filter(Guest.table_number.isnot(None)).distinct().count(),
    }
    return render_template("dashboard.html", wedding=wedding, stats=stats)


@web.get("/guests")
@admin_required
def guests():
    wedding = current_wedding()
    query = Guest.query.filter_by(wedding_id=wedding.id)
    term = request.args.get("q", "").strip()
    if term:
        query = query.filter((Guest.first_name.ilike(f"%{term}%")) | (Guest.last_name.ilike(f"%{term}%")))
    return render_template("guests.html", guests=query.order_by(Guest.first_name).all(), term=term)


@web.route("/guests/new", methods=["GET", "POST"])
@admin_required
def new_guest():
    wedding = current_wedding()
    if request.method == "POST":
        guest = Guest(
            wedding_id=wedding.id,
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            companions=max(0, int(request.form.get("companions", 0) or 0)),
            table_number=request.form.get("table_number", "").strip() or None,
            rsvp_status=RSVPStatus(request.form.get("rsvp_status", RSVPStatus.PENDING.value)),
            dietary_notes=request.form.get("dietary_notes", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(guest)
        db.session.commit()
        flash("Invitado agregado correctamente.", "success")
        return redirect(url_for("web.guests"))
    return render_template("guest_form.html", guest=None, statuses=RSVPStatus)


@web.route("/guests/<int:guest_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_guest(guest_id):
    wedding = current_wedding()
    guest = Guest.query.filter_by(id=guest_id, wedding_id=wedding.id).first_or_404()
    if request.method == "POST":
        for field in ("first_name", "last_name", "phone", "email", "table_number", "dietary_notes", "notes"):
            setattr(guest, field, request.form.get(field, "").strip() or None)
        guest.companions = max(0, int(request.form.get("companions", 0) or 0))
        guest.rsvp_status = RSVPStatus(request.form["rsvp_status"])
        db.session.commit()
        flash("Invitado actualizado.", "success")
        return redirect(url_for("web.guests"))
    return render_template("guest_form.html", guest=guest, statuses=RSVPStatus)


@web.post("/guests/<int:guest_id>/delete")
@admin_required
def delete_guest(guest_id):
    wedding = current_wedding()
    guest = Guest.query.filter_by(id=guest_id, wedding_id=wedding.id).first_or_404()
    db.session.delete(guest)
    db.session.commit()
    flash("Invitado eliminado.", "success")
    return redirect(url_for("web.guests"))


@web.get("/invitations")
@admin_required
def invitations():
    wedding = current_wedding()
    return render_template("invitations.html", guests=Guest.query.filter_by(wedding_id=wedding.id).order_by(Guest.first_name).all())


@web.post("/invitations/<int:guest_id>/generate")
@admin_required
def generate_invitation(guest_id):
    wedding = current_wedding()
    guest = Guest.query.filter_by(id=guest_id, wedding_id=wedding.id).first_or_404()
    guest.ensure_invitation_code()
    db.session.commit()
    flash(f"Invitación de {guest.full_name} creada.", "success")
    return redirect(url_for("web.invitations"))


@web.get("/invitations/<int:guest_id>/qr")
@admin_required
def invitation_qr(guest_id):
    import qrcode
    wedding = current_wedding()
    guest = Guest.query.filter_by(id=guest_id, wedding_id=wedding.id).first_or_404()
    guest.ensure_invitation_code()
    db.session.commit()
    image = qrcode.make(url_for("web.public_invitation", code=guest.invitation_code, _external=True))
    output = BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", as_attachment=True, download_name=f"invitacion-{guest.invitation_code}.png")


@web.route("/invitacion/<code>", methods=["GET", "POST"])
def public_invitation(code):
    guest = Guest.query.filter_by(invitation_code=code.upper()).first_or_404()
    
    # Fecha fija: 14 de noviembre de 2026 a las 5:00 PM
    event_datetime = datetime(2026, 11, 14, 17, 0, 0)
    
    if request.method == "POST":
        response = request.form.get("response")
        if response in (RSVPStatus.CONFIRMED.value, RSVPStatus.DECLINED.value):
            guest.rsvp_status = RSVPStatus(response)
            guest.rsvp_at = datetime.utcnow()
            db.session.commit()
            flash("¡Gracias! Tu respuesta fue registrada.", "success")
            return redirect(url_for("web.public_invitation", code=guest.invitation_code))
        flash("Selecciona una respuesta válida.", "danger")
    
    memories = Memory.query.filter_by(wedding_id=guest.wedding_id).order_by(Memory.created_at.desc()).limit(24).all()
    return render_template(
        "public_invitation.html",
        guest=guest,
        wedding=guest.wedding,
        memories=memories,
        portraits=guest.wedding.portraits,
        event_datetime=event_datetime
    )


ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEOS = {"mp4", "mov", "webm"}


def save_upload(file, allowed_extensions):
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in allowed_extensions:
        return None
    filename = f"{secrets.token_urlsafe(10)}-{secure_filename(file.filename)}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    return filename


@web.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    wedding = current_wedding()
    if request.method == "POST":
        for field in ("title", "couple_names", "ceremony_name", "ceremony_address", "reception_name", "reception_address", "reception_time", "reception_maps_url", "dress_code", "gifts_url", "gifts_message"):
            setattr(wedding, field, request.form.get(field, "").strip() or None)
        raw_datetime = request.form.get("event_datetime", "")
        wedding.event_datetime = datetime.fromisoformat(raw_datetime) if raw_datetime else None
        for field in ("portrait_one", "portrait_two", "gift_qr"):
            file = request.files.get(field)
            if file and file.filename:
                filename = save_upload(file, ALLOWED_IMAGES)
                if filename:
                    setattr(wedding, field, filename)
                else:
                    flash("Las imágenes deben ser JPG, PNG o WEBP.", "danger")
                    return redirect(url_for("web.settings"))
        video = request.files.get("hero_video")
        if video and video.filename:
            filename = save_upload(video, ALLOWED_VIDEOS)
            if not filename:
                flash("El video debe ser MP4, MOV o WEBM.", "danger")
                return redirect(url_for("web.settings"))
            wedding.hero_video = filename
        for file in request.files.getlist("portraits"):
            if file and file.filename:
                filename = save_upload(file, ALLOWED_IMAGES)
                if not filename:
                    flash("Los retratos deben ser JPG, PNG o WEBP.", "danger")
                    return redirect(url_for("web.settings"))
                maximum = db.session.query(db.func.max(Portrait.position)).filter_by(wedding_id=wedding.id).scalar() or 0
                db.session.add(Portrait(wedding_id=wedding.id, filename=filename, position=maximum + 1))
        db.session.commit()
        flash("Configuración de la invitación guardada.", "success")
        return redirect(url_for("web.settings"))
    return render_template("settings.html", wedding=wedding)


@web.post("/settings/portraits/<int:portrait_id>/delete")
@admin_required
def delete_portrait(portrait_id):
    wedding = current_wedding()
    portrait = Portrait.query.filter_by(id=portrait_id, wedding_id=wedding.id).first_or_404()
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], portrait.filename)
    if os.path.isfile(filepath):
        os.remove(filepath)
    db.session.delete(portrait)
    db.session.commit()
    flash("Retrato eliminado.", "success")
    return redirect(url_for("web.settings"))


@web.post("/settings/legacy-portrait/<slot>/delete")
@admin_required
def delete_legacy_portrait(slot):
    if slot not in {"portrait_one", "portrait_two"}:
        return redirect(url_for("web.settings"))
    wedding = current_wedding()
    filename = getattr(wedding, slot)
    if filename:
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
        setattr(wedding, slot, None)
        db.session.commit()
        flash("Retrato eliminado.", "success")
    return redirect(url_for("web.settings"))


@web.post("/invitacion/<code>/recuerdos")
def upload_memory(code):
    guest = Guest.query.filter_by(invitation_code=code.upper()).first_or_404()
    file = request.files.get("memory")
    if not file or not file.filename:
        flash("Selecciona una foto o un video.", "danger")
        return redirect(url_for("web.public_invitation", code=code))
    allowed = ALLOWED_IMAGES | ALLOWED_VIDEOS
    filename = save_upload(file, allowed)
    if not filename:
        flash("Formato no permitido. Usa JPG, PNG, WEBP, MP4, MOV o WEBM.", "danger")
        return redirect(url_for("web.public_invitation", code=code))
    media_type = "video" if filename.rsplit(".", 1)[-1].lower() in ALLOWED_VIDEOS else "image"
    db.session.add(Memory(wedding_id=guest.wedding_id, guest_id=guest.id, filename=filename, media_type=media_type))
    db.session.commit()
    flash("¡Gracias por compartir este recuerdo!", "success")
    return redirect(url_for("web.public_invitation", code=code))


@web.get("/media/<path:filename>")
def media(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
from datetime import datetime
from enum import Enum
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class RSVPStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    weddings = db.relationship("Wedding", backref="organization", lazy=True)


class Wedding(db.Model):
    __tablename__ = "weddings"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    event_date = db.Column(db.Date, nullable=True)
    couple_names = db.Column(db.String(160), nullable=False, default="Nuestra boda")
    event_datetime = db.Column(db.DateTime, nullable=True)
    ceremony_name = db.Column(db.String(160), nullable=False, default="Parroquia Santa María Reina")
    ceremony_address = db.Column(db.String(255), nullable=False, default="Cl 30 #23-25, Cañaveral, Floridablanca, Santander")
    reception_name = db.Column(db.String(160), nullable=False, default="Salón de Eventos Golden Park")
    reception_address = db.Column(db.String(255), nullable=False, default="Vía Alto Vereda Lagunetas, Girón, Santander")
    reception_time = db.Column(db.String(40), nullable=False, default="7:00 p. m.")
    reception_maps_url = db.Column(db.String(500), nullable=True)
    dress_code = db.Column(db.String(255), nullable=True)
    gifts_url = db.Column(db.String(500), nullable=True)
    gifts_message = db.Column(db.Text, nullable=True)
    gift_qr = db.Column(db.String(255), nullable=True)
    portrait_one = db.Column(db.String(255), nullable=True)
    portrait_two = db.Column(db.String(255), nullable=True)
    hero_video = db.Column(db.String(255), nullable=True)
    guests = db.relationship("Guest", backref="wedding", lazy=True, cascade="all, delete-orphan")
    memories = db.relationship("Memory", backref="wedding", lazy=True, cascade="all, delete-orphan")
    portraits = db.relationship("Portrait", backref="wedding", lazy=True, cascade="all, delete-orphan", order_by="Portrait.position")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Family(db.Model):
    __tablename__ = "families"
    id = db.Column(db.Integer, primary_key=True)
    wedding_id = db.Column(db.Integer, db.ForeignKey("weddings.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)


class Guest(db.Model):
    __tablename__ = "guests"
    id = db.Column(db.Integer, primary_key=True)
    wedding_id = db.Column(db.Integer, db.ForeignKey("weddings.id"), nullable=False, index=True)
    family_id = db.Column(db.Integer, db.ForeignKey("families.id"), nullable=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(255))
    companions = db.Column(db.Integer, nullable=False, default=0)
    table_number = db.Column(db.String(30))
    rsvp_status = db.Column(db.Enum(RSVPStatus), nullable=False, default=RSVPStatus.PENDING)
    dietary_notes = db.Column(db.String(255))
    notes = db.Column(db.Text)
    invitation_code = db.Column(db.String(20), unique=True, index=True, nullable=True)
    rsvp_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def ensure_invitation_code(self):
        if not self.invitation_code:
            self.invitation_code = secrets.token_urlsafe(6).replace("-", "").replace("_", "").upper()


class Memory(db.Model):
    __tablename__ = "memories"
    id = db.Column(db.Integer, primary_key=True)
    wedding_id = db.Column(db.Integer, db.ForeignKey("weddings.id"), nullable=False, index=True)
    guest_id = db.Column(db.Integer, db.ForeignKey("guests.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Portrait(db.Model):
    __tablename__ = "portraits"
    id = db.Column(db.Integer, primary_key=True)
    wedding_id = db.Column(db.Integer, db.ForeignKey("weddings.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

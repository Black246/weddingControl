from .extensions import db
from .models import Organization, User, Wedding


def seed_data():
    db.create_all()
    if User.query.filter_by(email="admin@weddingcontrol.local").first():
        return
    organization = Organization(name="Mi boda")
    wedding = Wedding(organization=organization, title="Nuestra boda")
    admin = User(organization_id=1, name="Administrador", email="admin@weddingcontrol.local")
    admin.set_password("CambiaEstaClave123!")
    db.session.add_all([organization, wedding])
    db.session.flush()
    admin.organization_id = organization.id
    db.session.add(admin)
    db.session.commit()

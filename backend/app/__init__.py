import os

from dotenv import load_dotenv
from flask import Flask, redirect, url_for

from .extensions import db, jwt, migrate


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "desarrollo-solamente-cambiar-por-un-secreto-largo-2026"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///weddingcontrol.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "jwt-desarrollo-solamente-cambiar-por-un-secreto-largo-2026"),
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_CSRF_PROTECT=False,
        JWT_COOKIE_SECURE=False,
        UPLOAD_FOLDER=os.path.join(app.root_path, "uploads"),
        MAX_CONTENT_LENGTH=30 * 1024 * 1024,
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @jwt.unauthorized_loader
    def missing_access_token(_reason):
        return redirect(url_for("web.login"))

    @jwt.expired_token_loader
    def expired_access_token(_header, _payload):
        return redirect(url_for("web.login"))

    from .routes import web
    app.register_blueprint(web)

    # Development-friendly schema update for the first release. Replace with
    # Flask-Migrate revisions before deploying to production.
    with app.app_context():
        from sqlalchemy import inspect
        from . import models  # Register every model before create_all.
        db.create_all()
        columns = {column["name"] for column in inspect(db.engine).get_columns("guests")}
        wedding_columns = {column["name"] for column in inspect(db.engine).get_columns("weddings")}
        with db.engine.begin() as connection:
            if "invitation_code" not in columns:
                connection.exec_driver_sql("ALTER TABLE guests ADD COLUMN invitation_code VARCHAR(20)")
                connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_guests_invitation_code ON guests (invitation_code)")
            if "rsvp_at" not in columns:
                connection.exec_driver_sql("ALTER TABLE guests ADD COLUMN rsvp_at DATETIME")
            additions = {
                "couple_names": "VARCHAR(160) NOT NULL DEFAULT 'Nuestra boda'",
                "event_datetime": "DATETIME",
                "ceremony_name": "VARCHAR(160) NOT NULL DEFAULT 'Parroquia Santa María Reina'",
                "ceremony_address": "VARCHAR(255) NOT NULL DEFAULT 'Cl 30 #23-25, Cañaveral, Floridablanca, Santander'",
                "reception_name": "VARCHAR(160) NOT NULL DEFAULT 'Salón de Eventos Golden Park'",
                "reception_address": "VARCHAR(255) NOT NULL DEFAULT 'Vía Alto Vereda Lagunetas, Girón, Santander'",
                "reception_time": "VARCHAR(40) NOT NULL DEFAULT '7:00 p. m.'",
                "reception_maps_url": "VARCHAR(500)",
                "dress_code": "VARCHAR(255)", "gifts_url": "VARCHAR(500)", "gifts_message": "TEXT", "gift_qr": "VARCHAR(255)",
                "portrait_one": "VARCHAR(255)", "portrait_two": "VARCHAR(255)",
                "hero_video": "VARCHAR(255)",
            }
            for name, definition in additions.items():
                if name not in wedding_columns:
                    connection.exec_driver_sql(f"ALTER TABLE weddings ADD COLUMN {name} {definition}")

    @app.cli.command("seed")
    def seed():
        from .seed import seed_data
        seed_data()
        print("Datos iniciales creados.")

    return app

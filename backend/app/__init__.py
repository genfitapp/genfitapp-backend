import os
import jsonify
from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask_cors import CORS
from .auth.routes import auth_bp
from .profile.routes import profile_bp
from .venues.routes import venues_bp
from .equipment.routes import equipment_bp
from .user.routes import user_bp
from .support.routes import support_bp
from .records.routes import records_bp
from .workout.routes import workout_bp
from .stats.routes import stats_bp
from app.media.routes import media_bp
from .db import db  # import the db instance from the new module

from dotenv import load_dotenv  # <-- if you’re using a .env


# Define the path to the .env file relative to the project root
load_dotenv(find_dotenv(usecwd=True))


def create_app():
    load_dotenv()  # no-op if not using .env

    app = Flask(__name__)

    # Enable CORS for your entire app (adjust as needed)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # ---------------------------
    # Configuration values
    # ---------------------------
    app.config["SESSION_JWT_SECRET"] = os.getenv("SESSION_JWT_SECRET", "change-me-lol")
    app.config["GOOGLE_CLIENT_ID_WEB"] = os.getenv("GOOGLE_CLIENT_ID_WEB")
    app.config["GOOGLE_OAUTH_AUDIENCE"] = [
        os.getenv("GOOGLE_CLIENT_ID_IOS"),
        os.getenv("GOOGLE_CLIENT_ID_ANDROID"),
        os.getenv("GOOGLE_CLIENT_ID_WEB"),
    ]
    app.config["APPLE_AUDIENCE"] = os.getenv("APPLE_AUDIENCE")
    app.config["MAIL_FROM"] = os.getenv("MAIL_FROM")
    app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL")

    # Normalize avatar upload dir to an absolute path; default to <app_root>/uploads/avatars
    env_avatar_dir = os.getenv("AVATAR_UPLOAD_DIR")
    if env_avatar_dir:
        app.config["AVATAR_UPLOAD_DIR"] = os.path.abspath(env_avatar_dir)
    else:
        app.config["AVATAR_UPLOAD_DIR"] = os.path.join(app.root_path, "uploads", "avatars")

    # Optional: set this later when you move to a CDN/object storage
    # app.config["AVATAR_PUBLIC_BASE"] = os.getenv("AVATAR_PUBLIC_BASE")  # e.g. https://cdn.example.com/avatars
    # app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:pass@localhost/db"

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(workout_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(media_bp)

    # ---------------------------
    # Health & root
    # ---------------------------
    @app.get("/")
    def root():
        return jsonify({"status": "ok", "service": "genfit-backend"})

    @app.get("/healthz")
    def healthz():
        return "ok", 200

    return app

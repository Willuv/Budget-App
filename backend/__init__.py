from pathlib import Path

from flask import Flask

from backend.database import init_db
from backend.routes import api_bp

ROOT = Path(__file__).resolve().parents[1]


def create_app():
    app = Flask(
        __name__, 
        template_folder=str(ROOT / "templates"), 
        static_folder=str(ROOT / "static")
    )

    init_db()
    app.register_blueprint(api_bp)

    return app

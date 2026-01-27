from flask import Flask
from app.extensions import db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tenderwatch.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "dev"

    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        
        # Initialize settings if not exist
        from app.models import AppSettings
        if not AppSettings.query.first():
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()

    # Start scheduler if enabled
    from app.scheduler import start_scheduler
    start_scheduler(app)

    return app

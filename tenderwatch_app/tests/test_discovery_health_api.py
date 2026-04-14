import os

from app import create_app
from app.extensions import db
from app.models import AppSettings


def _make_app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    app = create_app(start_scheduler=False, init_db=True)
    app.config["TESTING"] = True
    return app


def test_discovery_health_api_shape():
    app = _make_app()

    with app.app_context():
        if not AppSettings.query.first():
            db.session.add(AppSettings())
            db.session.commit()

    client = app.test_client()
    resp = client.get("/api/discovery/health")
    assert resp.status_code == 200

    payload = resp.get_json()
    assert "providers" in payload
    assert "source_reliability" in payload
    assert "serpapi_configured" in payload["providers"]
    assert "success_rate" in payload["source_reliability"]

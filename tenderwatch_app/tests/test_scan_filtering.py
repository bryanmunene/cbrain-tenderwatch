import os

from app import create_app
from app.extensions import db
from app.models import AppSettings, TenderResult
from app.routes import _filtered_tenders_from_request


def _make_app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    app = create_app(start_scheduler=False, init_db=True)
    app.config["TESTING"] = True
    return app


def test_min_score_zero_does_not_force_twenty():
    app = _make_app()

    with app.app_context():
        if not AppSettings.query.first():
            db.session.add(AppSettings())
            db.session.commit()

        low = TenderResult(
            title="Low score item",
            link="https://example.com/low-score",
            score=10,
            recommendation="REVIEW",
            geographic_scope="africa",
            africa_priority_flag=True,
        )
        high = TenderResult(
            title="High score item",
            link="https://example.com/high-score",
            score=60,
            recommendation="GO",
            geographic_scope="africa",
            africa_priority_flag=True,
        )
        db.session.add(low)
        db.session.add(high)
        db.session.commit()

        settings = AppSettings.query.first()
        assert settings is not None

        with app.test_request_context("/scan?min_score=0&shortlist_mode=africa&sort=fit_score"):
            state = _filtered_tenders_from_request(TenderResult.query, settings)

        scores = [float(x.score or 0) for x in state["results"]]
        assert 10.0 in scores
        assert 60.0 in scores


def test_shortlist_scope_filters_are_case_insensitive():
    app = _make_app()

    with app.app_context():
        if not AppSettings.query.first():
            db.session.add(AppSettings())
            db.session.commit()

        africa = TenderResult(
            title="Africa scope item",
            link="https://example.com/africa-scope",
            score=30,
            recommendation="REVIEW",
            geographic_scope="Africa",
            africa_priority_flag=False,
        )
        global_item = TenderResult(
            title="Global scope item",
            link="https://example.com/global-scope",
            score=30,
            recommendation="REVIEW",
            geographic_scope="Global",
            africa_priority_flag=False,
        )
        db.session.add(africa)
        db.session.add(global_item)
        db.session.commit()

        settings = AppSettings.query.first()
        assert settings is not None

        with app.test_request_context("/scan?shortlist_mode=africa&sort=fit_score"):
            africa_state = _filtered_tenders_from_request(TenderResult.query, settings)
        with app.test_request_context("/scan?shortlist_mode=global&sort=fit_score"):
            global_state = _filtered_tenders_from_request(TenderResult.query, settings)

        assert [x.link for x in africa_state["results"]] == ["https://example.com/africa-scope"]
        assert [x.link for x in global_state["results"]] == ["https://example.com/global-scope"]

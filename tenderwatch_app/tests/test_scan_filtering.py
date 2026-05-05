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


def test_region_filter_matches_all_region_fields():
    app = _make_app()

    with app.app_context():
        if not AppSettings.query.first():
            db.session.add(AppSettings())
            db.session.commit()

        tenders = [
            TenderResult(
                title="Primary region item",
                link="https://example.com/primary-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                region="East Africa",
            ),
            TenderResult(
                title="Buyer region item",
                link="https://example.com/buyer-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                buyer_region="East Africa",
            ),
            TenderResult(
                title="Implementation region item",
                link="https://example.com/implementation-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                implementation_region="East Africa",
            ),
            TenderResult(
                title="Beneficiary region item",
                link="https://example.com/beneficiary-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                target_beneficiary_region="East Africa",
            ),
            TenderResult(
                title="Different region item",
                link="https://example.com/different-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                region="West Africa",
            ),
        ]
        db.session.add_all(tenders)
        db.session.commit()

        settings = AppSettings.query.first()
        assert settings is not None

        with app.test_request_context("/scan?shortlist_mode=combined&region=East%20Africa&sort=newest"):
            state = _filtered_tenders_from_request(TenderResult.query, settings)

        links = {x.link for x in state["results"]}
        assert links == {
            "https://example.com/primary-region",
            "https://example.com/buyer-region",
            "https://example.com/implementation-region",
            "https://example.com/beneficiary-region",
        }
        assert state["region_filter"] == "East Africa"


def test_scan_page_renders_visible_region_dropdown():
    app = _make_app()

    with app.app_context():
        db.session.add(
            TenderResult(
                title="Visible region option",
                link="https://example.com/visible-region",
                score=30,
                recommendation="REVIEW",
                geographic_scope="Global",
                region="East Africa",
            )
        )
        db.session.commit()

    response = app.test_client().get("/scan?shortlist_mode=combined")

    assert response.status_code == 200
    assert b'id="toolbar_region"' in response.data
    assert b"East Africa" in response.data

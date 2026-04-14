import os

import pytest

from app import create_app


def test_production_missing_secret_key_fails_fast(monkeypatch):
    monkeypatch.setenv("TW_ENV", "production")
    monkeypatch.setenv("TW_FAIL_FAST_ENV", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError):
        create_app(start_scheduler=False, init_db=False)


def test_non_production_allows_missing_secret_key(monkeypatch):
    monkeypatch.setenv("TW_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    app = create_app(start_scheduler=False, init_db=False)
    assert app is not None

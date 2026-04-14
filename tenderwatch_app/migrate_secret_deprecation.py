"""
Deprecation migration: clear legacy secret fields from app_settings.

This script intentionally preserves columns for backward compatibility,
but removes any persisted sensitive values so runtime uses environment
variables only.
"""

from app import create_app
from app.extensions import db
from app.models import AppSettings


def main() -> None:
    app = create_app(start_scheduler=False)
    with app.app_context():
        settings = AppSettings.query.first()
        if not settings:
            print("No AppSettings row found; nothing to migrate.")
            return

        changed = False
        if (settings.google_api_key or "").strip():
            settings.google_api_key = ""
            changed = True
        if (settings.bing_api_key or "").strip():
            settings.bing_api_key = ""
            changed = True
        if (settings.smtp_password or "").strip():
            settings.smtp_password = ""
            changed = True

        if changed:
            db.session.commit()
            print("Cleared persisted secret values from app_settings.")
        else:
            print("No persisted secret values found in app_settings.")


if __name__ == "__main__":
    main()

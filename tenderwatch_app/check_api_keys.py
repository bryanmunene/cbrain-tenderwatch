"""
Quick diagnostic script to check if API keys are saved in database
"""

from app import create_app
from app.extensions import db
from app.models import AppSettings

app = create_app()

with app.app_context():
    settings = AppSettings.query.first()
    
    if not settings:
        print("❌ No settings found in database!")
    else:
        print("✅ Settings found!")
        print(f"\nGoogle API Key: {'✓ Present (' + settings.google_api_key[:20] + '...)' if settings.google_api_key else '✗ Missing'}")
        print(f"Google CX: {'✓ Present (' + settings.google_cx + ')' if settings.google_cx else '✗ Missing'}")
        print(f"Bing API Key: {'✓ Present (' + settings.bing_api_key[:20] + '...)' if settings.bing_api_key else '✗ Missing'}")
        print(f"Auto-discovery enabled: {settings.auto_discovery_enabled if hasattr(settings, 'auto_discovery_enabled') else 'Column does not exist!'}")

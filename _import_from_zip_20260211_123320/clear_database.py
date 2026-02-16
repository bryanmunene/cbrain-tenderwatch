"""
Clear all existing tender results from database
Run this to remove old results that were scored with the lenient algorithm
"""

from app import create_app
from app.extensions import db
from app.models import TenderResult

def clear_all_tenders():
    app = create_app(start_scheduler=False)
    
    with app.app_context():
        count = TenderResult.query.count()
        
        if count == 0:
            print("âœ… Database is already empty")
            return
        
        confirm = input(f"âš ï¸  This will delete {count} tender(s). Continue? (yes/no): ")
        
        if confirm.lower() in ['yes', 'y']:
            TenderResult.query.delete()
            db.session.commit()
            print(f"ðŸ—‘ï¸  Deleted {count} tender(s) from database")
            print("âœ… Database cleared! Run a new scan to get results with strict keyword filtering.")
        else:
            print("âŒ Cancelled")

if __name__ == "__main__":
    clear_all_tenders()


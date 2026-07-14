import sys
import os

# Set path to import app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models

def dump():
    db = SessionLocal()
    try:
        interactions = db.query(models.Interaction).order_by(models.Interaction.id.desc()).limit(10).all()
        print("=== LAST 10 INTERACTIONS ===")
        for idx, i in enumerate(interactions):
            print(f"ID: {i.id} | Date: {i.date} | HCP ID: {i.hcp_id} | Channel: {i.channel}")
            print(f"  Attendees (Patient Name): {i.attendees}")
            print(f"  Doctor Rating: {i.doctor_rating}")
            print(f"  Products Discussed: {i.products_discussed}")
            print(f"  Feedback: {i.feedback}")
            print(f"  Notes: {i.notes}")
            print("-" * 50)
            
        hcps = db.query(models.HCP).all()
        print("\n=== HCPS IN DATABASE ===")
        for h in hcps:
            print(f"ID: {h.id} | Name: {h.name} | Phone: {h.phone} | Specialty: {h.specialty}")
        print("=" * 50)
    finally:
        db.close()

if __name__ == "__main__":
    dump()

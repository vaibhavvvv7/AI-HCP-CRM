import sys
import os

# Set path to import app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base, SessionLocal
from app import models
from app.agent import chat_with_agent

def run_verification():
    print("=== STARTING BACKEND INTEGRATION VERIFICATION ===")
    
    # 1. Initialize Tables
    print("\n1. Initializing SQLite tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 2. Check and Seed Data
        print("2. Checking database contents...")
        hcp_count = db.query(models.HCP).count()
        prod_count = db.query(models.Product).count()
        
        if hcp_count == 0 or prod_count == 0:
            print("   Database is empty. Seeding sample records...")
            # Seed Products
            products = [
                models.Product(name="Lipitor", description="Heart health medication.", therapeutic_area="Cardiology"),
                models.Product(name="Nexium", description="Stomach acid reducer.", therapeutic_area="Gastroenterology"),
                models.Product(name="Gilenya", description="Multiple sclerosis treatment.", therapeutic_area="Neurology")
            ]
            db.add_all(products)
            
            # Seed HCPs
            hcps = [
                models.HCP(name="Dr. Sarah Jenkins", specialty="Cardiology", clinic_name="Heart Institute", email="sjenkins@cardio.org", recent_sentiment="Positive"),
                models.HCP(name="Dr. Alex Mercer", specialty="Neurology", clinic_name="Apex Neuro", email="amercer@apexneuro.com", recent_sentiment="Neutral")
            ]
            db.add_all(hcps)
            db.commit()
            print("   Seed complete.")
        else:
            print(f"   Database contains {hcp_count} HCPs and {prod_count} Products.")

        # Re-fetch records
        db_hcps = db.query(models.HCP).all()
        active_hcp = db_hcps[0]
        print(f"   Using active HCP for test: {active_hcp.name} (ID: {active_hcp.id})")

        # 3. Test LangGraph Agent Conversational Tool Execution
        print("\n3. Testing LangGraph Agent (Conversational Logging)...")
        prompt = (
            "Just finished a face-to-face call with Dr. Sarah Jenkins. Discussed Lipitor patient efficacy. "
            "She was very positive and asked me to follow-up next Friday with trial documents."
        )
        print(f"   User Prompt: '{prompt}'")
        
        result = chat_with_agent(message=prompt, hcp_id=active_hcp.id, history=[])
        print("\n   [Agent Response]")
        print(result["response"])
        
        print("\n   [Triggered Tools / Suggested Actions]")
        for action in result["suggested_actions"]:
            print(f"   - Action type: {action['type']}")
            if 'data' in action:
                print(f"     Status: {action['data'].get('status')}")
                print(f"     Message: {action['data'].get('message')}")

        # 4. Verify DB writes from agent tools
        print("\n4. Verifying DB changes...")
        interactions_count = db.query(models.Interaction).filter(models.Interaction.hcp_id == active_hcp.id).count()
        tasks_count = db.query(models.FollowUpTask).filter(models.FollowUpTask.hcp_id == active_hcp.id).count()
        print(f"   HCP {active_hcp.name} now has:")
        print(f"   - {interactions_count} logged interactions in timeline.")
        print(f"   - {tasks_count} pending follow-up tasks scheduled.")
        
        print("\n=== BACKEND VERIFICATION COMPLETED SUCCESSFULLY ===")
        
    except Exception as e:
        print(f"\n[ERROR] Verification failed with error: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()

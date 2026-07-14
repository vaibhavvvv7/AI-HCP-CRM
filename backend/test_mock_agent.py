import sys
import os

# Set path to import app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Base, engine
from app import models, main
from app.agent import chat_with_agent

def run_tests():
    print("=== RUNNING MOCK AGENT DETAILED TESTS ===")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Get/create an HCP to use
        hcp = db.query(models.HCP).first()
        if not hcp:
            hcp = models.HCP(name="Dr. Sarah Jenkins", specialty="Cardiology", email="sjenkins@cardio.org")
            db.add(hcp)
            db.commit()
            db.refresh(hcp)
        
        hcp_id = hcp.id
        print(f"Using HCP: {hcp.name} (ID: {hcp_id})")
        
        # Test Case 1: Broad name/patient/attendees checks on general chat (e.g. Topics step)
        print("\n--- Test Case 1: Discussing patient details in topics step ---")
        history = [
            {"role": "assistant", "content": "Hello! Let's fill out your consultation feedback form step-by-step. First, what is the name of the doctor you visited?"},
            {"role": "user", "content": "Dr. Sarah Jenkins"},
            {"role": "assistant", "content": "I've started logging the form for Dr. Sarah Jenkins. What was the reason for your visit or the topic discussed during the consultation?"}
        ]
        
        # User says something containing "patient name" or "patient" during topics question
        msg = "We discussed the patient's Lipitor dosage and treatment options."
        res = chat_with_agent(message=msg, hcp_id=hcp_id, history=history)
        print(f"User: {msg}")
        print(f"Agent: {res['response']}")
        
        # Check that we did NOT get "I have updated that field on the form!"
        assert "updated that field" not in res['response'], "Error: Falsely intercepted as an update!"
        assert "satisfaction" in res['response'].lower(), "Error: Did not advance to the satisfaction question!"
        print("SUCCESS: Patient name was NOT falsely updated, flow advanced normally.")
        
        # Test Case 2: Skip (answering "nothing") during patient name step
        print("\n--- Test Case 2: Answering 'nothing' for patient name ---")
        history = [
            {"role": "assistant", "content": "Hello! Let's fill out your consultation feedback form step-by-step. First, what is the name of the doctor you visited?"},
            {"role": "user", "content": "Dr. Sarah Jenkins"},
            {"role": "assistant", "content": "I've started logging the form for Dr. Sarah Jenkins. What was the reason for your visit or the topic discussed during the consultation?"},
            {"role": "user", "content": "Lipitor dosage"},
            {"role": "assistant", "content": "Understood. On a scale of 1 to 5, how would you rate your satisfaction with the doctor?"},
            {"role": "user", "content": "5"},
            {"role": "assistant", "content": "Thanks for the rating! Do you have any additional feedback or suggestions about the doctor?"},
            {"role": "user", "content": "nothing"},
            {"role": "assistant", "content": "No problem! What is your name?"}
        ]
        
        res = chat_with_agent(message="nothing", hcp_id=hcp_id, history=history)
        print("User: nothing")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        # Verify that no edit_interaction occurred or it was not called with attendees, and it moved to phone number
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert not edit_action, "Error: edit_interaction was called when skip response was given!"
        assert "phone number" in res['response'].lower(), "Error: Did not advance to the phone number question!"
        print("SUCCESS: 'nothing' successfully skipped name question and advanced to phone.")
        
        # Test Case 3: Answering 'nothing' for phone number step
        print("\n--- Test Case 3: Answering 'nothing' for phone number ---")
        history.extend([
            {"role": "user", "content": "nothing"},
            {"role": "assistant", "content": "No problem! What is your phone number?"}
        ])
        res = chat_with_agent(message="nothing", hcp_id=hcp_id, history=history)
        print("User: nothing")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert not edit_action, "Error: edit_interaction was called when phone skip response was given!"
        assert "consultation a meeting" in res['response'].lower(), "Error: Did not advance to channel question!"
        print("SUCCESS: 'nothing' successfully skipped phone number question and advanced to channel.")

        # Test Case 4: Explicit triggers: "doctor name is", "my name is", "number is"
        print("\n--- Test Case 4: Explicit update triggers ---")
        # Initialize a conversation that has completed to test updating any field
        history = [
            {"role": "assistant", "content": "Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!"}
        ]
        
        # Test doctor name update
        msg = "doctor name is Dr. Jenkins"
        res = chat_with_agent(message=msg, hcp_id=hcp_id, history=history)
        print(f"User: {msg}")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert edit_action and edit_action[0]['data'].get('hcp_name') == "Dr. Jenkins", "Error: Doctor name update failed!"
        print("SUCCESS: 'doctor name is' successfully updated doctor name.")
        
        # Test patient name update
        msg = "my name is John Doe"
        res = chat_with_agent(message=msg, hcp_id=hcp_id, history=history)
        print(f"User: {msg}")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert edit_action and edit_action[0]['data'].get('attendees') == "John Doe", "Error: Patient name update failed!"
        print("SUCCESS: 'my name is' successfully updated patient name.")
        
        # Test phone number update
        msg = "number is 555-123-4567"
        res = chat_with_agent(message=msg, hcp_id=hcp_id, history=history)
        print(f"User: {msg}")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert edit_action and edit_action[0]['data'].get('phone') == "555-123-4567", "Error: Phone number update failed!"
        print("SUCCESS: 'number is' successfully updated phone number.")

        # Test Case 5: Finalization close out on 'no'
        print("\n--- Test Case 5: Finalization close out on 'no' ---")
        history = [
            {"role": "assistant", "content": "Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!"}
        ]
        
        # User says "no"
        res = chat_with_agent(message="no", hcp_id=hcp_id, history=history)
        print(f"User: no")
        print(f"Agent: {res['response']}")
        assert "closed your feedback form" in res['response'].lower(), "Error: Did not close form on 'no'!"
        print("SUCCESS: 'no' successfully finalized and closed the form.")

        # Test Case 6: Materials shared follow-up question
        print("\n--- Test Case 6: Materials shared follow-up question ---")
        history = [
            {"role": "assistant", "content": "Hello! Let's fill out your consultation feedback form step-by-step. First, what is the name of the doctor you visited?"},
            {"role": "user", "content": "Dr. Sarah Jenkins"},
            {"role": "assistant", "content": "I've started logging the form for Dr. Sarah Jenkins. What was the reason for your visit or the topic discussed during the consultation?"},
            {"role": "user", "content": "Lipitor dosage"},
            {"role": "assistant", "content": "Understood. On a scale of 1 to 5, how would you rate your satisfaction with the doctor?"},
            {"role": "user", "content": "5"},
            {"role": "assistant", "content": "Thanks for the rating! Do you have any additional feedback or suggestions about the doctor?"},
            {"role": "user", "content": "nothing"},
            {"role": "assistant", "content": "Thank you for the feedback. Were there any materials attached or shared?"}
        ]
        
        # User says "yes" to materials attached
        res = chat_with_agent(message="yes", hcp_id=hcp_id, history=history)
        print("User: yes")
        print(f"Agent: {res['response']}")
        assert "what specific materials" in res['response'].lower(), "Error: Did not ask for specific materials!"
        
        # User names the specific materials
        history.extend([
            {"role": "user", "content": "yes"},
            {"role": "assistant", "content": res['response']}
        ])
        res = chat_with_agent(message="Lipitor brochures, dosing guide", hcp_id=hcp_id, history=history)
        print("User: Lipitor brochures, dosing guide")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert edit_action and edit_action[0]['data'].get('materials_shared') == "Lipitor brochures, dosing guide", "Error: Materials shared update failed!"
        print("SUCCESS: Materials shared follow-up question and update succeeded.")

        # Test Case 7: Post-survey clarifying question for update doctor name
        print("\n--- Test Case 7: Post-survey clarifying question for update doctor name ---")
        history = [
            {"role": "assistant", "content": "Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!"}
        ]
        
        # User says "update doctor name"
        res = chat_with_agent(message="update doctor name", hcp_id=hcp_id, history=history)
        print("User: update doctor name")
        print(f"Agent: {res['response']}")
        assert "what would you like to update the doctor name to" in res['response'].lower(), "Error: Did not prompt for doctor name update!"
        
        # User responds with the doctor name
        history.extend([
            {"role": "user", "content": "update doctor name"},
            {"role": "assistant", "content": res['response']}
        ])
        res = chat_with_agent(message="Dr. Gregory House", hcp_id=hcp_id, history=history)
        print("User: Dr. Gregory House")
        print(f"Agent: {res['response']}")
        print(f"Suggested Actions: {res['suggested_actions']}")
        edit_action = [a for a in res['suggested_actions'] if a['type'] == 'edit_interaction']
        assert edit_action and edit_action[0]['data'].get('hcp_name') == "Dr. Gregory House", "Error: Doctor name clarifying update failed!"
        print("SUCCESS: Post-survey clarifying doctor name update succeeded.")

        print("\n=== ALL TEST CASES PASSED SUCCESSFULLY ===")
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()

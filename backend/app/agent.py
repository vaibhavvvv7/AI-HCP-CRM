import json
from typing import TypedDict, List, Dict, Any, Annotated, Sequence, Optional
from datetime import datetime, date, timedelta
import re

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from .database import SessionLocal
from .models import HCP, Product, Interaction, FollowUpTask
from .config import GROQ_API_KEY

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def normalize_name(name: str) -> str:
    if not name:
        return ""
    name_clean = name.lower().strip()
    name_clean = re.sub(r'^(dr\b\.?|doctor\b)\s*', '', name_clean)
    return re.sub(r'[^a-z0-9]', '', name_clean)

# ----------------------------------------------------
# 1. State Definition
# ----------------------------------------------------
class AgentState(TypedDict):
    messages: List[BaseMessage]
    hcp_id: int
    suggested_actions: List[Dict[str, Any]]
    response_text: str

# ----------------------------------------------------
# 2. Tool Definitions
# ----------------------------------------------------

@tool
def get_hcp_profile(hcp_id: int) -> str:
    """Retrieves details of the Healthcare Professional (HCP) including recent interactions and tasks."""
    db = SessionLocal()
    try:
        hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
        if not hcp:
            return f"HCP with ID {hcp_id} not found."
        
        # Get recent 3 interactions
        interactions = db.query(Interaction).filter(Interaction.hcp_id == hcp_id).order_by(Interaction.date.desc()).limit(3).all()
        # Get pending tasks
        tasks = db.query(FollowUpTask).filter(FollowUpTask.hcp_id == hcp_id, FollowUpTask.status == "Pending").all()
        
        profile = {
            "id": hcp.id,
            "name": hcp.name,
            "specialty": hcp.specialty,
            "clinic": hcp.clinic_name,
            "email": hcp.email,
            "phone": hcp.phone,
            "address": hcp.address,
            "recent_sentiment": hcp.recent_sentiment,
            "recent_interactions": [
                {
                    "date": i.date.strftime("%Y-%m-%d"),
                    "channel": i.channel,
                    "summary": i.summary,
                    "sentiment": i.sentiment
                } for i in interactions
            ],
            "pending_tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "due_date": t.due_date.strftime("%Y-%m-%d")
                } for t in tasks
            ]
        }
        return json.dumps(profile, indent=2)
    finally:
        db.close()

@tool
def log_interaction(
    hcp_id: int, 
    notes: str, 
    channel: str = "Meeting", 
    date_str: Optional[str] = None, 
    hcp_name: Optional[str] = None,
    time_str: Optional[str] = None,
    attendees: Optional[str] = None,
    topics: Optional[str] = None,
    materials_shared: Optional[str] = None,
    samples_distributed: Optional[str] = None,
    sentiment: Optional[str] = None,
    outcomes: Optional[str] = None,
    followup_actions: Optional[str] = None,
    doctor_rating: Optional[int] = None,
    feedback: Optional[str] = None,
    phone: Optional[str] = None
) -> str:
    """Logs a new interaction with an HCP and populates the details.
    
    Args:
        hcp_id: The database ID of the HCP.
        notes: Raw text notes or transcript of the conversation.
        channel: The channel/interaction type (e.g. Meeting, Call, Email).
        date_str: Date (YYYY-MM-DD).
        hcp_name: Name of the HCP (e.g. Dr. Smith).
        time_str: Time of interaction (e.g. 07:36 PM).
        attendees: Attendees.
        topics: Topics discussed (e.g. Product X efficiency).
        materials_shared: Materials shared (e.g. Brochures).
        samples_distributed: Samples distributed.
        sentiment: Sentiment (Positive, Neutral, Negative).
        outcomes: Key outcomes.
        followup_actions: Next steps.
        doctor_rating: Doctor rating on a scale of 1-5.
        feedback: Suggestions or feedback.
        phone: Phone number of the doctor.
    """
    db = SessionLocal()
    try:
        hcp = None
        if hcp_name:
            # Query all HCPs and match robustly using normalize_name
            hcps = db.query(HCP).all()
            search_norm = normalize_name(hcp_name)
            for h in hcps:
                h_norm = normalize_name(h.name)
                if search_norm and (search_norm in h_norm or h_norm in search_norm):
                    hcp = h
                    break
            
            if not hcp:
                # Check if generated email already exists to prevent duplicate / integrity error
                base_email = hcp_name.lower().replace(' ', '').replace('.', '')
                email = f"{base_email}@example.com"
                existing_email_hcp = db.query(HCP).filter(HCP.email == email).first()
                if existing_email_hcp:
                    hcp = existing_email_hcp
                else:
                    # Create a new HCP profile dynamically!
                    hcp = HCP(
                        name=hcp_name,
                        specialty="General Medicine",
                        clinic_name="Community Health",
                        email=email,
                        phone=phone,
                        recent_sentiment=sentiment or "Neutral"
                    )
                    db.add(hcp)
                    db.commit()
                    db.refresh(hcp)
        
        if not hcp:
            hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
            
        if not hcp:
            return f"Error: HCP with ID {hcp_id} does not exist."

        if phone and hcp:
            hcp.phone = phone
            db.commit()

        # Parse date and time
        log_date = datetime.utcnow()
        if date_str:
            try:
                if time_str:
                    try:
                        log_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
                    except ValueError:
                        log_date = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    log_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Compute sentiment from doctor_rating if provided
        if doctor_rating is not None:
            if doctor_rating in [1, 2]:
                sentiment = "Negative"
            elif doctor_rating in [3, 4, 5]:
                sentiment = "Positive"

        # Compute sentiment if not explicitly provided or inferred
        if not sentiment:
            sentiment = "Neutral"
            notes_lower = notes.lower()
            pos_words = ["happy", "interested", "good", "great", "excellent", "impressed", "agreed", "positive", "like"]
            neg_words = ["unhappy", "dislike", "skeptical", "concerned", "refused", "no interest", "busy", "poor"]
            pos_count = sum(1 for w in pos_words if w in notes_lower)
            neg_count = sum(1 for w in neg_words if w in notes_lower)
            if pos_count > neg_count:
                sentiment = "Positive"
            elif neg_count > pos_count:
                sentiment = "Negative"

        # Update HCP recent sentiment
        hcp.recent_sentiment = sentiment

        # Summary and products discussed
        summary = notes[:200] + "..." if len(notes) > 200 else notes
        
        # Save to DB
        interaction = Interaction(
            hcp_id=hcp.id,
            date=log_date,
            channel=channel,
            notes=notes,
            summary=outcomes or summary,
            sentiment=sentiment,
            next_steps=followup_actions or "None",
            products_discussed=topics or "None",
            doctor_rating=doctor_rating,
            feedback=feedback,
            attendees=attendees,
            materials_shared=materials_shared or "",
            samples_distributed=samples_distributed or ""
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        result = {
            "status": "success",
            "message": "Interaction logged successfully.",
            "interaction_id": interaction.id,
            "hcp_id": hcp.id,
            "hcp_name": hcp.name,
            "interaction_type": channel,
            "date": log_date.strftime("%Y-%m-%d"),
            "time": log_date.strftime("%I:%M %p"),
            "attendees": interaction.attendees or "",
            "topics": topics or interaction.products_discussed,
            "materials_shared": interaction.materials_shared or "",
            "samples_distributed": interaction.samples_distributed or "",
            "sentiment": sentiment,
            "outcomes": outcomes or "",
            "followup_actions": followup_actions or "",
            "doctor_rating": doctor_rating or 0,
            "feedback": feedback or "",
            "notes": interaction.notes or "",
            "phone": hcp.phone or ""
        }
        return json.dumps(result)
    except Exception as e:
        db.rollback()
        return f"Error logging interaction: {str(e)}"
    finally:
        db.close()

@tool
def edit_interaction(
    interaction_id: int, 
    notes: Optional[str] = None, 
    channel: Optional[str] = None, 
    sentiment: Optional[str] = None, 
    products: Optional[str] = None,
    hcp_name: Optional[str] = None,
    date_str: Optional[str] = None,
    time_str: Optional[str] = None,
    attendees: Optional[str] = None,
    topics: Optional[str] = None,
    materials_shared: Optional[str] = None,
    samples_distributed: Optional[str] = None,
    outcomes: Optional[str] = None,
    followup_actions: Optional[str] = None,
    doctor_rating: Optional[int] = None,
    feedback: Optional[str] = None,
    phone: Optional[str] = None
) -> str:
    """Modifies the details of an existing logged interaction.
    
    Args:
        interaction_id: The ID of the interaction to edit.
        notes: Updated notes.
        channel: Updated channel/interaction type.
        sentiment: Updated sentiment (Positive, Neutral, Negative).
        products: Comma-separated list of products discussed.
        hcp_name: Updated HCP name.
        date_str: Updated date.
        time_str: Updated time.
        attendees: Updated attendees list.
        topics: Updated topics.
        materials_shared: Updated materials shared.
        samples_distributed: Updated samples.
        outcomes: Updated outcomes.
        followup_actions: Updated next steps.
        doctor_rating: Updated doctor rating (1-5).
        feedback: Updated suggestions or feedback.
        phone: Updated phone number.
    """
    db = SessionLocal()
    try:
        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return f"Error: Interaction with ID {interaction_id} not found."

        # Fetch the HCP
        hcp = db.query(HCP).filter(HCP.id == interaction.hcp_id).first()
        if hcp:
            if hcp_name:
                hcp.name = hcp_name
            if phone:
                hcp.phone = phone
            db.commit()

        if notes is not None:
            interaction.notes = notes
            interaction.summary = notes[:200] + "..." if len(notes) > 200 else notes
        if channel is not None:
            interaction.channel = channel
        if doctor_rating is not None:
            interaction.doctor_rating = doctor_rating
            if sentiment is None:
                if doctor_rating in [1, 2]:
                    sentiment = "Negative"
                elif doctor_rating in [3, 4, 5]:
                    sentiment = "Positive"
        if sentiment is not None:
            interaction.sentiment = sentiment
            if hcp:
                hcp.recent_sentiment = sentiment
        if products is not None:
            interaction.products_discussed = products
        if topics is not None:
            interaction.products_discussed = topics
        if outcomes is not None:
            interaction.summary = outcomes
        if followup_actions is not None:
            interaction.next_steps = followup_actions
        if feedback is not None:
            interaction.feedback = feedback
        if attendees is not None:
            interaction.attendees = attendees
        if materials_shared is not None:
            interaction.materials_shared = materials_shared
        if samples_distributed is not None:
            interaction.samples_distributed = samples_distributed
 
        # Parse date and time if updated
        if date_str or time_str:
            # Get existing date parts
            cur_date = interaction.date.strftime("%Y-%m-%d")
            cur_time = interaction.date.strftime("%I:%M %p")
            new_date = date_str if date_str else cur_date
            new_time = time_str if time_str else cur_time
            try:
                interaction.date = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %I:%M %p")
            except ValueError:
                pass

        db.commit()
        db.refresh(interaction)
        if hcp:
            db.refresh(hcp)
        
        result = {
            "status": "success",
            "message": f"Interaction {interaction.id} updated successfully.",
            "interaction_id": interaction.id,
            "hcp_id": hcp.id if hcp else 0,
            "hcp_name": hcp.name if hcp else "Unknown",
            "interaction_type": interaction.channel,
            "date": interaction.date.strftime("%Y-%m-%d"),
            "time": interaction.date.strftime("%I:%M %p"),
            "attendees": interaction.attendees or "",
            "topics": topics or interaction.products_discussed,
            "materials_shared": interaction.materials_shared or "",
            "samples_distributed": interaction.samples_distributed or "",
            "sentiment": interaction.sentiment,
            "outcomes": outcomes or interaction.summary,
            "followup_actions": followup_actions or interaction.next_steps,
            "doctor_rating": interaction.doctor_rating or 0,
            "feedback": interaction.feedback or "",
            "notes": interaction.notes or "",
            "phone": hcp.phone if hcp else ""
        }
        return json.dumps(result)
    except Exception as e:
        db.rollback()
        return f"Error updating interaction: {str(e)}"
    finally:
        db.close()

@tool
def schedule_followup(hcp_id: int, description: str, due_date_str: str) -> str:
    """Schedules a new follow-up task with an HCP.
    
    Args:
        hcp_id: The database ID of the HCP.
        description: Description of what needs to be done.
        due_date_str: Due date in YYYY-MM-DD format.
    """
    db = SessionLocal()
    try:
        hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
        if not hcp:
            return f"Error: HCP with ID {hcp_id} does not exist."

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            return f"Error: Invalid date format for '{due_date_str}'. Please use YYYY-MM-DD."

        task = FollowUpTask(
            hcp_id=hcp_id,
            description=description,
            due_date=due_date,
            status="Pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        result = {
            "status": "success",
            "message": "Follow-up task scheduled.",
            "task_id": task.id,
            "hcp_name": hcp.name,
            "description": task.description,
            "due_date": task.due_date.strftime("%Y-%m-%d")
        }
        return json.dumps(result)
    except Exception as e:
        db.rollback()
        return f"Error scheduling task: {str(e)}"
    finally:
        db.close()

@tool
def generate_followup_email(hcp_id: int, interaction_summary: str) -> str:
    """Generates a highly personalized professional follow-up email layout to send to the HCP.
    
    Args:
        hcp_id: The ID of the HCP.
        interaction_summary: Summary of the meeting to construct relevant email text.
    """
    db = SessionLocal()
    try:
        hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
        if not hcp:
            return f"Error: HCP with ID {hcp_id} not found."

        subject = f"Follow-up: Scientific Discussion / Next Steps - {hcp.name}"
        
        body = (
            f"Dear Dr. {hcp.name.split()[-1]},\n\n"
            f"Thank you for taking the time to meet with me recently. I appreciated our discussion regarding "
            f"our latest therapeutic developments.\n\n"
            f"Regarding our conversation: \"{interaction_summary}\"\n\n"
            f"I am working on preparing the clinical resources we discussed and will follow up shortly. "
            f"Please let me know if you have any immediate questions in the meantime.\n\n"
            f"Best regards,\n\n"
            f"Life Sciences Relationship Team\n"
            f"CRM Therapeutics"
        )

        email_draft = {
            "status": "success",
            "to": hcp.email or "doctor@clinic.com",
            "subject": subject,
            "body": body
        }
        return json.dumps(email_draft)
    finally:
        db.close()

def generate_summary_from_data(data: dict) -> str:
    hcp_name = "the doctor"
    phone = None
    db = SessionLocal()
    hcp = db.query(HCP).filter(HCP.id == data["hcp_id"]).first()
    if hcp:
        hcp_name = hcp.name
        phone = data.get("phone") or hcp.phone
    db.close()
    
    parts = []
    attendees = data.get("attendees")
    if attendees:
        contact = f" ({phone})" if phone else ""
        parts.append(f"Patient {attendees}{contact} visited {hcp_name}")
    else:
        parts.append(f"Feedback session for {hcp_name}")
        
    products_discussed = data.get("products_discussed")
    if products_discussed and products_discussed != "None":
        parts.append(f"regarding '{products_discussed}'")
        
    channel = data.get("channel")
    if channel:
        parts.append(f"via {channel}")
        
    doctor_rating = data.get("doctor_rating")
    if doctor_rating:
        parts.append(f"Satisfaction rating: {doctor_rating}/5.")
        
    feedback = data.get("feedback")
    if feedback:
        parts.append(f"Feedback: '{feedback}'")
        
    materials_shared = data.get("materials_shared")
    if materials_shared:
        parts.append(f"Materials shared: {materials_shared}.")
        
    next_steps = data.get("next_steps")
    if next_steps and next_steps != "None":
        parts.append(f"Follow-up: {next_steps}.")
        
    return " ".join(parts)

def generate_discussion_summary(interaction):
    data = {
        "hcp_id": interaction.hcp_id,
        "attendees": interaction.attendees,
        "products_discussed": interaction.products_discussed,
        "channel": interaction.channel,
        "doctor_rating": interaction.doctor_rating,
        "feedback": interaction.feedback,
        "materials_shared": getattr(interaction, "materials_shared", None),
        "next_steps": getattr(interaction, "next_steps", None)
    }
    return generate_summary_from_data(data)

def summarize_chat_history_with_llm(messages: List[BaseMessage]) -> str:
    chat_lines = []
    for m in messages:
        role = ""
        content = ""
        if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
            role = "User"
            content = m.content
        elif isinstance(m, AIMessage) or (hasattr(m, "type") and m.type == "ai"):
            role = "Assistant"
            content = m.content
        elif isinstance(m, dict):
            role = "User" if m.get("role") == "user" else "Assistant"
            content = m.get("content", "")
            
        if content and role:
            if content.strip().startswith("{") and content.strip().endswith("}"):
                continue
            chat_lines.append(f"{role}: {content}")
            
    chat_text = "\n".join(chat_lines)
    if not chat_text:
        return ""
        
    try:
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
            temperature=0.1
        )
        prompt = (
            "You are a helpful CRM assistant. Summarize the following consultation feedback chat conversation into a single paragraph of simplified discussion notes.\n"
            "Include key details like: doctor visited, topics/products discussed, doctor satisfaction rating, feedback, patient name, contact info, materials shared, and scheduled follow-ups.\n"
            "Keep it concise, professional, and in third-person. Do not include conversational preambles or greetings. Output ONLY the summary paragraph.\n\n"
            f"Chat history:\n{chat_text}"
        )
        resp = model.invoke([HumanMessage(content=prompt)])
        return resp.content.strip()
    except Exception as e:
        print(f"Error summarizing chat history: {e}")
        return ""

def get_simplified_chat_summary(messages: List[BaseMessage], tool_args: Dict[str, Any]) -> str:
    if GROQ_API_KEY:
        summary = summarize_chat_history_with_llm(messages)
        if summary:
            return summary

    db = SessionLocal()
    latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
    
    temp = {
        "attendees": tool_args.get("attendees") or (latest.attendees if latest else ""),
        "products_discussed": tool_args.get("topics") or tool_args.get("products") or (latest.products_discussed if latest else ""),
        "channel": tool_args.get("channel") or (latest.channel if latest else ""),
        "doctor_rating": tool_args.get("doctor_rating") or (latest.doctor_rating if latest else None),
        "feedback": tool_args.get("feedback") or (latest.feedback if latest else ""),
        "materials_shared": tool_args.get("materials_shared") or (latest.materials_shared if latest else ""),
        "next_steps": tool_args.get("followup_actions") or (latest.next_steps if latest else ""),
        "hcp_id": tool_args.get("hcp_id") or (latest.hcp_id if latest else 1)
    }
    db.close()
    
    return generate_summary_from_data(temp)

# List of tools to pass to the agent
tools_list = [get_hcp_profile, log_interaction, edit_interaction, schedule_followup, generate_followup_email]
tools_map = {t.name: t for t in tools_list}

# ----------------------------------------------------
# 3. LangGraph Agent Construction
# ----------------------------------------------------

def run_mock_agent(state: AgentState) -> AgentState:
    """A highly specialized pattern-matching mock agent that acts when Groq API Key is not set."""
    messages = state["messages"]
    hcp_id = state["hcp_id"]
    last_message = messages[-1].content.strip()
    
    response_text = ""
    suggested_actions = []
    
    last_message_lower = last_message.lower()

    # Helper: detect when user intentionally skips a question
    SKIP_PHRASES = {"nothing", "none", "n/a", "na", "nope", "skip", "no", "nil", "nothing else", "no feedback", "no thanks"}
    def is_skip(text: str) -> bool:
        t = text.strip().lower().rstrip('.')
        return t in SKIP_PHRASES or t.startswith('nothing') and len(t) <= 20

    last_agent_message = ""
    questionnaire_prompts = [
        "name of the doctor you visited?",
        "reason for your visit or the topic discussed",
        "rate your satisfaction with the doctor",
        "additional feedback or suggestions",
        "were there any materials attached or shared?",
        "what specific materials were attached or shared?",
        "what is your name?",
        "what is your phone number?",
        "lastly, was this consultation a meeting",
        "schedule a next follow-up task?",
        "all your feedback has been logged in the form",
        "updated that field on the form",
        "what would you like to update the doctor name to?",
        "what would you like to update the patient name to?",
        "what would you like to update the phone number to?",
        "what would you like to update the materials shared to?",
        "what would you like to update the doctor rating to (1-5)?",
        "what would you like to update the feedback to?",
        "what would you like to update the topics discussed to?",
        "what would you like to update the interaction type to (meeting, call, virtual, email)?"
    ]
    
    for m in reversed(messages):
        msg_content = ""
        msg_role = ""
        if isinstance(m, dict):
            msg_content = m.get("content", "")
            msg_role = m.get("role", "")
        else:
            msg_content = getattr(m, "content", "")
            if hasattr(m, "type") and m.type == "ai":
                msg_role = "assistant"
            elif hasattr(m, "role"):
                msg_role = m.role
        if msg_role in ["assistant", "ai"] or "AIMessage" in str(type(m)):
            content_lower = msg_content.lower()
            if any(p in content_lower for p in questionnaire_prompts):
                last_agent_message = content_lower
                break
                
    if not last_agent_message:
        for m in reversed(messages):
            msg_content = ""
            msg_role = ""
            if isinstance(m, dict):
                msg_content = m.get("content", "")
                msg_role = m.get("role", "")
            else:
                msg_content = getattr(m, "content", "")
                if hasattr(m, "type") and m.type == "ai":
                    msg_role = "assistant"
                elif hasattr(m, "role"):
                    msg_role = m.role
            if msg_role in ["assistant", "ai"] or "AIMessage" in str(type(m)):
                last_agent_message = msg_content.lower()
                break

    # Helper to check if user wants to update a previously submitted field
    is_update = False
    update_args = {}
    is_survey_completed = "all your feedback has been logged in the form" in last_agent_message

    # Check clarifying reply parser
    is_clarifying_reply = False
    if "what would you like to update the doctor name to?" in last_agent_message:
        update_args["hcp_name"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the patient name to?" in last_agent_message:
        update_args["attendees"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the phone number to?" in last_agent_message:
        update_args["phone"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the materials shared to?" in last_agent_message:
        update_args["materials_shared"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the doctor rating to (1-5)?" in last_agent_message:
        rating_match = re.search(r"\b([1-5])\b", last_message)
        update_args["doctor_rating"] = int(rating_match.group(1)) if rating_match else 3
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the feedback to?" in last_agent_message:
        update_args["feedback"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the topics discussed to?" in last_agent_message:
        update_args["topics"] = last_message
        is_update = True
        is_clarifying_reply = True
    elif "what would you like to update the interaction type to (meeting, call, virtual, email)?" in last_agent_message:
        channel = "Meeting"
        if "virtual" in last_message_lower or "zoom" in last_message_lower or "teams" in last_message_lower:
            channel = "Virtual"
        elif "phone" in last_message_lower or "call" in last_message_lower:
            channel = "Call"
        elif "email" in last_message_lower:
            channel = "Email"
        update_args["channel"] = channel
        is_update = True
        is_clarifying_reply = True

    # Check rating update
    if not is_clarifying_reply and "rate your satisfaction with the doctor" not in last_agent_message:
        rating_match = re.search(r"(?:rating|rate|score|to)\s*\b([1-5])\b", last_message_lower)
        if rating_match:
            update_args["doctor_rating"] = int(rating_match.group(1))
            is_update = True
    
    # Check phone update
    is_phone_update = False
    if "what is your phone number?" not in last_agent_message:
        phone_triggers = ["number is", "phone is", "phone number is", "change phone to", "change phone number to", "update phone to", "update phone number to", "change number to", "update number to"]
        matched_phone_trigger = None
        for trigger in phone_triggers:
            if trigger in last_message_lower:
                matched_phone_trigger = trigger
                break
        if matched_phone_trigger:
            idx = last_message_lower.find(matched_phone_trigger)
            val = last_message[idx + len(matched_phone_trigger):].strip()
            val = re.sub(r'^[,.:;!?-]+|[,.:;!?-]+$', '', val).strip()
            phone_match = re.search(r"(\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{3}[-.]\d{4}\b|\b\d{7,12}\b)", val)
            if phone_match:
                update_args["phone"] = phone_match.group(1).strip()
                is_update = True
                is_phone_update = True
            elif val:
                update_args["phone"] = val
                is_update = True
                is_phone_update = True
        elif is_survey_completed:
            phone_match = re.search(r"(\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{3}[-.]\d{4}\b|\b\d{7,12}\b)", last_message)
            if phone_match:
                update_args["phone"] = phone_match.group(1).strip()
                is_update = True
                is_phone_update = True

    # Check doctor name update first
    is_doctor_name_update = False
    if "name of the doctor you visited?" not in last_agent_message:
        doc_triggers = ["doctor name is", "change doctor name to", "change doctor to", "update doctor name to", "update doctor to"]
        matched_doc_trigger = None
        for trigger in doc_triggers:
            if trigger in last_message_lower:
                matched_doc_trigger = trigger
                break
                
        if matched_doc_trigger:
            idx = last_message_lower.find(matched_doc_trigger)
            val = last_message[idx + len(matched_doc_trigger):].strip()
            val = re.sub(r'^[,.:;!?-]+|[,.:;!?-]+$', '', val).strip()
            if val:
                update_args["hcp_name"] = val
                is_update = True
                is_doctor_name_update = True

    # Check patient name update
    is_patient_name_update = False
    if not is_doctor_name_update and "what is your name?" not in last_agent_message:
        patient_triggers = ["my name is", "i am", "patient is", "patient name is", "attendees is", "change name to", "change patient name to", "change patient to", "update name to", "update patient name to", "update patient to"]
        matched_trigger = None
        for trigger in patient_triggers:
            if trigger in last_message_lower:
                matched_trigger = trigger
                break
        if matched_trigger:
            idx = last_message_lower.find(matched_trigger)
            val = last_message[idx + len(matched_trigger):].strip()
            val = re.sub(r'^[,.:;!?-]+|[,.:;!?-]+$', '', val).strip()
            if val:
                update_args["attendees"] = val
                is_update = True
                is_patient_name_update = True
        elif is_survey_completed and not is_skip(last_message) and last_message_lower not in {"yes", "ok", "okay", "correct", "confirm"} and "change" not in last_message_lower and "update" not in last_message_lower:
            # Case-insensitive name match
            name_match = re.search(r"(?i)\b(dr\.\s+[a-z]+|dr\s+[a-z]+|[a-z]+(?:\s+[a-z]+)?)\b", last_message)
            if name_match:
                update_args["attendees"] = name_match.group(1).strip()
                is_update = True
                is_patient_name_update = True

    # Check channel update
    if "meeting, phone call, virtual meeting, or email" not in last_agent_message:
        if is_survey_completed or any(tr in last_message_lower for tr in ["change channel", "update channel", "change type", "update type"]):
            if "channel" in last_message_lower or "type" in last_message_lower or any(ch in last_message_lower for ch in ["meeting", "call", "virtual", "email"]):
                channel = "Meeting"
                if "virtual" in last_message_lower or "zoom" in last_message_lower:
                    channel = "Virtual"
                elif "phone" in last_message_lower or "call" in last_message_lower:
                    channel = "Call"
                elif "email" in last_message_lower:
                    channel = "Email"
                update_args["channel"] = channel
                is_update = True

    # Check feedback update
    if "additional feedback or suggestions" not in last_agent_message:
        if is_survey_completed or any(tr in last_message_lower for tr in ["change feedback", "update feedback", "change suggestion", "update suggestion"]):
            if "feedback" in last_message_lower or "suggestion" in last_message_lower:
                update_args["feedback"] = last_message
                is_update = True

    # Check topic update
    if "reason for your visit or the topic discussed" not in last_agent_message:
        if is_survey_completed or any(tr in last_message_lower for tr in ["change topic", "update topic", "change reason", "update reason"]):
            if "topic" in last_message_lower or "reason" in last_message_lower:
                update_args["topics"] = last_message
                is_update = True

    # Check materials update
    if "were there any materials attached or shared?" not in last_agent_message:
        material_triggers = ["material is", "materials are", "change materials to", "update materials to", "change material to", "update material to"]
        matched_mat_trigger = None
        for trigger in material_triggers:
            if trigger in last_message_lower:
                matched_mat_trigger = trigger
                break
        if matched_mat_trigger:
            idx = last_message_lower.find(matched_mat_trigger)
            val = last_message[idx + len(matched_mat_trigger):].strip()
            val = re.sub(r'^[,.:;!?-]+|[,.:;!?-]+$', '', val).strip()
            if val:
                update_args["materials_shared"] = val
                is_update = True
        elif is_survey_completed or any(tr in last_message_lower for tr in ["change materials", "update materials", "change material", "update material"]):
            if "material" in last_message_lower:
                update_args["materials_shared"] = last_message
                is_update = True

    # Check if they asked to change/update a field but didn't provide a value
    if not is_update and not is_clarifying_reply and ("change" in last_message_lower or "update" in last_message_lower):
        if "doctor" in last_message_lower or "hcp" in last_message_lower or "dr" in last_message_lower:
            response_text = "Sure! What would you like to update the doctor name to?"
        elif "patient" in last_message_lower or "my name" in last_message_lower or "attendee" in last_message_lower or "name" in last_message_lower:
            response_text = "Sure! What would you like to update the patient name to?"
        elif "phone" in last_message_lower or "number" in last_message_lower:
            response_text = "Sure! What would you like to update the phone number to?"
        elif "material" in last_message_lower or "attachment" in last_message_lower:
            response_text = "Sure! What would you like to update the materials shared to?"
        elif "rating" in last_message_lower or "satisfaction" in last_message_lower or "score" in last_message_lower:
            response_text = "Sure! What would you like to update the doctor rating to (1-5)?"
        elif "feedback" in last_message_lower or "suggestion" in last_message_lower:
            response_text = "Sure! What would you like to update the feedback to?"
        elif "topic" in last_message_lower or "product" in last_message_lower or "reason" in last_message_lower:
            response_text = "Sure! What would you like to update the topics discussed to?"
        elif "channel" in last_message_lower or "type" in last_message_lower:
            response_text = "Sure! What would you like to update the interaction type to (Meeting, Call, Virtual, Email)?"

    if is_update:
        db = SessionLocal()
        latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
        id_val = latest.id if latest else 1
        if latest:
            temp = {
                "attendees": update_args.get("attendees", latest.attendees),
                "products_discussed": update_args.get("topics", latest.products_discussed),
                "channel": update_args.get("channel", latest.channel),
                "doctor_rating": update_args.get("doctor_rating", latest.doctor_rating),
                "feedback": update_args.get("feedback", latest.feedback),
                "materials_shared": update_args.get("materials_shared", latest.materials_shared),
                "next_steps": update_args.get("followup_actions", latest.next_steps),
                "hcp_id": latest.hcp_id
            }
            notes_summary = generate_summary_from_data(temp)
        else:
            notes_summary = last_message
        db.close()

        update_args["interaction_id"] = id_val
        update_args["notes"] = notes_summary
        edit_res = edit_interaction.invoke(update_args)
        try:
            edit_data = json.loads(edit_res)
        except (json.JSONDecodeError, Exception):
            edit_data = {"raw": edit_res}
        response_text = f"I have updated that field on the form! What would you like to do next?"
        suggested_actions.append({"type": "edit_interaction", "data": edit_data})

    elif response_text:
        # Clarifying question response_text is already set, so do nothing here and let it be returned!
        pass

    # Step-by-step Survey Flow
    else:
        # Step 6: Channel / Date / Time
        if "meeting, phone call, virtual meeting, or email" in last_agent_message:
            if is_skip(last_message):
                response_text = "Got it! Would you like to schedule a next follow-up task? If so, please tell me the description and the next follow-up date (YYYY-MM-DD)."
            else:
                channel = "Meeting"
                if "virtual" in last_message_lower or "zoom" in last_message_lower or "teams" in last_message_lower:
                    channel = "Virtual"
                elif "phone" in last_message_lower or "call" in last_message_lower:
                    channel = "Call"
                elif "email" in last_message_lower:
                    channel = "Email"
                
                # Combine into date_str and time_str fallback
                date_str = date.today().strftime("%Y-%m-%d")
                time_str = datetime.now().strftime("%I:%M %p")
                
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "channel": channel,
                    "date_str": date_str,
                    "time_str": time_str,
                    "notes": notes_summary
                })
                try:
                    edit_data = json.loads(edit_res)
                except (json.JSONDecodeError, Exception):
                    edit_data = {"raw": edit_res}
                response_text = "Got it! Would you like to schedule a next follow-up task? If so, please tell me the description and the next follow-up date (YYYY-MM-DD)."
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})
            
        # Step 7: Follow-up scheduling
        elif "schedule a next follow-up task?" in last_agent_message:
            if is_skip(last_message) or any(no in last_message_lower for no in ["no", "none", "don't need", "no follow-up", "n/a"]):
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": "None",
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                
                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "followup_actions": "None",
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                db.close()
                
                response_text = "Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})
            else:
                date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", last_message)
                due_date_str = date_match.group(1) if date_match else (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
                
                description = last_message.replace(due_date_str, "").replace("on", "").strip()
                description = re.sub(r'\s+', ' ', description)
                description = re.sub(r'^[,.:;!?-]+|[,.:;!?-]+$', '', description).strip()
                if not description:
                    description = "Follow-up discussion"
                
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                
                task_res = schedule_followup.invoke({
                    "hcp_id": latest.hcp_id if latest else hcp_id,
                    "description": description,
                    "due_date_str": due_date_str
                })
                try:
                    task_data = json.loads(task_res)
                except (json.JSONDecodeError, Exception):
                    task_data = {"raw": task_res}
                
                followup_text = f"Follow-up on {due_date_str}: {description}"
                
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": followup_text,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                
                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "followup_actions": followup_text,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                db.close()
                
                response_text = "Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!"
                suggested_actions.append({"type": "schedule_followup", "data": task_data})
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 8: Finalization close out when user says "No"
        elif "all your feedback has been logged in the form" in last_agent_message:
            if is_skip(last_message) or any(no in last_message_lower for no in ["no", "no thanks", "nothing else", "stop", "end"]):
                response_text = "Great! I have finalized and closed your feedback form. Have a wonderful day!"
            else:
                response_text = "Understood. Please let me know if you would like to make any other changes, or say 'No' to close the form."

        # Step 8.5: After updates, handle finalization close out
        elif "updated that field on the form" in last_agent_message:
            if is_skip(last_message) or any(no in last_message_lower for no in ["no", "no thanks", "nothing else", "stop", "end"]):
                response_text = "Great! I have finalized and closed your feedback form. Have a wonderful day!"
            else:
                response_text = "Understood. Please let me know if you would like to make any other changes, or say 'No' to close the form."

        # Step 5b: Phone number (asked separately after patient name)
        elif "what is your phone number?" in last_agent_message:
            if is_skip(last_message):
                response_text = "Got it! Lastly, was this consultation a Meeting, Phone Call, Virtual Meeting, or Email? Also, what date and time did it occur?"
            else:
                phone = None
                phone_match = re.search(r"(\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{3}[-.]\d{4}\b|\b\d{7,12}\b)", last_message)
                if phone_match:
                    phone = phone_match.group(1).strip()
                else:
                    # Accept whatever the user typed as their phone
                    phone = last_message.strip()

                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id,
                        "phone": phone
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "phone": phone,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                response_text = "Got it! Lastly, was this consultation a Meeting, Phone Call, Virtual Meeting, or Email? Also, what date and time did it occur?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 5a: Patient name (asked first, separately)
        elif "what is your name?" in last_agent_message:
            if is_skip(last_message):
                response_text = "Thank you! What is your phone number?"
            else:
                attendees = last_message.strip()
                name_match = re.search(r"(?i:my name is|i am|patient is|patient name is|name is)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)", last_message)
                if name_match:
                    attendees = name_match.group(1).strip()

                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "attendees": attendees,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                response_text = "Thank you! What is your phone number?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 4: Feedback
        elif "additional feedback or suggestions" in last_agent_message:
            if is_skip(last_message):
                # User has nothing to add — skip saving and move on
                response_text = "No problem! Were there any materials attached or shared?"
            else:
                feedback = last_message.strip()
                
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "feedback": feedback,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                response_text = "Thank you for the feedback. Were there any materials attached or shared?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 4.5: Materials attached
        elif "were there any materials attached or shared?" in last_agent_message:
            if is_skip(last_message) or any(no in last_message_lower for no in ["no", "none", "nope", "n/a"]):
                response_text = "Got it! What is your name?"
            else:
                yes_phrases = {"yes", "yep", "yeah", "sure", "y", "correct", "true", "indeed", "there were", "yes there were"}
                cleaned_msg = last_message_lower.strip().rstrip('.')
                if cleaned_msg in yes_phrases:
                    response_text = "What specific materials were attached or shared?"
                else:
                    materials = last_message.strip()
                    db = SessionLocal()
                    latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                    id_val = latest.id if latest else 1
                    if latest:
                        temp = {
                            "attendees": latest.attendees,
                            "products_discussed": latest.products_discussed,
                            "channel": latest.channel,
                            "doctor_rating": latest.doctor_rating,
                            "feedback": latest.feedback,
                            "materials_shared": materials,
                            "next_steps": latest.next_steps,
                            "hcp_id": latest.hcp_id
                        }
                        notes_summary = generate_summary_from_data(temp)
                    else:
                        notes_summary = last_message
                    db.close()

                    edit_res = edit_interaction.invoke({
                        "interaction_id": id_val,
                        "materials_shared": materials,
                        "notes": notes_summary
                    })
                    try:
                        edit_data = json.loads(edit_res)
                    except Exception:
                        edit_data = {"raw": edit_res}
                    response_text = "Got it! What is your name?"
                    suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 4.6: Specific materials attached
        elif "what specific materials were attached or shared?" in last_agent_message:
            if is_skip(last_message) or any(no in last_message_lower for no in ["no", "none", "nope", "n/a"]):
                response_text = "Got it! What is your name?"
            else:
                materials = last_message.strip()
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": materials,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "materials_shared": materials,
                    "notes": notes_summary
                })
                try:
                    edit_data = json.loads(edit_res)
                except Exception:
                    edit_data = {"raw": edit_res}
                response_text = "Got it! What is your name?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 3: Rating
        elif "rate your satisfaction with the doctor" in last_agent_message:
            if is_skip(last_message):
                # Skip — don't save a rating, advance to feedback question
                response_text = "No problem! Do you have any additional feedback or suggestions about the doctor?"
            else:
                rating_match = re.search(r"\b([1-5])\b", last_message)
                doctor_rating = int(rating_match.group(1)) if rating_match else 3
                
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": latest.products_discussed,
                        "channel": latest.channel,
                        "doctor_rating": doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "doctor_rating": doctor_rating,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                response_text = "Thanks for the rating! Do you have any additional feedback or suggestions about the doctor?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 2: Topics discussed / reason for visit
        elif "reason for your visit or the topic discussed" in last_agent_message:
            if is_skip(last_message):
                # Skip saving — just advance
                response_text = "Understood. On a scale of 1 to 5, how would you rate your satisfaction with the doctor?"
            else:
                topics = last_message.strip()
                
                db = SessionLocal()
                latest = db.query(Interaction).order_by(Interaction.date.desc()).first()
                id_val = latest.id if latest else 1
                if latest:
                    temp = {
                        "attendees": latest.attendees,
                        "products_discussed": topics,
                        "channel": latest.channel,
                        "doctor_rating": latest.doctor_rating,
                        "feedback": latest.feedback,
                        "materials_shared": latest.materials_shared,
                        "next_steps": latest.next_steps,
                        "hcp_id": latest.hcp_id
                    }
                    notes_summary = generate_summary_from_data(temp)
                else:
                    notes_summary = last_message
                db.close()

                edit_res = edit_interaction.invoke({
                    "interaction_id": id_val,
                    "topics": topics,
                    "notes": notes_summary
                })
                edit_data = json.loads(edit_res)
                response_text = "Understood. On a scale of 1 to 5, how would you rate your satisfaction with the doctor?"
                suggested_actions.append({"type": "edit_interaction", "data": edit_data})

        # Step 1: Doctor name (HCP Name)
        elif "name of the doctor you visited?" in last_agent_message:
            if is_skip(last_message):
                db = SessionLocal()
                hcp = db.query(HCP).filter(HCP.id == hcp_id).first()
                hcp_name = hcp.name if hcp else "the doctor"
                db.close()

                log_res = log_interaction.invoke({
                    "hcp_id": hcp_id,
                    "notes": "Feedback session for the doctor",
                    "date_str": date.today().strftime("%Y-%m-%d"),
                    "time_str": datetime.now().strftime("%I:%M %p")
                })
                log_data = json.loads(log_res)
                response_text = f"I've started logging the form for {hcp_name}. What was the reason for your visit or the topic discussed during the consultation?"
                suggested_actions.append({"type": "log_interaction", "data": log_data})
            else:
                hcp_name = None
                doc_match = re.search(r"\b(Dr\.\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?|Dr\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?|[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)\b", last_message)
                if doc_match:
                    hcp_name = doc_match.group(1).strip()
                else:
                    hcp_name = last_message.strip()

                log_res = log_interaction.invoke({
                    "hcp_id": hcp_id,
                    "hcp_name": hcp_name,
                    "notes": f"Feedback session for {hcp_name}",
                    "date_str": date.today().strftime("%Y-%m-%d"),
                    "time_str": datetime.now().strftime("%I:%M %p")
                })
                log_data = json.loads(log_res)
                response_text = f"I've started logging the form for {hcp_name}. What was the reason for your visit or the topic discussed during the consultation?"
                suggested_actions.append({"type": "log_interaction", "data": log_data})

        # Welcome / First message
        else:
            response_text = "Hello! Let's fill out your consultation feedback form step-by-step. First, what is the name of the doctor you visited?"

    new_messages = messages + [AIMessage(content=response_text)]
    return {
        "messages": new_messages,
        "hcp_id": hcp_id,
        "suggested_actions": suggested_actions,
        "response_text": response_text
    }

# ----------------------------------------------------
# 4. Define LLM-based StateGraph Nodes (if Key is active)
# ----------------------------------------------------

def call_llm(state: AgentState) -> Dict[str, Any]:
    """Invokes the Groq model with tool definitions."""
    if not GROQ_API_KEY:
        # If API key is missing, route immediately to mock agent
        return run_mock_agent(state)
    
    try:
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
            temperature=0.1
        )
        
        # Bind tools
        model_with_tools = model.bind_tools(tools_list)
        
        # Setup prompt
        system_prompt = (
            "You are a friendly patient feedback assistant. Your main goal is to fill out a single feedback form "
            "for the selected doctor (HCP) by asking the patient questions step-by-step.\n\n"
            "To gather the necessary details, follow this questionnaire sequence:\n"
            "1. Ask for the doctor's name they visited.\n"
            "2. Ask for the topic or reason for the consultation (log the interaction once you have the doctor name).\n"
            "3. Ask for their satisfaction rating of the doctor (from 1 to 5).\n"
            "4. Ask for any suggestions or additional feedback.\n"
            "5. Ask if there were any materials attached or shared.\n"
            "6. If materials were attached or shared (i.e. user responds yes or indicates so), ask 'What specific materials were attached or shared?' and update the materials_shared field with their response. If they say no or skip, proceed directly to asking for their name.\n"
            "7. Ask ONLY for their name (patient name). Do NOT ask for phone number here.\n"
            "8. Ask ONLY for their phone number. Do NOT ask for name or anything else here.\n"
            "9. Ask for the interaction channel (Meeting, Call, Virtual, Email) and the date/time of the visit.\n"
            "10. Ask if they want to schedule a next follow-up task (getting description and due date in YYYY-MM-DD format). If so, call `schedule_followup` and also write it to `followup_actions` on the form.\n"
            "11. Confirm that the entire form is logged, saying: 'Thank you! All your feedback has been logged in the form on the left. Let me know if you would like to update or change any of the fields!'\n"
            "12. Once you display this confirmation, if the user replies 'No', end the conversation and close the form.\n\n"
            "RULES:\n"
            "- Ask only ONE question at a time. Never combine two questions in one message.\n"
            "- Ask for name and phone number in TWO SEPARATE messages — name first, then phone.\n"
            "- When the user provides a detail, call the appropriate database tool (`log_interaction` or `edit_interaction`) to update the form fields in real-time.\n"
            "- IMPORTANT: If the user replies with 'nothing', 'none', 'n/a', 'skip', 'nope', or any similar empty/skip phrase to ANY question in the questionnaire flow (including doctor name, topics, rating, feedback, materials, patient name, phone, channel, follow-up), do NOT save/update that field in the database. Simply acknowledge and move on to the next question in the sequence.\n"
            "- IMPORTANT: Only update patient name (attendees), doctor name (hcp_name), phone number (phone), or materials (materials_shared) in `edit_interaction` if the user explicitly asks to update/change them (using triggers like 'my name is Y', 'doctor name is X', 'number is Z', 'materials are W', 'change name to ...') or is currently answering that specific question in the flow.\n"
            "- If the user asks to 'update' or 'change' a field (such as 'doctor name', 'patient name', or 'phone number') after the survey is completed but does not provide the new value in the same message, ask a clarifying question (e.g. 'What would you like to update the doctor name to?'). Once they respond with the new value, call `edit_interaction` to save it.\n"
            "- After completing the questionnaire, construct a short summary of the whole chat and save it in the `notes` (Discussion Notes) field of the interaction.\n"
            "- If the user asks to change or update any details at any point (e.g. 'actually change my rating to 4'), call `edit_interaction` to apply the update immediately."
        )
        
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        
        # Add an explicit instruction to ensure the tool receives correct arguments
        messages.append(SystemMessage(content=f"IMPORTANT: The current active HCP ID is {state['hcp_id']}. Always use this hcp_id when calling tools that require it."))
        
        response = model_with_tools.invoke(messages)
        
        return {
            "messages": state["messages"] + [response],
            "hcp_id": state["hcp_id"],
            "suggested_actions": state.get("suggested_actions", []),
            "response_text": response.content
        }
    except Exception as e:
        print(f"Error calling Groq API: {str(e)}. Falling back to local Mock Agent.")
        return run_mock_agent(state)

def execute_tools(state: AgentState) -> Dict[str, Any]:
    """Executes tools called by the LLM."""
    messages = state["messages"]
    last_message = messages[-1]
    suggested_actions = list(state.get("suggested_actions", []))
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return state
        
    new_messages = list(messages)
    tool_outputs = []
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # Inject HCP ID if missing from LLM arguments
        if "hcp_id" in tool_args and (tool_args["hcp_id"] is None or tool_args["hcp_id"] == 0):
            tool_args["hcp_id"] = state["hcp_id"]
            
        # Rewrite the notes argument to be the simplified summary of the whole chat
        if tool_name in ["log_interaction", "edit_interaction"]:
            tool_args["notes"] = get_simplified_chat_summary(messages, tool_args)
            
        # Execute tool
        selected_tool = tools_map.get(tool_name)
        if selected_tool:
            tool_res = selected_tool.invoke(tool_args)
            new_messages.append(
                ToolMessage(
                    content=str(tool_res),
                    tool_call_id=tool_call["id"]
                )
            )
            
            # Parse result to add to suggested actions for the frontend UI
            try:
                data = json.loads(tool_res)
                suggested_actions.append({"type": tool_name, "data": data})
            except Exception:
                suggested_actions.append({"type": tool_name, "raw_data": str(tool_res)})
                
            tool_outputs.append(f"Tool {tool_name} returned: {tool_res}")
            
    # After running tools, run the model again to let it summarize the tool execution
    try:
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
            temperature=0.1
        )
        final_resp = model.invoke(new_messages)
        content = final_resp.content
        new_messages.append(final_resp)
    except Exception as e:
        print(f"Error calling Groq API in execute_tools: {str(e)}. Using fallback text.")
        content = "I have saved those details to the form. What is the next detail you'd like to provide?"
        new_messages.append(AIMessage(content=content))
        
    return {
        "messages": new_messages,
        "hcp_id": state["hcp_id"],
        "suggested_actions": suggested_actions,
        "response_text": content
    }

def should_continue(state: AgentState):
    """Determines whether the graph should branch to tools or end."""
    if not GROQ_API_KEY:
        # Mock agent handles execution locally and goes straight to END
        return "end"
        
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"
    return "end"

# ----------------------------------------------------
# 5. Compile StateGraph
# ----------------------------------------------------

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("agent", call_llm)
workflow.add_node("action", execute_tools)

# Set entry point
workflow.set_entry_point("agent")

# Add conditional edges
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "end": END
    }
)

# Add transition from action back to agent (or end directly, we'll route action to END for simplicity or let LLM evaluate)
workflow.add_edge("action", END)

agent_app = workflow.compile()

# Helper interface for FastAPI
def chat_with_agent(message: str, hcp_id: int, history: List[dict] = None) -> Dict[str, Any]:
    """Interface to call the compiled LangGraph agent."""
    messages_list = []
    
    # Rebuild history
    if history:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                messages_list.append(HumanMessage(content=content))
            elif role == "assistant":
                messages_list.append(AIMessage(content=content))
                
    messages_list.append(HumanMessage(content=message))
    
    initial_state = {
        "messages": messages_list,
        "hcp_id": hcp_id,
        "suggested_actions": [],
        "response_text": ""
    }
    
    final_state = agent_app.invoke(initial_state)
    
    return {
        "response": final_state["response_text"],
        "suggested_actions": final_state["suggested_actions"]
    }

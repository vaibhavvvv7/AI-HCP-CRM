from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from .database import engine, Base, get_db
from . import models, schemas
from .agent import chat_with_agent

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI-First CRM HCP Module Backend")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI-First CRM HCP Module API is running"}

# --- Seed DB ---
@app.post("/api/seed", status_code=status.HTTP_201_CREATED)
def seed_database(db: Session = Depends(get_db)):
    # Check if products already exist
    if db.query(models.Product).count() > 0:
        return {"message": "Database already seeded."}

    # 1. Seed Products
    products = [
        models.Product(name="Lipitor", description="Statin medication to prevent cardiovascular disease and lower lipids.", therapeutic_area="Cardiology"),
        models.Product(name="Zestril", description="ACE inhibitor for treating hypertension and heart failure.", therapeutic_area="Cardiology"),
        models.Product(name="Nexium", description="Proton pump inhibitor to reduce stomach acid and treat GERD.", therapeutic_area="Gastroenterology"),
        models.Product(name="Keytruda", description="Immunotherapy treatment used to combat various cancer types.", therapeutic_area="Oncology"),
        models.Product(name="Gilenya", description="Immunomodulator used for multiple sclerosis treatment.", therapeutic_area="Neurology")
    ]
    db.add_all(products)

    # 2. Seed HCPs
    hcps = [
        models.HCP(name="Dr. Sarah Jenkins", specialty="Cardiology", clinic_name="Heart & Vascular Institute", email="sjenkins@cardio.org", phone="555-0192", address="100 Medical Plaza, Suite 400", recent_sentiment="Positive"),
        models.HCP(name="Dr. Alex Mercer", specialty="Neurology", clinic_name="Apex Neuro Group", email="amercer@apexneuro.com", phone="555-0143", address="220 Brain Center Blvd", recent_sentiment="Neutral"),
        models.HCP(name="Dr. Elena Rostova", specialty="Oncology", clinic_name="Metro Oncology Center", email="erostova@metrooncology.com", phone="555-0188", address="350 Cancer Care Way, Building B", recent_sentiment="Positive"),
        models.HCP(name="Dr. Marcus Vance", specialty="Endocrinology", clinic_name="Vance Endocrinology Clinic", email="mvance@vanceendo.com", phone="555-0177", address="50 Glandular Ave, Room 12")
    ]
    db.add_all(hcps)
    db.commit() # Commit to get IDs

    # 3. Seed Interactions
    interactions = [
        models.Interaction(
            hcp_id=hcps[0].id,
            channel="Face-to-Face",
            notes="Discussed Lipitor clinical trial data. The doctor was happy with the cardiology profiles and requested print brochures to share with patients.",
            summary="Presented Lipitor safety profile. Dr. Jenkins expressed positive interest and requested printed patient brochures.",
            sentiment="Positive",
            next_steps="Send Lipitor print brochures.",
            products_discussed="Lipitor"
        ),
        models.Interaction(
            hcp_id=hcps[1].id,
            channel="Phone",
            notes="Called Dr. Mercer regarding Gilenya efficacy reports. He was busy but asked to send him the PDF summary via email.",
            summary="Short phone update on Gilenya. Doctor requested PDF summary.",
            sentiment="Neutral",
            next_steps="Email Gilenya PDF summary.",
            products_discussed="Gilenya"
        )
    ]
    db.add_all(interactions)

    # 4. Seed Tasks
    tasks = [
        models.FollowUpTask(
            hcp_id=hcps[0].id,
            description="Send Lipitor printed patient brochures",
            due_date=date.today(),
            status="Pending"
        ),
        models.FollowUpTask(
            hcp_id=hcps[1].id,
            description="Email Gilenya efficacy PDF summary",
            due_date=date.today(),
            status="Pending"
        )
    ]
    db.add_all(tasks)
    db.commit()

    return {"message": "Database seeded successfully with products, HCPs, interactions, and tasks."}

# --- HCP Endpoints ---
@app.get("/api/hcps", response_model=List[schemas.HCPResponse])
def get_hcps(db: Session = Depends(get_db)):
    return db.query(models.HCP).all()

@app.post("/api/hcps", response_model=schemas.HCPResponse)
def create_hcp(hcp: schemas.HCPCreate, db: Session = Depends(get_db)):
    db_hcp = models.HCP(**hcp.model_dump())
    db.add(db_hcp)
    db.commit()
    db.refresh(db_hcp)
    return db_hcp

# --- Product Endpoints ---
@app.get("/api/products", response_model=List[schemas.ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()

# --- Interaction Endpoints ---
@app.get("/api/interactions", response_model=List[schemas.InteractionResponse])
def get_interactions(hcp_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Interaction)
    if hcp_id is not None:
        query = query.filter(models.Interaction.hcp_id == hcp_id)
    return query.order_by(models.Interaction.date.desc()).all()

@app.post("/api/interactions", response_model=schemas.InteractionResponse)
def create_interaction(interaction: schemas.InteractionCreate, db: Session = Depends(get_db)):
    # Verify HCP exists
    hcp = db.query(models.HCP).filter(models.HCP.id == interaction.hcp_id).first()
    if not hcp:
        raise HTTPException(status_code=404, detail="HCP not found")
    
    # Process products discussed from notes if not provided
    products_discussed = interaction.products_discussed
    if not products_discussed:
        prods = db.query(models.Product).all()
        found = []
        for p in prods:
            if p.name.lower() in interaction.notes.lower():
                found.append(p.name)
        products_discussed = ",".join(found) if found else "None"

    # Quick sentiment scoring if not provided
    sentiment = interaction.sentiment or "Neutral"
    if not interaction.sentiment:
        pos_words = ["happy", "interested", "good", "great", "excellent", "impressed", "agreed", "positive"]
        neg_words = ["unhappy", "dislike", "skeptical", "concerned", "refused", "no interest", "busy", "poor"]
        notes_lower = interaction.notes.lower()
        pos_count = sum(1 for w in pos_words if w in notes_lower)
        neg_count = sum(1 for w in neg_words if w in notes_lower)
        if pos_count > neg_count:
            sentiment = "Positive"
        elif neg_count > pos_count:
            sentiment = "Negative"

    # Summary fallback
    summary = interaction.summary or (interaction.notes[:200] + "..." if len(interaction.notes) > 200 else interaction.notes)

    # Next steps fallback
    next_steps = interaction.next_steps or "None"

    # Update HCP sentiment
    hcp.recent_sentiment = sentiment

    db_interaction = models.Interaction(
        hcp_id=interaction.hcp_id,
        date=interaction.date,
        channel=interaction.channel,
        notes=interaction.notes,
        summary=summary,
        sentiment=sentiment,
        next_steps=next_steps,
        products_discussed=products_discussed
    )
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

@app.put("/api/interactions/{interaction_id}", response_model=schemas.InteractionResponse)
def update_interaction(interaction_id: int, interaction_data: schemas.InteractionUpdate, db: Session = Depends(get_db)):
    db_interaction = db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()
    if not db_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
        
    for key, value in interaction_data.model_dump(exclude_unset=True).items():
        setattr(db_interaction, key, value)
        
    # If sentiment is updated, update HCP's overall status
    if interaction_data.sentiment:
        hcp = db.query(models.HCP).filter(models.HCP.id == db_interaction.hcp_id).first()
        if hcp:
            hcp.recent_sentiment = interaction_data.sentiment
            
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

# --- Task Endpoints ---
@app.get("/api/tasks", response_model=List[schemas.FollowUpTaskResponse])
def get_tasks(hcp_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.FollowUpTask)
    if hcp_id is not None:
        query = query.filter(models.FollowUpTask.hcp_id == hcp_id)
    return query.order_by(models.FollowUpTask.due_date.asc()).all()

@app.post("/api/tasks", response_model=schemas.FollowUpTaskResponse)
def create_task(task: schemas.FollowUpTaskCreate, db: Session = Depends(get_db)):
    hcp = db.query(models.HCP).filter(models.HCP.id == task.hcp_id).first()
    if not hcp:
        raise HTTPException(status_code=404, detail="HCP not found")
        
    db_task = models.FollowUpTask(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.put("/api/tasks/{task_id}", response_model=schemas.FollowUpTaskResponse)
def update_task(task_id: int, status: str, db: Session = Depends(get_db)):
    db_task = db.query(models.FollowUpTask).filter(models.FollowUpTask.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db_task.status = status
    db.commit()
    db.refresh(db_task)
    return db_task

# --- AI Agent / Chat Endpoint ---
@app.post("/api/chat", response_model=schemas.ChatResponse)
def chat_endpoint(request: schemas.ChatRequest):
    try:
        result = chat_with_agent(
            message=request.message,
            hcp_id=request.hcp_id,
            history=request.chat_history
        )
        return schemas.ChatResponse(
            response=result["response"],
            suggested_actions=result["suggested_actions"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Agent error: {str(e)}")

from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import List, Optional

# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    therapeutic_area: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    class Config:
        from_attributes = True

# --- FollowUpTask Schemas ---
class FollowUpTaskBase(BaseModel):
    description: str
    due_date: date
    status: str = "Pending"

class FollowUpTaskCreate(FollowUpTaskBase):
    hcp_id: int

class FollowUpTaskResponse(FollowUpTaskBase):
    id: int
    hcp_id: int
    created_at: datetime
    class Config:
        from_attributes = True

# --- Interaction Schemas ---
class InteractionBase(BaseModel):
    date: datetime
    channel: str
    notes: str
    summary: Optional[str] = None
    sentiment: Optional[str] = "Neutral"
    next_steps: Optional[str] = None
    products_discussed: Optional[str] = None
    doctor_rating: Optional[int] = None
    feedback: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None

class InteractionCreate(BaseModel):
    hcp_id: int
    date: datetime = Field(default_factory=datetime.utcnow)
    channel: str
    notes: str
    summary: Optional[str] = None
    sentiment: Optional[str] = "Neutral"
    next_steps: Optional[str] = None
    products_discussed: Optional[str] = None
    doctor_rating: Optional[int] = None
    feedback: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None

class InteractionUpdate(BaseModel):
    date: Optional[datetime] = None
    channel: Optional[str] = None
    notes: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    next_steps: Optional[str] = None
    products_discussed: Optional[str] = None
    doctor_rating: Optional[int] = None
    feedback: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None

class InteractionResponse(InteractionBase):
    id: int
    hcp_id: int
    class Config:
        from_attributes = True

# --- HCP Schemas ---
class HCPBase(BaseModel):
    name: str
    specialty: str
    clinic_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    recent_sentiment: str = "Neutral"

class HCPCreate(HCPBase):
    pass

class HCPResponse(HCPBase):
    id: int
    interactions: List[InteractionResponse] = []
    tasks: List[FollowUpTaskResponse] = []
    class Config:
        from_attributes = True

# --- AI / Chat Schemas ---
class ChatRequest(BaseModel):
    message: str
    hcp_id: int
    chat_history: Optional[List[dict]] = None # List of {"role": "user"/"assistant", "content": "..."}

class ChatResponse(BaseModel):
    response: str
    suggested_actions: Optional[List[dict]] = None # List of action objects like { "type": "log_interaction", "data": {...} }
    agent_state: Optional[dict] = None

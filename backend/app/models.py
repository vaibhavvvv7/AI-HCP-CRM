from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class HCP(Base):
    __tablename__ = "hcps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    specialty = Column(String, nullable=False)
    clinic_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    recent_sentiment = Column(String, default="Neutral")

    interactions = relationship("Interaction", back_populates="hcp", cascade="all, delete-orphan")
    tasks = relationship("FollowUpTask", back_populates="hcp", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    therapeutic_area = Column(String, nullable=True)

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcps.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    channel = Column(String, nullable=False) # e.g. Face-to-Face, Virtual, Phone, Email
    notes = Column(Text, nullable=False)     # Raw transcript/notes
    summary = Column(Text, nullable=True)     # LLM parsed/summarized notes
    sentiment = Column(String, default="Neutral") # LLM derived sentiment
    next_steps = Column(Text, nullable=True) # LLM derived tasks
    products_discussed = Column(String, nullable=True) # JSON or Comma-separated list of product names
    doctor_rating = Column(Integer, nullable=True) # Scale of 1-5
    feedback = Column(Text, nullable=True) # Suggestion or feedback
    attendees = Column(String, nullable=True) # Patient name
    materials_shared = Column(String, nullable=True)
    samples_distributed = Column(String, nullable=True)

    hcp = relationship("HCP", back_populates="interactions")

class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"

    id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcps.id"), nullable=False)
    description = Column(String, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String, default="Pending") # Pending, Completed, Cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    hcp = relationship("HCP", back_populates="tasks")

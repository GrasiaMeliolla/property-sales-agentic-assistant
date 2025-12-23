from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class ProjectBase(BaseModel):
    project_name: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    completion_status: Optional[str] = None
    unit_type: Optional[str] = None
    developer_name: Optional[str] = None
    price_usd: Optional[float] = None
    area_sqm: Optional[float] = None
    property_type: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    completion_date: Optional[str] = None
    features: Optional[List[str]] = []
    facilities: Optional[List[str]] = []
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    id: UUID
    project_name: str
    city: Optional[str] = None
    country: Optional[str] = None
    price_usd: Optional[float] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None

    class Config:
        from_attributes = True


class LeadBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = {}


class LeadCreate(LeadBase):
    conversation_id: Optional[UUID] = None


class LeadResponse(LeadBase):
    id: UUID
    conversation_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BookingBase(BaseModel):
    project_id: UUID
    preferred_date: Optional[datetime] = None
    notes: Optional[str] = None


class BookingCreate(BookingBase):
    lead_id: UUID


class BookingResponse(BookingBase):
    id: UUID
    lead_id: UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    pass


class ConversationResponse(BaseModel):
    id: UUID
    status: str
    context: Optional[Dict[str, Any]] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    role: str
    content: str
    extra_data: Optional[Dict[str, Any]] = {}


class MessageCreate(MessageBase):
    conversation_id: UUID


class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: UUID


class ChatResponse(BaseModel):
    response: str
    conversation_id: UUID
    recommended_projects: Optional[List[ProjectSummary]] = None
    metadata: Optional[Dict[str, Any]] = None


class UserPreferences(BaseModel):
    location: Optional[str] = None
    city: Optional[str] = None
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None
    other_requirements: Optional[List[str]] = []

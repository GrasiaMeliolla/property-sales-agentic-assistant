"""Pydantic schemas for API request/response."""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from ninja import Schema


class ConversationCreateSchema(Schema):
    """Schema for creating a conversation."""
    pass


class ConversationResponseSchema(Schema):
    """Schema for conversation response."""
    id: UUID
    status: str
    context: Dict[str, Any]
    created_at: datetime


class ChatRequestSchema(Schema):
    """Schema for chat request."""
    conversation_id: UUID
    message: str


class ProjectSummarySchema(Schema):
    """Schema for project summary in chat response."""
    id: Optional[UUID] = None
    project_name: str
    city: Optional[str] = None
    country: Optional[str] = None
    price_usd: Optional[float] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None


class ChatMetadataSchema(Schema):
    """Schema for chat metadata."""
    intent: Optional[str] = None
    booking_confirmed: bool = False


class ChatResponseSchema(Schema):
    """Schema for chat response."""
    response: str
    conversation_id: UUID
    recommended_projects: Optional[List[ProjectSummarySchema]] = None
    metadata: Optional[ChatMetadataSchema] = None


class HealthResponseSchema(Schema):
    """Schema for health check response."""
    status: str
    app_name: str
    version: str
    vanna_available: bool


class ErrorSchema(Schema):
    """Schema for error response."""
    detail: str

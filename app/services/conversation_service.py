"""Conversation management service."""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, Lead, Booking, Project
from app.schemas.models import ChatResponse, ProjectSummary

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and related data."""

    async def create_conversation(self, db: AsyncSession) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(context={})
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        logger.info(f"Created conversation: {conversation.id}")
        return conversation

    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """Get conversation messages."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()

        # Return in chronological order
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(messages)
        ]

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        extra_data: Optional[Dict] = None
    ) -> Message:
        """Add a message to conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_data=extra_data or {}
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    async def update_context(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        context: Dict[str, Any]
    ) -> None:
        """Update conversation context."""
        conversation = await self.get_conversation(db, conversation_id)
        if conversation:
            current_context = conversation.context or {}
            current_context.update(context)
            conversation.context = current_context
            await db.commit()

    async def get_or_create_lead(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        lead_info: Optional[Dict] = None
    ) -> Lead:
        """Get or create lead for conversation."""
        result = await db.execute(
            select(Lead).where(Lead.conversation_id == conversation_id)
        )
        lead = result.scalar_one_or_none()

        if not lead:
            lead = Lead(
                conversation_id=conversation_id,
                first_name=lead_info.get("first_name") if lead_info else None,
                last_name=lead_info.get("last_name") if lead_info else None,
                email=lead_info.get("email") if lead_info else None,
                phone=lead_info.get("phone") if lead_info else None,
                preferences={}
            )
            db.add(lead)
            await db.commit()
            await db.refresh(lead)
        elif lead_info:
            # Update with new info
            if lead_info.get("first_name"):
                lead.first_name = lead_info["first_name"]
            if lead_info.get("last_name"):
                lead.last_name = lead_info["last_name"]
            if lead_info.get("email"):
                lead.email = lead_info["email"]
            if lead_info.get("phone"):
                lead.phone = lead_info["phone"]
            await db.commit()
            await db.refresh(lead)

        return lead

    async def update_lead_preferences(
        self,
        db: AsyncSession,
        lead_id: UUID,
        preferences: Dict[str, Any]
    ) -> None:
        """Update lead preferences."""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead:
            current_prefs = lead.preferences or {}
            current_prefs.update(preferences)
            lead.preferences = current_prefs
            await db.commit()

    async def create_booking(
        self,
        db: AsyncSession,
        lead_id: UUID,
        project_id: UUID,
        notes: Optional[str] = None
    ) -> Booking:
        """Create a property visit booking."""
        booking = Booking(
            lead_id=lead_id,
            project_id=project_id,
            status="pending",
            notes=notes
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        logger.info(f"Created booking: {booking.id}")
        return booking

    async def find_project_by_name(
        self,
        db: AsyncSession,
        project_name: str
    ) -> Optional[Project]:
        """Find project by name."""
        result = await db.execute(
            select(Project).where(
                Project.project_name.ilike(f"%{project_name}%")
            ).limit(1)
        )
        return result.scalar_one_or_none()


conversation_service = ConversationService()

"""Conversation management service."""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from proplens.models import Conversation, Message, Lead, Booking, Project

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and related data."""

    def create_conversation(self) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation.objects.create(context={})
        logger.info(f"Created conversation: {conversation.id}")
        return conversation

    def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get conversation by ID."""
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    def get_messages(self, conversation_id: UUID, limit: int = 20) -> List[Dict[str, str]]:
        """Get conversation messages."""
        messages = Message.objects.filter(
            conversation_id=conversation_id
        ).order_by('-created_at')[:limit]

        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(list(messages))
        ]

    def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        extra_data: Optional[Dict] = None
    ) -> Message:
        """Add a message to conversation."""
        message = Message.objects.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_data=extra_data or {}
        )
        return message

    def update_context(self, conversation_id: UUID, context: Dict[str, Any]) -> None:
        """Update conversation context."""
        conversation = self.get_conversation(conversation_id)
        if conversation:
            current_context = conversation.context or {}
            current_context.update(context)
            conversation.context = current_context
            conversation.save()

    def get_or_create_lead(
        self,
        conversation_id: UUID,
        lead_info: Optional[Dict] = None
    ) -> Lead:
        """Get or create lead for conversation."""
        try:
            lead = Lead.objects.get(conversation_id=conversation_id)
            if lead_info:
                if lead_info.get("first_name"):
                    lead.first_name = lead_info["first_name"]
                if lead_info.get("last_name"):
                    lead.last_name = lead_info["last_name"]
                if lead_info.get("email"):
                    lead.email = lead_info["email"]
                if lead_info.get("phone"):
                    lead.phone = lead_info["phone"]
                lead.save()
        except Lead.DoesNotExist:
            lead = Lead.objects.create(
                conversation_id=conversation_id,
                first_name=lead_info.get("first_name") if lead_info else None,
                last_name=lead_info.get("last_name") if lead_info else None,
                email=lead_info.get("email") if lead_info else None,
                phone=lead_info.get("phone") if lead_info else None,
                preferences={}
            )
        return lead

    def update_lead_preferences(self, lead_id: UUID, preferences: Dict[str, Any]) -> None:
        """Update lead preferences."""
        try:
            lead = Lead.objects.get(id=lead_id)
            current_prefs = lead.preferences or {}
            current_prefs.update(preferences)
            lead.preferences = current_prefs
            lead.save()
        except Lead.DoesNotExist:
            pass

    def create_booking(
        self,
        lead_id: UUID,
        project_id: UUID,
        notes: Optional[str] = None
    ) -> Booking:
        """Create a property visit booking."""
        booking = Booking.objects.create(
            lead_id=lead_id,
            project_id=project_id,
            status=Booking.Status.PENDING,
            notes=notes
        )
        logger.info(f"Created booking: {booking.id}")
        return booking

    def find_project_by_name(self, project_name: str) -> Optional[Project]:
        """Find project by name."""
        return Project.objects.filter(
            project_name__icontains=project_name
        ).first()


conversation_service = ConversationService()

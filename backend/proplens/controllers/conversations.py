"""Conversation controller."""
from uuid import UUID
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.exceptions import NotFound

from proplens.schemas import ConversationResponseSchema
from proplens.services.conversation import conversation_service


@api_controller("/conversations", tags=["Conversations"])
class ConversationController:
    """Controller for conversation management."""

    @http_post("", response=ConversationResponseSchema)
    def create_conversation(self):
        """Create a new conversation session."""
        conversation = conversation_service.create_conversation()
        return {
            "id": conversation.id,
            "status": conversation.status,
            "context": conversation.context or {},
            "created_at": conversation.created_at
        }

    @http_get("/{conversation_id}", response=ConversationResponseSchema)
    def get_conversation(self, conversation_id: UUID):
        """Get conversation by ID."""
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise NotFound("Conversation not found")

        return {
            "id": conversation.id,
            "status": conversation.status,
            "context": conversation.context or {},
            "created_at": conversation.created_at
        }

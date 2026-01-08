"""Tests for service layer."""
import uuid
import pytest

from proplens.services.conversation import ConversationService, conversation_service
from proplens.models import Conversation, Message, Lead, Booking, Project


@pytest.mark.django_db
class TestConversationService:
    """Tests for ConversationService."""

    def test_create_conversation(self):
        """Test creating a new conversation."""
        service = ConversationService()
        conversation = service.create_conversation()

        assert conversation is not None
        assert isinstance(conversation.id, uuid.UUID)
        assert conversation.status == 'active'
        assert conversation.context == {}

        conversation.delete()

    def test_get_conversation(self, sample_conversation):
        """Test retrieving an existing conversation."""
        service = ConversationService()
        retrieved = service.get_conversation(sample_conversation.id)

        assert retrieved is not None
        assert retrieved.id == sample_conversation.id

    def test_get_conversation_not_found(self):
        """Test retrieving a non-existent conversation."""
        service = ConversationService()
        fake_id = uuid.uuid4()
        result = service.get_conversation(fake_id)

        assert result is None

    def test_add_message(self, sample_conversation):
        """Test adding a message to conversation."""
        service = ConversationService()
        message = service.add_message(
            conversation_id=sample_conversation.id,
            role="user",
            content="Test message"
        )

        assert message is not None
        assert message.role == "user"
        assert message.content == "Test message"
        assert message.conversation_id == sample_conversation.id

        message.delete()

    def test_add_message_with_extra_data(self, sample_conversation):
        """Test adding a message with extra_data."""
        service = ConversationService()
        extra = {"intent": "greeting", "confidence": 0.9}
        message = service.add_message(
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Hello!",
            extra_data=extra
        )

        assert message.extra_data == extra

        message.delete()

    def test_get_messages(self, sample_conversation):
        """Test retrieving conversation messages."""
        service = ConversationService()

        # Add some messages
        service.add_message(sample_conversation.id, "user", "First")
        service.add_message(sample_conversation.id, "assistant", "Second")
        service.add_message(sample_conversation.id, "user", "Third")

        messages = service.get_messages(sample_conversation.id)

        assert len(messages) >= 3
        assert messages[-3]["content"] == "First"
        assert messages[-2]["content"] == "Second"
        assert messages[-1]["content"] == "Third"

    def test_get_messages_with_limit(self, sample_conversation):
        """Test message retrieval with limit."""
        service = ConversationService()

        # Add more messages than limit
        for i in range(5):
            service.add_message(sample_conversation.id, "user", f"Message {i}")

        messages = service.get_messages(sample_conversation.id, limit=3)
        assert len(messages) == 3

    def test_update_context(self, sample_conversation):
        """Test updating conversation context."""
        service = ConversationService()
        new_context = {"preferences": {"city": "Dubai"}}

        service.update_context(sample_conversation.id, new_context)

        sample_conversation.refresh_from_db()
        assert sample_conversation.context["preferences"]["city"] == "Dubai"

    def test_update_context_merges(self, sample_conversation):
        """Test that context update merges with existing context."""
        service = ConversationService()

        # Set initial context
        service.update_context(sample_conversation.id, {"key1": "value1"})
        # Update with new key
        service.update_context(sample_conversation.id, {"key2": "value2"})

        sample_conversation.refresh_from_db()
        assert sample_conversation.context["key1"] == "value1"
        assert sample_conversation.context["key2"] == "value2"

    def test_get_or_create_lead_new(self, sample_conversation):
        """Test creating a new lead for conversation."""
        service = ConversationService()
        lead_info = {
            "first_name": "Alice",
            "last_name": "Wonder",
            "email": "alice@example.com",
            "phone": "+1112223333"
        }

        lead = service.get_or_create_lead(sample_conversation.id, lead_info)

        assert lead is not None
        assert lead.first_name == "Alice"
        assert lead.email == "alice@example.com"
        assert lead.conversation_id == sample_conversation.id

        lead.delete()

    def test_get_or_create_lead_existing(self, sample_lead, sample_conversation):
        """Test retrieving existing lead and updating info."""
        service = ConversationService()
        new_info = {"phone": "+9999999999"}

        lead = service.get_or_create_lead(sample_conversation.id, new_info)

        assert lead.id == sample_lead.id
        lead.refresh_from_db()
        assert lead.phone == "+9999999999"
        # Original info should be preserved
        assert lead.first_name == "John"

    def test_update_lead_preferences(self, sample_lead):
        """Test updating lead preferences."""
        service = ConversationService()
        new_prefs = {"interested_property": "The OWO", "bedrooms": 4}

        service.update_lead_preferences(sample_lead.id, new_prefs)

        sample_lead.refresh_from_db()
        assert sample_lead.preferences["interested_property"] == "The OWO"
        assert sample_lead.preferences["bedrooms"] == 4
        # Original prefs should be preserved
        assert sample_lead.preferences["city"] == "Dubai"

    def test_update_lead_preferences_nonexistent(self):
        """Test updating preferences for non-existent lead."""
        service = ConversationService()
        fake_id = uuid.uuid4()
        # Should not raise an error
        service.update_lead_preferences(fake_id, {"test": "value"})

    def test_create_booking(self, sample_lead, sample_project):
        """Test creating a booking."""
        service = ConversationService()
        booking = service.create_booking(
            lead_id=sample_lead.id,
            project_id=sample_project.id,
            notes="Test booking notes"
        )

        assert booking is not None
        assert booking.lead_id == sample_lead.id
        assert booking.project_id == sample_project.id
        assert booking.status == Booking.Status.PENDING
        assert booking.notes == "Test booking notes"

        booking.delete()

    def test_find_project_by_name(self, sample_project):
        """Test finding project by name."""
        service = ConversationService()

        # Exact match
        project = service.find_project_by_name("Test Tower Dubai")
        assert project is not None
        assert project.id == sample_project.id

        # Partial match (case-insensitive)
        project = service.find_project_by_name("test tower")
        assert project is not None
        assert project.id == sample_project.id

    def test_find_project_by_name_not_found(self):
        """Test finding non-existent project."""
        service = ConversationService()
        project = service.find_project_by_name("Nonexistent Project")
        assert project is None


@pytest.mark.django_db
class TestConversationServiceSingleton:
    """Test the singleton instance of ConversationService."""

    def test_singleton_instance(self):
        """Test that conversation_service is a singleton."""
        assert conversation_service is not None
        assert isinstance(conversation_service, ConversationService)

    def test_singleton_creates_conversation(self):
        """Test using singleton to create conversation."""
        conversation = conversation_service.create_conversation()
        assert conversation is not None

        # Verify we can retrieve it
        retrieved = conversation_service.get_conversation(conversation.id)
        assert retrieved.id == conversation.id

        conversation.delete()

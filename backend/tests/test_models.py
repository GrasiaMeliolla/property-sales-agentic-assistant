"""Tests for Django ORM models."""
import uuid
import pytest

from proplens.models import Project, Conversation, Lead, Booking, Message


@pytest.mark.django_db
class TestProjectModel:
    """Tests for the Project model."""

    def test_create_project(self, sample_project_data):
        """Test creating a project with all fields."""
        project = Project.objects.create(**sample_project_data)

        assert project.id is not None
        assert isinstance(project.id, uuid.UUID)
        assert project.project_name == "Test Tower Dubai"
        assert project.city == "Dubai"
        assert project.price_usd == 500000.0
        assert project.bedrooms == 3
        assert project.features == ["Pool", "Gym"]

        project.delete()

    def test_project_str_representation(self, sample_project):
        """Test the string representation of a project."""
        assert str(sample_project) == "Test Tower Dubai"

    def test_project_ordering(self, multiple_projects):
        """Test that projects are ordered by created_at descending."""
        projects = list(Project.objects.all())
        # Most recently created should be first
        assert projects[0].project_name == "Miami Penthouse"

    def test_project_with_null_fields(self):
        """Test creating a project with minimal required fields."""
        project = Project.objects.create(project_name="Minimal Project")

        assert project.id is not None
        assert project.city is None
        assert project.price_usd is None
        assert project.features == []

        project.delete()

    def test_project_search_by_city(self, multiple_projects):
        """Test filtering projects by city."""
        dubai_projects = Project.objects.filter(city="Dubai")
        assert dubai_projects.count() >= 1
        assert all(p.city == "Dubai" for p in dubai_projects)

    def test_project_search_by_price_range(self, multiple_projects):
        """Test filtering projects by price range."""
        affordable = Project.objects.filter(price_usd__lte=700000)
        assert affordable.count() >= 1

        expensive = Project.objects.filter(price_usd__gte=1000000)
        assert expensive.count() >= 1


@pytest.mark.django_db
class TestConversationModel:
    """Tests for the Conversation model."""

    def test_create_conversation(self):
        """Test creating a conversation."""
        conversation = Conversation.objects.create()

        assert conversation.id is not None
        assert isinstance(conversation.id, uuid.UUID)
        assert conversation.status == 'active'
        assert conversation.context == {}

        conversation.delete()

    def test_conversation_with_context(self):
        """Test conversation with context data."""
        context = {"preferences": {"city": "Dubai"}, "lead_info": {"name": "John"}}
        conversation = Conversation.objects.create(context=context)

        assert conversation.context == context
        assert conversation.context["preferences"]["city"] == "Dubai"

        conversation.delete()

    def test_conversation_str_representation(self, sample_conversation):
        """Test the string representation of a conversation."""
        assert str(sample_conversation).startswith("Conversation ")


@pytest.mark.django_db
class TestLeadModel:
    """Tests for the Lead model."""

    def test_create_lead(self, sample_conversation):
        """Test creating a lead."""
        lead = Lead.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+9876543210",
            conversation=sample_conversation
        )

        assert lead.id is not None
        assert lead.email == "jane@example.com"
        assert lead.conversation == sample_conversation

        lead.delete()

    def test_lead_str_representation(self, sample_lead):
        """Test the string representation of a lead."""
        assert str(sample_lead) == "John Doe"

    def test_lead_with_preferences(self, sample_lead):
        """Test lead preferences JSON field."""
        assert sample_lead.preferences["city"] == "Dubai"
        assert sample_lead.preferences["max_budget"] == 1000000

    def test_lead_without_name(self, sample_conversation):
        """Test lead string representation without name."""
        lead = Lead.objects.create(
            email="anonymous@example.com",
            conversation=sample_conversation
        )
        # Should show UUID when no name
        assert str(lead) == str(lead.id)

        lead.delete()

    def test_lead_conversation_relationship(self, sample_lead, sample_conversation):
        """Test the one-to-one relationship with conversation."""
        # Access lead from conversation
        assert sample_conversation.lead == sample_lead


@pytest.mark.django_db
class TestBookingModel:
    """Tests for the Booking model."""

    def test_create_booking(self, sample_lead, sample_project):
        """Test creating a booking."""
        booking = Booking.objects.create(
            lead=sample_lead,
            project=sample_project,
            status=Booking.Status.PENDING
        )

        assert booking.id is not None
        assert booking.status == "pending"
        assert booking.lead == sample_lead
        assert booking.project == sample_project

        booking.delete()

    def test_booking_str_representation(self, sample_booking):
        """Test the string representation of a booking."""
        assert "Test Tower Dubai" in str(sample_booking)

    def test_booking_status_choices(self, sample_booking):
        """Test booking status transitions."""
        sample_booking.status = Booking.Status.CONFIRMED
        sample_booking.save()
        sample_booking.refresh_from_db()
        assert sample_booking.status == "confirmed"

        sample_booking.status = Booking.Status.CANCELLED
        sample_booking.save()
        sample_booking.refresh_from_db()
        assert sample_booking.status == "cancelled"

    def test_lead_bookings_relationship(self, sample_booking, sample_lead):
        """Test the foreign key relationship from lead to bookings."""
        assert sample_booking in sample_lead.bookings.all()


@pytest.mark.django_db
class TestMessageModel:
    """Tests for the Message model."""

    def test_create_message(self, sample_conversation):
        """Test creating a message."""
        message = Message.objects.create(
            conversation=sample_conversation,
            role="user",
            content="Hello, looking for a property"
        )

        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello, looking for a property"
        assert message.extra_data == {}

        message.delete()

    def test_message_with_extra_data(self, sample_conversation):
        """Test message with extra_data JSON field."""
        extra = {"intent": "greeting", "confidence": 0.95}
        message = Message.objects.create(
            conversation=sample_conversation,
            role="assistant",
            content="Hi! How can I help?",
            extra_data=extra
        )

        assert message.extra_data["intent"] == "greeting"
        assert message.extra_data["confidence"] == 0.95

        message.delete()

    def test_message_str_representation(self, sample_message):
        """Test the string representation of a message."""
        assert str(sample_message).startswith("user:")

    def test_message_ordering(self, sample_conversation):
        """Test that messages are ordered by created_at ascending."""
        msg1 = Message.objects.create(
            conversation=sample_conversation,
            role="user",
            content="First message"
        )
        msg2 = Message.objects.create(
            conversation=sample_conversation,
            role="assistant",
            content="Second message"
        )

        messages = list(sample_conversation.messages.all())
        assert messages[-2].content == "First message"
        assert messages[-1].content == "Second message"

        msg1.delete()
        msg2.delete()

    def test_conversation_messages_relationship(self, sample_message, sample_conversation):
        """Test the foreign key relationship from conversation to messages."""
        assert sample_message in sample_conversation.messages.all()

    def test_message_role_choices(self, sample_conversation):
        """Test message role validation."""
        user_msg = Message.objects.create(
            conversation=sample_conversation,
            role=Message.Role.USER,
            content="User message"
        )
        assistant_msg = Message.objects.create(
            conversation=sample_conversation,
            role=Message.Role.ASSISTANT,
            content="Assistant message"
        )

        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"

        user_msg.delete()
        assistant_msg.delete()

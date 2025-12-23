"""Database model tests."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Project, Lead, Booking, Conversation, Message


@pytest.mark.asyncio
async def test_create_project(test_db: AsyncSession):
    """Test project creation."""
    project = Project(
        project_name="Test Project",
        bedrooms=2,
        bathrooms=2,
        price_usd=500000,
        city="Dubai",
        country="AE",
        property_type="apartment"
    )
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    assert project.id is not None
    assert project.project_name == "Test Project"
    assert project.bedrooms == 2
    assert project.price_usd == 500000


@pytest.mark.asyncio
async def test_create_conversation_with_messages(test_db: AsyncSession):
    """Test conversation with messages."""
    conversation = Conversation(status="active", context={})
    test_db.add(conversation)
    await test_db.commit()
    await test_db.refresh(conversation)

    # Add messages
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content="Hello"
    )
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Hi there!"
    )
    test_db.add_all([user_msg, assistant_msg])
    await test_db.commit()

    # Query messages
    result = await test_db.execute(
        select(Message).where(Message.conversation_id == conversation.id)
    )
    messages = result.scalars().all()

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_create_lead_with_booking(test_db: AsyncSession):
    """Test lead with booking."""
    # Create project
    project = Project(
        project_name="Luxury Villa",
        price_usd=1000000,
        city="Singapore"
    )
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    # Create lead
    lead = Lead(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        preferences={"city": "Singapore", "bedrooms": 3}
    )
    test_db.add(lead)
    await test_db.commit()
    await test_db.refresh(lead)

    # Create booking
    booking = Booking(
        lead_id=lead.id,
        project_id=project.id,
        status="pending"
    )
    test_db.add(booking)
    await test_db.commit()
    await test_db.refresh(booking)

    assert booking.id is not None
    assert booking.lead_id == lead.id
    assert booking.project_id == project.id
    assert booking.status == "pending"

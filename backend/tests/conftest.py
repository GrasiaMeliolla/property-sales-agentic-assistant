"""Pytest configuration and fixtures for PropLens tests."""
import os
import sys
import uuid
from unittest.mock import Mock, patch, MagicMock
from typing import Generator, Dict, Any

import pytest
import django

# Setup Django settings before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('OPENAI_API_KEY', 'test-api-key')
os.environ.setdefault('TAVILY_API_KEY', 'test-tavily-key')

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from django.test import Client
from proplens.models import Project, Conversation, Lead, Booking, Message


@pytest.fixture
def django_client() -> Client:
    """Django test client for API testing."""
    return Client()


@pytest.fixture
def sample_project_data() -> Dict[str, Any]:
    """Sample project data for testing."""
    return {
        "project_name": "Test Tower Dubai",
        "bedrooms": 3,
        "bathrooms": 2,
        "completion_status": "Ready",
        "unit_type": "Apartment",
        "developer_name": "Test Developer",
        "price_usd": 500000.0,
        "area_sqm": 150.0,
        "property_type": "Apartment",
        "city": "Dubai",
        "country": "UAE",
        "completion_date": "2024-06-01",
        "features": ["Pool", "Gym"],
        "facilities": ["Parking", "Security"],
        "description": "A beautiful test property in Dubai"
    }


@pytest.fixture
def sample_project(sample_project_data) -> Generator[Project, None, None]:
    """Create a sample project for testing."""
    project = Project.objects.create(**sample_project_data)
    yield project
    project.delete()


@pytest.fixture
def sample_conversation() -> Generator[Conversation, None, None]:
    """Create a sample conversation for testing."""
    conversation = Conversation.objects.create(
        status='active',
        context={"test": True}
    )
    yield conversation
    conversation.delete()


@pytest.fixture
def sample_lead(sample_conversation) -> Generator[Lead, None, None]:
    """Create a sample lead for testing."""
    lead = Lead.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        conversation=sample_conversation,
        preferences={"city": "Dubai", "max_budget": 1000000}
    )
    yield lead
    lead.delete()


@pytest.fixture
def sample_booking(sample_lead, sample_project) -> Generator[Booking, None, None]:
    """Create a sample booking for testing."""
    booking = Booking.objects.create(
        lead=sample_lead,
        project=sample_project,
        status=Booking.Status.PENDING,
        notes="Test booking"
    )
    yield booking
    booking.delete()


@pytest.fixture
def sample_message(sample_conversation) -> Generator[Message, None, None]:
    """Create a sample message for testing."""
    message = Message.objects.create(
        conversation=sample_conversation,
        role="user",
        content="Hello, I'm looking for a property",
        extra_data={"intent": "greeting"}
    )
    yield message
    message.delete()


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = Mock()
    mock_response.content = "This is a test response from the AI."
    return mock_response


@pytest.fixture
def mock_llm():
    """Mock LLM for testing without API calls."""
    mock = MagicMock()
    mock.invoke.return_value = Mock(content='{"intent": "greeting", "confidence": 0.9}')
    return mock


@pytest.fixture
def mock_tavily_client():
    """Mock Tavily client for web search testing."""
    mock = MagicMock()
    mock.search.return_value = {
        "results": [
            {
                "title": "Test School Dubai",
                "url": "https://example.com/school",
                "content": "A great international school in Dubai."
            }
        ]
    }
    mock.extract.return_value = {
        "results": [
            {
                "url": "https://example.com/school",
                "raw_content": "Detailed content about the school..."
            }
        ]
    }
    return mock


@pytest.fixture
def mock_google_search():
    """Mock Google Custom Search service."""
    mock_service = MagicMock()
    mock_service.cse().list().execute.return_value = {
        "items": [
            {
                "title": "Test Result",
                "snippet": "Test snippet",
                "link": "https://example.com/result"
            }
        ]
    }
    return mock_service


@pytest.fixture
def sample_messages_history():
    """Sample conversation history for testing."""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! I'm Silvy, how can I help you today?"},
        {"role": "user", "content": "I'm looking for a property in Dubai"},
        {"role": "assistant", "content": "Great choice! What's your budget range?"}
    ]


@pytest.fixture
def sample_preferences():
    """Sample user preferences for testing."""
    return {
        "city": "Dubai",
        "max_budget": 1000000,
        "min_budget": 500000,
        "bedrooms": 3,
        "property_type": "Apartment"
    }


@pytest.fixture
def sample_lead_info():
    """Sample lead info for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "+1234567890"
    }


@pytest.fixture
def multiple_projects() -> Generator[list, None, None]:
    """Create multiple projects for search testing."""
    projects_data = [
        {
            "project_name": "Luxury Tower Dubai",
            "city": "Dubai",
            "country": "UAE",
            "price_usd": 800000,
            "bedrooms": 3,
            "property_type": "Apartment"
        },
        {
            "project_name": "Beach Villa Phuket",
            "city": "Phuket",
            "country": "Thailand",
            "price_usd": 600000,
            "bedrooms": 4,
            "property_type": "Villa"
        },
        {
            "project_name": "Miami Penthouse",
            "city": "Miami",
            "country": "USA",
            "price_usd": 1200000,
            "bedrooms": 2,
            "property_type": "Penthouse"
        }
    ]

    projects = []
    for data in projects_data:
        project = Project.objects.create(**data)
        projects.append(project)

    yield projects

    for project in projects:
        project.delete()


# Cleanup fixture to ensure database is clean between tests
@pytest.fixture(autouse=True)
def cleanup_db():
    """Cleanup database after each test."""
    yield
    # Cleanup is handled by individual fixture teardowns

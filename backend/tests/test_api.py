"""Tests for API endpoints using Django Ninja Extra."""
import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, django_client):
        """Test health check returns 200 and correct structure."""
        response = django_client.get('/api/health')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'app_name' in data
        assert 'version' in data
        assert 'vanna_available' in data

    def test_health_check_response_fields(self, django_client):
        """Test health check response contains all expected fields."""
        response = django_client.get('/api/health')
        data = response.json()

        assert data['app_name'] == 'PropLens API'
        assert data['version'] == '1.0.0'
        assert isinstance(data['vanna_available'], bool)


@pytest.mark.django_db
class TestConversationsEndpoint:
    """Tests for conversation management endpoints."""

    def test_create_conversation(self, django_client):
        """Test creating a new conversation."""
        response = django_client.post(
            '/api/conversations',
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert data['status'] == 'active'
        assert 'context' in data
        assert 'created_at' in data

    def test_get_conversation(self, django_client, sample_conversation):
        """Test retrieving an existing conversation."""
        response = django_client.get(f'/api/conversations/{sample_conversation.id}')

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == str(sample_conversation.id)
        assert data['status'] == 'active'

    def test_get_conversation_not_found(self, django_client):
        """Test retrieving non-existent conversation returns 404."""
        fake_id = uuid.uuid4()
        response = django_client.get(f'/api/conversations/{fake_id}')

        assert response.status_code == 404

    def test_conversation_context_preserved(self, django_client, sample_conversation):
        """Test that conversation context is properly returned."""
        # Update context
        sample_conversation.context = {"test_key": "test_value"}
        sample_conversation.save()

        response = django_client.get(f'/api/conversations/{sample_conversation.id}')
        data = response.json()

        assert data['context']['test_key'] == 'test_value'


@pytest.mark.django_db
class TestAgentsChatEndpoint:
    """Tests for agent chat endpoints."""

    @patch('proplens.controllers.agents.property_agent')
    def test_chat_endpoint(self, mock_agent, django_client, sample_conversation):
        """Test the non-streaming chat endpoint."""
        mock_agent.process.return_value = {
            "response": "Hello! How can I help you find a property?",
            "intent": "greeting",
            "preferences": {},
            "lead_info": {},
            "recommended_properties": [],
            "interested_properties": [],
            "booking_confirmed": False,
            "booking_project": None
        }

        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({
                "conversation_id": str(sample_conversation.id),
                "message": "Hello"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert 'response' in data
        assert data['conversation_id'] == str(sample_conversation.id)

    @patch('proplens.controllers.agents.property_agent')
    def test_chat_with_properties(self, mock_agent, django_client, sample_conversation):
        """Test chat endpoint with property recommendations."""
        mock_agent.process.return_value = {
            "response": "Here are some properties in Dubai:",
            "intent": "searching_properties",
            "preferences": {"city": "Dubai"},
            "lead_info": {},
            "recommended_properties": [
                {
                    "id": str(uuid.uuid4()),
                    "project_name": "Test Property",
                    "city": "Dubai",
                    "country": "UAE",
                    "price_usd": 500000,
                    "bedrooms": 3,
                    "property_type": "Apartment"
                }
            ],
            "interested_properties": [],
            "booking_confirmed": False,
            "booking_project": None
        }

        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({
                "conversation_id": str(sample_conversation.id),
                "message": "Show me properties in Dubai"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['recommended_projects'] is not None
        assert len(data['recommended_projects']) == 1
        assert data['recommended_projects'][0]['project_name'] == "Test Property"

    def test_chat_conversation_not_found(self, django_client):
        """Test chat with non-existent conversation returns 404."""
        fake_id = uuid.uuid4()
        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({
                "conversation_id": str(fake_id),
                "message": "Hello"
            }),
            content_type='application/json'
        )

        assert response.status_code == 404

    @patch('proplens.controllers.agents.property_agent')
    def test_chat_metadata(self, mock_agent, django_client, sample_conversation):
        """Test chat response includes metadata."""
        mock_agent.process.return_value = {
            "response": "Booking confirmed!",
            "intent": "collecting_lead_info",
            "preferences": {},
            "lead_info": {"first_name": "John", "email": "john@test.com"},
            "recommended_properties": [],
            "interested_properties": [],
            "booking_confirmed": True,
            "booking_project": "Test Property"
        }

        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({
                "conversation_id": str(sample_conversation.id),
                "message": "My name is John, email john@test.com"
            }),
            content_type='application/json'
        )

        data = response.json()
        assert data['metadata']['intent'] == "collecting_lead_info"
        assert data['metadata']['booking_confirmed'] is True


@pytest.mark.django_db
class TestAgentsStreamEndpoint:
    """Tests for streaming chat endpoint."""

    @patch('proplens.controllers.agents.property_agent')
    def test_stream_endpoint_headers(self, mock_agent, django_client, sample_conversation):
        """Test streaming endpoint returns correct headers."""

        async def mock_stream(*args, **kwargs):
            yield {"type": "intent", "data": "greeting"}
            yield {"type": "content", "data": "Hello!"}
            yield {"type": "done", "data": {"intent": "greeting"}}

        mock_agent.process_stream = mock_stream

        response = django_client.post(
            '/api/agents/chat/stream',
            data=json.dumps({
                "conversation_id": str(sample_conversation.id),
                "message": "Hello"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/event-stream'
        assert response['Cache-Control'] == 'no-cache'

    def test_stream_conversation_not_found(self, django_client):
        """Test streaming with non-existent conversation returns 404."""
        fake_id = uuid.uuid4()
        response = django_client.post(
            '/api/agents/chat/stream',
            data=json.dumps({
                "conversation_id": str(fake_id),
                "message": "Hello"
            }),
            content_type='application/json'
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestAPIValidation:
    """Tests for API input validation."""

    def test_chat_missing_conversation_id(self, django_client):
        """Test chat without conversation_id."""
        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({"message": "Hello"}),
            content_type='application/json'
        )

        assert response.status_code == 422

    def test_chat_missing_message(self, django_client, sample_conversation):
        """Test chat without message."""
        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({"conversation_id": str(sample_conversation.id)}),
            content_type='application/json'
        )

        assert response.status_code == 422

    def test_chat_invalid_conversation_id_format(self, django_client):
        """Test chat with invalid UUID format."""
        response = django_client.post(
            '/api/agents/chat',
            data=json.dumps({
                "conversation_id": "not-a-uuid",
                "message": "Hello"
            }),
            content_type='application/json'
        )

        assert response.status_code == 422

    def test_get_conversation_invalid_uuid(self, django_client):
        """Test get conversation with invalid UUID."""
        response = django_client.get('/api/conversations/invalid-uuid')

        assert response.status_code == 422

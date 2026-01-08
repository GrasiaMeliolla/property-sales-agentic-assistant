"""Tests for the LangGraph orchestrator and agent logic."""
import json
from unittest.mock import patch, MagicMock, Mock

import pytest

from proplens.agents.orchestrator import (
    PropertySalesAgent,
    IntentClassification,
    extract_json,
    get_property_agent,
    LazyPropertyAgent
)


class TestExtractJson:
    """Tests for the JSON extraction utility."""

    def test_extract_valid_json(self):
        """Test extracting valid JSON."""
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_with_surrounding_text(self):
        """Test extracting JSON with surrounding text."""
        text = 'Here is the result: {"intent": "greeting", "confidence": 0.9} and more text'
        result = extract_json(text)
        assert result["intent"] == "greeting"
        assert result["confidence"] == 0.9

    def test_extract_json_invalid(self):
        """Test extracting from invalid JSON returns empty dict."""
        result = extract_json("This is not JSON at all")
        assert result == {}

    def test_extract_json_whitespace(self):
        """Test extracting JSON with whitespace."""
        result = extract_json('  \n  {"test": true}  \n  ')
        assert result == {"test": True}

    def test_extract_json_nested(self):
        """Test that only simple objects are extracted."""
        # Note: the regex in extract_json only handles simple objects
        text = '{"simple": "object"}'
        result = extract_json(text)
        assert result == {"simple": "object"}


class TestIntentClassification:
    """Tests for the IntentClassification Pydantic model."""

    def test_valid_intent_classification(self):
        """Test creating a valid intent classification."""
        classification = IntentClassification(
            intent="greeting",
            confidence=0.95,
            reasoning="User said hello",
            needs_web_search=False
        )

        assert classification.intent == "greeting"
        assert classification.confidence == 0.95
        assert classification.needs_web_search is False
        assert classification.interested_property is None

    def test_intent_with_property_interest(self):
        """Test intent classification with property interest."""
        classification = IntentClassification(
            intent="answering_question",
            confidence=0.85,
            reasoning="User asking about The OWO",
            needs_web_search=True,
            interested_property="The OWO"
        )

        assert classification.interested_property == "The OWO"
        assert classification.needs_web_search is True

    def test_confidence_bounds(self):
        """Test confidence score validation."""
        # Valid bounds
        low = IntentClassification(
            intent="greeting",
            confidence=0.0,
            reasoning="test"
        )
        high = IntentClassification(
            intent="greeting",
            confidence=1.0,
            reasoning="test"
        )

        assert low.confidence == 0.0
        assert high.confidence == 1.0

    def test_all_valid_intents(self):
        """Test all valid intent types."""
        valid_intents = [
            "greeting",
            "gathering_preferences",
            "searching_properties",
            "answering_question",
            "booking_visit",
            "collecting_lead_info",
            "general_conversation"
        ]

        for intent in valid_intents:
            classification = IntentClassification(
                intent=intent,
                confidence=0.9,
                reasoning="test"
            )
            assert classification.intent == intent


@pytest.mark.django_db
class TestPropertySalesAgent:
    """Tests for the PropertySalesAgent class."""

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_agent_initialization(self, mock_chat_openai):
        """Test agent initializes correctly."""
        mock_chat_openai.return_value = MagicMock()
        agent = PropertySalesAgent()

        assert agent.llm is not None
        assert agent.streaming_llm is not None
        assert agent.graph is not None

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_route_by_intent(self, mock_chat_openai):
        """Test intent routing logic."""
        mock_chat_openai.return_value = MagicMock()
        agent = PropertySalesAgent()

        test_cases = [
            ({"intent": "greeting"}, "greeting"),
            ({"intent": "searching_properties"}, "searching_properties"),
            ({"intent": "booking_visit"}, "booking_visit"),
            ({}, "general_conversation"),  # Default case
        ]

        for state, expected in test_cases:
            result = agent._route_by_intent(state)
            assert result == expected

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_handle_greeting(self, mock_chat_openai):
        """Test greeting handler generates response."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(content="Hello! Welcome to Silver Land Properties!")
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "Hello",
            "messages": []
        }

        result = agent._handle_greeting(state)

        assert "response" in result
        assert result["response"] is not None

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_gather_preferences(self, mock_chat_openai):
        """Test preference gathering extracts preferences."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(
            content='{"city": "Dubai", "max_budget": 1000000}'
        )
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "I'm looking for a property in Dubai under 1 million",
            "preferences": {}
        }

        result = agent._gather_preferences(state)

        assert result["preferences"]["city"] == "Dubai"
        assert result["preferences"]["max_budget"] == 1000000

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_gather_preferences_merges_existing(self, mock_chat_openai):
        """Test preference gathering merges with existing preferences."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(
            content='{"bedrooms": 3}'
        )
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "I need 3 bedrooms",
            "preferences": {"city": "Dubai"}  # Existing pref
        }

        result = agent._gather_preferences(state)

        # Both old and new prefs should exist
        assert result["preferences"]["city"] == "Dubai"
        assert result["preferences"]["bedrooms"] == 3

    @patch('proplens.agents.orchestrator.sql_tool')
    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_search_properties(self, mock_chat_openai, mock_sql_tool):
        """Test property search returns results."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(content='{"city": null}')
        mock_chat_openai.return_value = mock_llm

        mock_sql_tool.search_properties.return_value = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "project_name": "Test Tower",
                "city": "Dubai",
                "price_usd": 500000,
                "bedrooms": 3
            }
        ]

        agent = PropertySalesAgent()
        state = {
            "user_message": "Show me properties",
            "preferences": {"city": "Dubai"},
            "messages": []
        }

        result = agent._search_properties(state)

        assert len(result["recommended_properties"]) == 1
        assert result["recommended_properties"][0].project_name == "Test Tower"

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_handle_booking(self, mock_chat_openai):
        """Test booking handler sets up booking state."""
        mock_chat_openai.return_value = MagicMock()

        agent = PropertySalesAgent()
        state = {
            "user_message": "I want to book a visit",
            "recommended_properties": [
                {"project_name": "Test Property", "city": "Dubai"}
            ],
            "lead_info": {}
        }

        result = agent._handle_booking(state)

        assert result["booking_project"] == "Test Property"
        assert result["needs_more_info"] is True
        assert "name" in result["missing_preferences"]

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_collect_lead_info(self, mock_chat_openai):
        """Test lead info collection."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(
            content='{"first_name": "John", "email": "john@test.com"}'
        )
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "My name is John, email john@test.com",
            "lead_info": {},
            "recommended_properties": [{"project_name": "Test Property"}]
        }

        result = agent._collect_lead_info(state)

        assert result["lead_info"]["first_name"] == "John"
        assert result["lead_info"]["email"] == "john@test.com"
        assert result["booking_confirmed"] is True

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_collect_lead_info_incomplete(self, mock_chat_openai):
        """Test lead collection with incomplete info."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = Mock(
            content='{"first_name": "John"}'  # No email
        )
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "My name is John",
            "lead_info": {},
            "recommended_properties": [{"project_name": "Test Property"}]
        }

        result = agent._collect_lead_info(state)

        assert result["lead_info"]["first_name"] == "John"
        assert result["booking_confirmed"] is False
        assert "email" in result["missing_preferences"]

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_classify_intent_function_calling(self, mock_chat_openai):
        """Test intent classification uses structured output."""
        mock_llm = MagicMock()

        # Mock the with_structured_output method
        mock_classifier = MagicMock()
        mock_classifier.invoke.return_value = IntentClassification(
            intent="greeting",
            confidence=0.95,
            reasoning="User said hello",
            needs_web_search=False
        )
        mock_llm.with_structured_output.return_value = mock_classifier
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "Hello",
            "messages": []
        }

        result = agent._classify_intent(state)

        assert result["intent"] == "greeting"
        mock_llm.with_structured_output.assert_called_once_with(IntentClassification)

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_classify_intent_with_property_interest(self, mock_chat_openai):
        """Test intent classification tracks property interest."""
        mock_llm = MagicMock()

        mock_classifier = MagicMock()
        mock_classifier.invoke.return_value = IntentClassification(
            intent="answering_question",
            confidence=0.90,
            reasoning="User asking about The OWO",
            needs_web_search=True,
            interested_property="The OWO"
        )
        mock_llm.with_structured_output.return_value = mock_classifier
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        state = {
            "user_message": "Tell me about schools near The OWO",
            "messages": [],
            "interested_properties": []
        }

        result = agent._classify_intent(state)

        assert result["intent"] == "answering_question"
        assert result["needs_web_search"] is True
        assert "The OWO" in result["interested_properties"]


@pytest.mark.django_db
class TestPropertyAgentProcess:
    """Tests for the main process method."""

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_process_greeting(self, mock_chat_openai):
        """Test processing a greeting message."""
        mock_llm = MagicMock()

        # Mock intent classification
        mock_classifier = MagicMock()
        mock_classifier.invoke.return_value = IntentClassification(
            intent="greeting",
            confidence=0.95,
            reasoning="User greeted",
            needs_web_search=False
        )
        mock_llm.with_structured_output.return_value = mock_classifier
        mock_llm.invoke.return_value = Mock(content="Hello! Welcome!")
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        result = agent.process(
            message="Hello",
            conversation_id="test-conv-id",
            messages_history=[],
            preferences={},
            lead_info={}
        )

        assert "response" in result
        assert result["intent"] == "greeting"

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_process_error_handling(self, mock_chat_openai):
        """Test process handles errors gracefully."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = Exception("API Error")
        mock_chat_openai.return_value = mock_llm

        agent = PropertySalesAgent()
        result = agent.process(
            message="Hello",
            conversation_id="test-conv-id"
        )

        # Should return error response
        assert "error" in result or "apologize" in result.get("response", "").lower()


class TestLazyPropertyAgent:
    """Tests for the lazy loading proxy."""

    @patch('proplens.agents.orchestrator._property_agent', None)
    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_lazy_initialization(self, mock_chat_openai):
        """Test that agent is lazily initialized."""
        mock_chat_openai.return_value = MagicMock()

        lazy = LazyPropertyAgent()
        # Agent shouldn't be created yet
        from proplens.agents import orchestrator
        assert orchestrator._property_agent is None

    @patch('proplens.agents.orchestrator.ChatOpenAI')
    def test_get_property_agent(self, mock_chat_openai):
        """Test get_property_agent singleton."""
        mock_chat_openai.return_value = MagicMock()

        agent1 = get_property_agent()
        agent2 = get_property_agent()

        # Should return same instance
        assert agent1 is agent2

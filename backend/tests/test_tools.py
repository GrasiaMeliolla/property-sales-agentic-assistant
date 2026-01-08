"""Tests for tools (SQL tool and Web search tool)."""
from unittest.mock import patch, MagicMock, Mock

import pytest

from proplens.tools.sql_tool import SQLTool, sql_tool
from proplens.tools.web_search import WebSearchTool, web_search_tool


@pytest.mark.django_db
class TestSQLTool:
    """Tests for the SQL tool."""

    def test_search_properties_by_city(self, multiple_projects):
        """Test searching properties by city."""
        tool = SQLTool()
        results = tool.search_properties(city="Dubai")

        assert len(results) >= 1
        assert all(r["city"] == "Dubai" for r in results)

    def test_search_properties_by_price_range(self, multiple_projects):
        """Test searching properties by price range."""
        tool = SQLTool()
        results = tool.search_properties(min_price=500000, max_price=900000)

        assert len(results) >= 1
        for r in results:
            assert r["price_usd"] >= 500000
            assert r["price_usd"] <= 900000

    def test_search_properties_by_bedrooms(self, multiple_projects):
        """Test searching properties by bedroom count."""
        tool = SQLTool()
        results = tool.search_properties(bedrooms=3)

        assert len(results) >= 1
        assert all(r["bedrooms"] == 3 for r in results)

    def test_search_properties_by_type(self, multiple_projects):
        """Test searching properties by property type."""
        tool = SQLTool()
        results = tool.search_properties(property_type="Apartment")

        assert len(results) >= 1
        assert all(r["property_type"] == "Apartment" for r in results)

    def test_search_properties_combined_filters(self, multiple_projects):
        """Test searching with multiple filters."""
        tool = SQLTool()
        results = tool.search_properties(
            city="Dubai",
            max_price=1000000,
            bedrooms=3
        )

        for r in results:
            assert r["city"] == "Dubai"
            assert r["price_usd"] <= 1000000
            assert r["bedrooms"] == 3

    def test_search_properties_with_limit(self, multiple_projects):
        """Test that limit parameter works."""
        tool = SQLTool()
        results = tool.search_properties(limit=2)

        assert len(results) <= 2

    def test_search_properties_returns_correct_fields(self, sample_project):
        """Test that returned results have expected fields."""
        tool = SQLTool()
        results = tool.search_properties(city="Dubai")

        assert len(results) >= 1
        result = results[0]

        expected_fields = [
            "id", "project_name", "bedrooms", "bathrooms",
            "price_usd", "area_sqm", "city", "country",
            "property_type", "completion_status", "developer_name"
        ]

        for field in expected_fields:
            assert field in result

    def test_search_properties_empty_result(self):
        """Test search returns empty list when no matches."""
        tool = SQLTool()
        results = tool.search_properties(city="NonexistentCity12345")

        assert results == []

    def test_search_properties_case_insensitive(self, multiple_projects):
        """Test that city search is case insensitive."""
        tool = SQLTool()

        results_lower = tool.search_properties(city="dubai")
        results_upper = tool.search_properties(city="DUBAI")
        results_mixed = tool.search_properties(city="DuBaI")

        # All should return same count
        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_get_project_details(self, sample_project):
        """Test getting detailed project information."""
        tool = SQLTool()
        details = tool.get_project_details("Test Tower Dubai")

        assert details is not None
        assert details["project_name"] == "Test Tower Dubai"
        assert "features" in details
        assert "facilities" in details
        assert "description" in details

    def test_get_project_details_partial_match(self, sample_project):
        """Test partial name matching for project details."""
        tool = SQLTool()
        details = tool.get_project_details("Test Tower")

        assert details is not None
        assert "Test Tower" in details["project_name"]

    def test_get_project_details_not_found(self):
        """Test getting details for non-existent project."""
        tool = SQLTool()
        details = tool.get_project_details("Nonexistent Project XYZ")

        assert details is None

    @patch('proplens.tools.sql_tool.vanna_service')
    def test_query_with_vanna_available(self, mock_vanna):
        """Test query when Vanna AI is available."""
        mock_vanna.is_available = True
        mock_vanna.ask.return_value = {
            "sql": "SELECT * FROM projects",
            "results": [{"project_name": "Test"}]
        }

        tool = SQLTool()
        result = tool.query("Show me all projects")

        mock_vanna.ask.assert_called_once_with("Show me all projects")
        assert result["results"] == [{"project_name": "Test"}]

    @patch('proplens.tools.sql_tool.vanna_service')
    def test_query_with_vanna_unavailable(self, mock_vanna):
        """Test query when Vanna AI is not available."""
        mock_vanna.is_available = False

        tool = SQLTool()
        result = tool.query("Show me all projects")

        assert "error" in result
        assert result["results"] is None

    def test_sql_tool_singleton(self):
        """Test that sql_tool is a singleton instance."""
        assert sql_tool is not None
        assert isinstance(sql_tool, SQLTool)


class TestWebSearchTool:
    """Tests for the web search tool."""

    @patch('proplens.tools.web_search.settings')
    def test_initialization_google_enabled(self, mock_settings):
        """Test tool initialization with Google enabled."""
        mock_settings.GOOGLE_SEARCH_ENABLED = True
        mock_settings.GOOGLE_SEARCH_API_KEY = "test-api-key"
        mock_settings.GOOGLE_SEARCH_CSE_ID = "test-cse-id"
        mock_settings.TAVILY_API_KEY = "test-tavily-key"

        tool = WebSearchTool()

        assert tool.google_enabled is True
        assert tool.tavily_enabled is True

    @patch('proplens.tools.web_search.settings')
    def test_initialization_google_disabled(self, mock_settings):
        """Test tool initialization with Google disabled."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = "test-tavily-key"

        tool = WebSearchTool()

        assert tool.google_enabled is False
        assert tool.tavily_enabled is True

    @patch('proplens.tools.web_search.settings')
    def test_tavily_client_lazy_init(self, mock_settings):
        """Test Tavily client is lazily initialized."""
        mock_settings.TAVILY_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""

        tool = WebSearchTool()

        # Client should not be initialized yet
        assert tool._tavily_client is None

    @patch('proplens.tools.web_search.settings')
    def test_google_service_lazy_init(self, mock_settings):
        """Test Google service is lazily initialized."""
        mock_settings.GOOGLE_SEARCH_ENABLED = True
        mock_settings.GOOGLE_SEARCH_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_CSE_ID = "test-cse"
        mock_settings.TAVILY_API_KEY = ""

        tool = WebSearchTool()

        # Service should not be initialized yet
        assert tool._google_service is None

    @patch('proplens.tools.web_search.settings')
    def test_google_search(self, mock_settings, mock_google_search):
        """Test Google Custom Search."""
        mock_settings.GOOGLE_SEARCH_ENABLED = True
        mock_settings.GOOGLE_SEARCH_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_CSE_ID = "test-cse"
        mock_settings.TAVILY_API_KEY = ""

        tool = WebSearchTool()
        tool._google_service = mock_google_search

        results = tool.google_search("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Result"
        assert results[0]["url"] == "https://example.com/result"

    @patch('proplens.tools.web_search.settings')
    def test_google_search_no_service(self, mock_settings):
        """Test Google search returns empty when service unavailable."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = ""

        tool = WebSearchTool()
        results = tool.google_search("test query")

        assert results == []

    @patch('proplens.tools.web_search.settings')
    def test_tavily_search(self, mock_settings, mock_tavily_client):
        """Test Tavily search."""
        mock_settings.TAVILY_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        results = tool.tavily_search("schools in dubai")

        assert len(results) == 1
        assert results[0]["title"] == "Test School Dubai"

    @patch('proplens.tools.web_search.settings')
    def test_tavily_extract(self, mock_settings, mock_tavily_client):
        """Test Tavily URL extraction."""
        mock_settings.TAVILY_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        extracted = tool.tavily_extract(["https://example.com/school"])

        assert "https://example.com/school" in extracted
        assert "Detailed content" in extracted["https://example.com/school"]

    @patch('proplens.tools.web_search.settings')
    def test_search_and_extract_with_google(self, mock_settings, mock_google_search, mock_tavily_client):
        """Test combined search and extract using Google."""
        mock_settings.GOOGLE_SEARCH_ENABLED = True
        mock_settings.GOOGLE_SEARCH_API_KEY = "test-key"
        mock_settings.GOOGLE_SEARCH_CSE_ID = "test-cse"
        mock_settings.TAVILY_API_KEY = "test-tavily"

        tool = WebSearchTool()
        tool._google_service = mock_google_search
        tool._tavily_client = mock_tavily_client

        result = tool.search_and_extract("best schools dubai")

        assert result is not None
        # Should contain extracted content
        assert "Source:" in result or "Detailed content" in result

    @patch('proplens.tools.web_search.settings')
    def test_search_and_extract_fallback_to_tavily(self, mock_settings, mock_tavily_client):
        """Test fallback to Tavily search when Google disabled."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = "test-tavily"

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        result = tool.search_and_extract("schools in dubai")

        # Should use Tavily search and extract
        mock_tavily_client.search.assert_called()

    @patch('proplens.tools.web_search.settings')
    def test_search_context_with_property(self, mock_settings, mock_tavily_client):
        """Test context search with property name."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = "test-tavily"

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        result = tool.search_context(
            question="schools nearby",
            property_name="The OWO",
            city="London"
        )

        # Should construct query with property + city + question
        mock_tavily_client.search.assert_called()

    @patch('proplens.tools.web_search.settings')
    def test_search_context_fallback_to_city(self, mock_settings, mock_tavily_client):
        """Test context search falls back to city when property search fails."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = "test-tavily"

        # First call returns empty, second returns results
        mock_tavily_client.search.side_effect = [
            {"results": []},  # Property search fails
            {"results": [{"title": "Result", "url": "http://test.com", "content": "City result"}]}
        ]
        mock_tavily_client.extract.return_value = {"results": []}

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        result = tool.search_context(
            question="best restaurants",
            property_name="Some Property",
            city="Dubai"
        )

        # Should have called search twice (property + city fallback)
        assert mock_tavily_client.search.call_count == 2

    @patch('proplens.tools.web_search.settings')
    def test_search_no_urls_found(self, mock_settings, mock_tavily_client):
        """Test handling when no URLs are found."""
        mock_settings.GOOGLE_SEARCH_ENABLED = False
        mock_settings.GOOGLE_SEARCH_API_KEY = ""
        mock_settings.GOOGLE_SEARCH_CSE_ID = ""
        mock_settings.TAVILY_API_KEY = "test-tavily"

        mock_tavily_client.search.return_value = {"results": []}

        tool = WebSearchTool()
        tool._tavily_client = mock_tavily_client

        result = tool.search_and_extract("impossible query xyz123")

        assert result is None

    def test_web_search_tool_singleton(self):
        """Test that web_search_tool is a singleton instance."""
        assert web_search_tool is not None
        assert isinstance(web_search_tool, WebSearchTool)


@pytest.mark.django_db
class TestSQLToolAsync:
    """Tests for async SQL tool methods."""

    @pytest.mark.asyncio
    async def test_search_properties_async(self, multiple_projects):
        """Test async property search."""
        tool = SQLTool()
        results = await tool.search_properties_async(city="Dubai")

        assert len(results) >= 1
        assert all(r["city"] == "Dubai" for r in results)

    @pytest.mark.asyncio
    @patch('proplens.tools.sql_tool.vanna_service')
    async def test_query_async(self, mock_vanna):
        """Test async query method."""
        mock_vanna.is_available = True
        mock_vanna.ask.return_value = {
            "sql": "SELECT 1",
            "results": [{"test": True}]
        }

        tool = SQLTool()
        result = await tool.query_async("Test query")

        assert result["results"] == [{"test": True}]

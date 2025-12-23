"""Web search tool using Tavily API."""
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Tool for web search using Tavily API."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy initialize Tavily client."""
        if self._client is None and settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
        return self._client

    def search(self, query: str, max_results: int = 5) -> list:
        """Perform a web search."""
        client = self._get_client()
        if not client:
            logger.warning("Tavily client not available")
            return []

        try:
            response = client.search(query=query, max_results=max_results)
            return response.get("results", [])
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def search_context(
        self,
        question: str,
        property_name: Optional[str] = None
    ) -> Optional[str]:
        """Search for context about a property or location."""
        if property_name:
            query = f"{property_name} property area neighborhood amenities"
        else:
            query = question

        results = self.search(query, max_results=3)

        if not results:
            return None

        context_parts = []
        for result in results:
            title = result.get("title", "")
            content = result.get("content", "")
            if content:
                context_parts.append(f"**{title}**: {content[:300]}")

        return "\n\n".join(context_parts) if context_parts else None


web_search_tool = WebSearchTool()

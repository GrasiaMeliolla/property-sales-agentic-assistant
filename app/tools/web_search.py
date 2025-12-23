"""Web search tool using Tavily API."""
import logging
from typing import Optional, List, Dict, Any

from tavily import TavilyClient

from app.config import settings

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Tool for searching the web using Tavily API."""

    def __init__(self):
        self._client: Optional[TavilyClient] = None

    def _get_client(self) -> TavilyClient:
        if self._client is None:
            if not settings.tavily_api_key:
                raise ValueError("TAVILY_API_KEY not configured")
            self._client = TavilyClient(api_key=settings.tavily_api_key)
        return self._client

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> List[Dict[str, Any]]:
        """
        Search the web for information.

        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: 'basic' or 'advanced'

        Returns:
            List of search results with title, url, and content
        """
        try:
            client = self._get_client()
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth
            )

            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0)
                })

            logger.info(f"Web search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []

    def extract(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Extract content from specific URLs.

        Args:
            urls: List of URLs to extract content from

        Returns:
            List of extracted content
        """
        try:
            client = self._get_client()
            response = client.extract(urls=urls)

            results = []
            for result in response.get("results", []):
                results.append({
                    "url": result.get("url", ""),
                    "raw_content": result.get("raw_content", "")
                })

            logger.info(f"Extracted content from {len(results)} URLs")
            return results

        except Exception as e:
            logger.error(f"URL extraction failed: {e}")
            return []

    def search_context(self, query: str, project_name: Optional[str] = None) -> str:
        """
        Search for context about a property or location.

        Args:
            query: The search query
            project_name: Optional project name to include in search

        Returns:
            Formatted string with search results
        """
        if project_name:
            search_query = f"{project_name} {query}"
        else:
            search_query = query

        results = self.search(search_query, max_results=3)

        if not results:
            return "No additional information found from web search."

        context_parts = ["Web search results:"]
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n{i}. {result['title']}")
            context_parts.append(f"   {result['content'][:300]}...")
            context_parts.append(f"   Source: {result['url']}")

        return "\n".join(context_parts)


web_search_tool = WebSearchTool()

"""Web search tool using Google Search + Tavily Extract."""
import logging
from typing import Optional, List, Dict, Any

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool with Google Search for URLs and Tavily Extract for content.

    Architecture:
    - Google Search: Better at finding relevant URLs
    - Tavily Extract: Extracts full page content from URLs
    - Fallback: Tavily Search if Google not configured
    """

    def __init__(self):
        self._tavily_client = None
        self._google_service = None

        # Check configurations
        self.google_enabled = bool(
            getattr(settings, 'GOOGLE_SEARCH_ENABLED', False) and
            getattr(settings, 'GOOGLE_SEARCH_API_KEY', '') and
            getattr(settings, 'GOOGLE_SEARCH_CSE_ID', '')
        )
        self.tavily_enabled = bool(getattr(settings, 'TAVILY_API_KEY', ''))

        print(f"[SEARCH] Initialized - Google: {'ON' if self.google_enabled else 'OFF'}, Tavily: {'ON' if self.tavily_enabled else 'OFF'}", flush=True)

    def _get_tavily_client(self):
        """Lazy initialize Tavily client."""
        if self._tavily_client is None and self.tavily_enabled:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            except Exception as e:
                print(f"[TAVILY] Failed to init: {e}", flush=True)
        return self._tavily_client

    def _get_google_service(self):
        """Lazy initialize Google Custom Search service."""
        if self._google_service is None and self.google_enabled:
            try:
                from googleapiclient.discovery import build
                self._google_service = build(
                    "customsearch", "v1",
                    developerKey=settings.GOOGLE_SEARCH_API_KEY,
                    cache_discovery=False
                )
            except Exception as e:
                print(f"[GOOGLE] Failed to init: {e}", flush=True)
        return self._google_service

    def google_search(self, query: str, num: int = 5) -> List[Dict[str, Any]]:
        """Search using Google Custom Search API."""
        service = self._get_google_service()
        if not service:
            return []

        try:
            print(f"[GOOGLE] Searching: '{query}'", flush=True)
            response = service.cse().list(
                q=query,
                cx=settings.GOOGLE_SEARCH_CSE_ID,
                num=min(num, 10)
            ).execute()

            items = response.get("items", [])
            results = []
            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                })

            print(f"[GOOGLE] Found {len(results)} results", flush=True)
            return results
        except Exception as e:
            print(f"[GOOGLE] Search failed: {e}", flush=True)
            return []

    def tavily_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search using Tavily API."""
        client = self._get_tavily_client()
        if not client:
            return []

        try:
            print(f"[TAVILY] Searching: '{query}'", flush=True)
            response = client.search(query=query, max_results=max_results)
            results = response.get("results", [])
            print(f"[TAVILY] Found {len(results)} results", flush=True)
            return results
        except Exception as e:
            print(f"[TAVILY] Search failed: {e}", flush=True)
            return []

    def tavily_extract(self, urls: List[str]) -> Dict[str, str]:
        """Extract full content from URLs using Tavily."""
        client = self._get_tavily_client()
        if not client or not urls:
            return {}

        try:
            print(f"[TAVILY] Extracting {len(urls)} URLs", flush=True)
            response = client.extract(urls=urls)

            extracted = {}
            for result in response.get("results", []):
                url = result.get("url", "")
                content = result.get("raw_content", "")
                if url and content:
                    extracted[url] = content[:2000]  # Limit per URL

            print(f"[TAVILY] Extracted {len(extracted)} pages", flush=True)
            return extracted
        except Exception as e:
            print(f"[TAVILY] Extract failed: {e}", flush=True)
            return {}

    def search_and_extract(self, query: str, max_results: int = 10) -> Optional[str]:
        """
        Search for URLs and return snippets as context.

        Strategy:
        1. Google Search for 10 results with snippets
        2. Return all snippets as context (LLM can use these)
        3. Only extract top 2 URLs with Tavily if snippets are too short
        """
        print(f"[SEARCH] Query: '{query}'", flush=True)

        # Step 1: Get search results with snippets
        if self.google_enabled:
            results = self.google_search(query, num=max_results)
        else:
            results = self.tavily_search(query, max_results=max_results)

        if not results:
            print("[SEARCH] No results found", flush=True)
            return None

        # Step 2: Build context from snippets
        snippet_parts = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            snippet = r.get("snippet", r.get("content", ""))
            url = r.get("url", "")
            if title and snippet:
                snippet_parts.append(f"{i}. **{title}**\n{snippet}\nSource: {url}")

        snippets_text = "\n\n".join(snippet_parts)
        print(f"[SEARCH] Got {len(snippet_parts)} snippets, total length: {len(snippets_text)}", flush=True)

        # Step 3: If snippets are too short, extract full content from top 2 URLs
        if len(snippets_text) < 500 and self.tavily_enabled:
            urls = [r.get("url") for r in results[:2] if r.get("url")]
            if urls:
                print(f"[SEARCH] Snippets short, extracting {len(urls)} URLs", flush=True)
                extracted = self.tavily_extract(urls)
                if extracted:
                    extract_parts = []
                    for url, content in extracted.items():
                        extract_parts.append(f"Source: {url}\n\n{content}")
                    return snippets_text + "\n\n--- DETAILED CONTENT ---\n\n" + "\n\n".join(extract_parts)

        return snippets_text if snippets_text else None

    def _build_search_query(self, question: str, city: Optional[str] = None) -> str:
        """Use LLM to extract optimal search query from user question."""
        try:
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0
            )

            prompt = f"""Extract the best Google search query from this user question.

User question: "{question}"
City context: {city or "unknown"}

Rules:
- Extract ONLY the key search terms
- Remove filler words (find me, give me, show me, before I choose, etc)
- Keep the main topic (school, gym, restaurant, transport, etc)
- Add the city if relevant
- Output ONLY the search query, nothing else

Examples:
- "before i choose, give me options of nearest elementary school to that properties" -> "best elementary schools"
- "find me gym near the property" -> "gyms"
- "what are the transport options nearby" -> "public transport stations"
- "show me restaurants around" -> "restaurants"

Search query:"""

            response = llm.invoke([HumanMessage(content=prompt)])
            query = response.content.strip().strip('"').strip("'")

            # Add city if not already in query
            if city and city.lower() not in query.lower():
                query = f"{query} {city}"

            print(f"[SEARCH] LLM extracted query: '{query}'", flush=True)
            return query

        except Exception as e:
            print(f"[SEARCH] LLM query extraction failed: {e}, using fallback", flush=True)
            # Fallback: just use city + generic terms
            return f"best places {city}" if city else question[:50]

    def search_context(
        self,
        question: str,
        property_name: Optional[str] = None,
        city: Optional[str] = None
    ) -> Optional[str]:
        """
        Search for context based on user's question.

        Strategy:
        1. Use LLM to extract optimal search query
        2. If property mentioned: search with property + query
        3. Fallback: search with city + query
        """
        print(f"[SEARCH] Context search: question='{question}', property='{property_name}', city='{city}'", flush=True)

        # Use LLM to build optimal search query
        search_query = self._build_search_query(question, city)

        # Try with property name first if provided
        if property_name:
            query = f"{property_name} {search_query}".strip()
            print(f"[SEARCH] Query (with property): '{query}'", flush=True)
            result = self.search_and_extract(query, max_results=10)

            if result and len(result) > 300:
                return result

            print("[SEARCH] Property search insufficient, trying without property", flush=True)

        # Search with the LLM-extracted query (already includes city)
        print(f"[SEARCH] Query: '{search_query}'", flush=True)
        return self.search_and_extract(search_query, max_results=10)


web_search_tool = WebSearchTool()

"""Agent state definitions."""
from typing import TypedDict, Optional, List, Dict, Any


class PropertyMatch(TypedDict, total=False):
    """Property match from database."""
    id: str
    project_name: str
    city: Optional[str]
    country: Optional[str]
    price_usd: Optional[float]
    bedrooms: Optional[int]
    property_type: Optional[str]
    description: Optional[str]


class AgentState(TypedDict, total=False):
    """State for the property sales agent."""
    user_message: str
    conversation_id: str
    messages: List[Dict[str, str]]
    preferences: Dict[str, Any]
    lead_info: Dict[str, Any]
    intent: str
    needs_web_search: bool  # Flag from intent classification for web search
    needs_property_first: bool  # Flag when user provides name before property context
    interested_properties: List[str]  # Properties user explicitly expressed interest in
    context_property: Optional[str]  # Property user was last discussing/asking about
    recommended_properties: List[PropertyMatch]
    selected_property: Optional[PropertyMatch]
    sql_results: Optional[List[Dict]]
    web_search_results: Optional[str]
    response: str
    booking_confirmed: bool
    booking_project: Optional[str]
    needs_more_info: bool
    missing_preferences: List[str]
    error: Optional[str]

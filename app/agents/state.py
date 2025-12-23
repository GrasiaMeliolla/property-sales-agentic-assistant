"""Agent state definitions for LangGraph."""
from typing import TypedDict, Optional, List, Dict, Any, Literal
from uuid import UUID


class UserPreferences(TypedDict, total=False):
    location: Optional[str]
    city: Optional[str]
    min_budget: Optional[float]
    max_budget: Optional[float]
    bedrooms: Optional[int]
    property_type: Optional[str]
    other_requirements: List[str]


class LeadInfo(TypedDict, total=False):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]


class PropertyMatch(TypedDict):
    id: str
    project_name: str
    city: Optional[str]
    country: Optional[str]
    price_usd: Optional[float]
    bedrooms: Optional[int]
    property_type: Optional[str]
    description: Optional[str]


class AgentState(TypedDict, total=False):
    # Input
    user_message: str
    conversation_id: str

    # Conversation history
    messages: List[Dict[str, str]]

    # User information
    preferences: UserPreferences
    lead_info: LeadInfo

    # Current intent
    intent: Literal[
        "greeting",
        "gathering_preferences",
        "searching_properties",
        "answering_question",
        "booking_visit",
        "collecting_lead_info",
        "general_conversation"
    ]

    # Properties
    recommended_properties: List[PropertyMatch]
    selected_property: Optional[PropertyMatch]

    # Web search results
    web_search_results: Optional[str]

    # SQL query results
    sql_results: Optional[List[Dict[str, Any]]]

    # Response
    response: str

    # Booking
    booking_confirmed: bool
    booking_project: Optional[str]

    # Metadata
    needs_more_info: bool
    missing_preferences: List[str]
    error: Optional[str]

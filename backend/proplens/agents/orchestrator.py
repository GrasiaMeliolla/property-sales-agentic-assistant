"""LangGraph orchestrator for property sales agent."""
import json
import re
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator

from django.conf import settings
from asgiref.sync import sync_to_async
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from proplens.agents.state import AgentState, PropertyMatch
from proplens.agents.prompts import (
    SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    PREFERENCE_EXTRACTION_PROMPT,
    PROPERTY_RECOMMENDATION_PROMPT,
    QUESTION_ANSWERING_PROMPT,
    BOOKING_PROMPT,
    LEAD_EXTRACTION_PROMPT,
    GENERAL_RESPONSE_PROMPT
)
from proplens.tools.sql_tool import sql_tool
from proplens.tools.web_search import web_search_tool

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response that might contain extra text."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {}


class PropertySalesAgent:
    """LangGraph-based property sales agent."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.7
        )
        self.streaming_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.7,
            streaming=True
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("handle_greeting", self._handle_greeting)
        workflow.add_node("gather_preferences", self._gather_preferences)
        workflow.add_node("search_properties", self._search_properties)
        workflow.add_node("answer_question", self._answer_question)
        workflow.add_node("handle_booking", self._handle_booking)
        workflow.add_node("collect_lead_info", self._collect_lead_info)
        workflow.add_node("generate_response", self._generate_response)

        workflow.set_entry_point("classify_intent")

        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "greeting": "handle_greeting",
                "gathering_preferences": "gather_preferences",
                "searching_properties": "search_properties",
                "answering_question": "answer_question",
                "booking_visit": "handle_booking",
                "collecting_lead_info": "collect_lead_info",
                "general_conversation": "generate_response"
            }
        )

        workflow.add_edge("handle_greeting", "generate_response")
        workflow.add_edge("gather_preferences", "search_properties")
        workflow.add_edge("search_properties", "generate_response")
        workflow.add_edge("answer_question", "generate_response")
        workflow.add_edge("handle_booking", "generate_response")
        workflow.add_edge("collect_lead_info", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _classify_intent(self, state: AgentState) -> AgentState:
        """Classify user intent."""
        message = state.get("user_message", "")
        messages_history = state.get("messages", [])

        context = "No previous context"
        if messages_history:
            recent = messages_history[-4:] if len(messages_history) > 4 else messages_history
            context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

        prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message, context=context)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        intent = response.content.strip().lower().replace(".", "").replace(",", "")

        valid_intents = [
            "greeting", "gathering_preferences", "searching_properties",
            "answering_question", "booking_visit", "collecting_lead_info",
            "general_conversation"
        ]

        found_intent = "general_conversation"
        for valid in valid_intents:
            if valid in intent:
                found_intent = valid
                break

        logger.info(f"Classified intent: {found_intent}")
        state["intent"] = found_intent
        return state

    def _route_by_intent(self, state: AgentState) -> str:
        return state.get("intent", "general_conversation")

    def _handle_greeting(self, state: AgentState) -> AgentState:
        """Handle greeting intent."""
        state["response"] = (
            "Hello! I'm **Luna**, your property assistant at Silver Land Properties. "
            "I'm here to help you find your perfect home!\n\n"
            "To get started, could you tell me:\n"
            "- Which **city** are you interested in?\n"
            "- What's your **budget range**?\n"
            "- How many **bedrooms** do you need?"
        )
        return state

    def _gather_preferences(self, state: AgentState) -> AgentState:
        """Extract and update user preferences."""
        message = state.get("user_message", "")
        current_prefs = state.get("preferences", {})

        prompt = PREFERENCE_EXTRACTION_PROMPT.format(
            message=message,
            previous_preferences=json.dumps(current_prefs)
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        new_prefs = extract_json(response.content)

        for key, value in new_prefs.items():
            if value is not None and value != "null":
                current_prefs[key] = value

        state["preferences"] = current_prefs

        missing = []
        if not current_prefs.get("city"):
            missing.append("preferred city/location")
        if not current_prefs.get("max_budget") and not current_prefs.get("min_budget"):
            missing.append("budget range")
        if not current_prefs.get("bedrooms"):
            missing.append("number of bedrooms")

        state["missing_preferences"] = missing
        state["needs_more_info"] = len(missing) > 0

        logger.info(f"Extracted preferences: {current_prefs}, missing: {missing}")
        return state

    def _search_properties(self, state: AgentState) -> AgentState:
        """Search for properties matching preferences."""
        prefs = state.get("preferences", {})

        results = sql_tool.search_properties(
            city=prefs.get("city"),
            min_price=prefs.get("min_budget"),
            max_price=prefs.get("max_budget"),
            bedrooms=prefs.get("bedrooms"),
            property_type=prefs.get("property_type"),
            limit=5
        )

        if results:
            properties = []
            for r in results:
                prop = PropertyMatch(
                    id=str(r.get("id", "")),
                    project_name=r.get("project_name", ""),
                    city=r.get("city"),
                    country=r.get("country"),
                    price_usd=r.get("price_usd"),
                    bedrooms=r.get("bedrooms"),
                    property_type=r.get("property_type"),
                    description=r.get("description", "")[:500] if r.get("description") else None
                )
                properties.append(prop)
            state["recommended_properties"] = properties
            state["sql_results"] = results
        else:
            state["recommended_properties"] = []
            state["sql_results"] = []

        logger.info(f"Found {len(results) if results else 0} matching properties")
        return state

    def _answer_question(self, state: AgentState) -> AgentState:
        """Answer specific questions about properties."""
        message = state.get("user_message", "")

        sql_result = sql_tool.query(message)
        state["sql_results"] = sql_result.get("results")

        web_keywords = ["near", "school", "transport", "area", "neighborhood", "around"]
        needs_web_search = any(kw in message.lower() for kw in web_keywords)

        if needs_web_search and settings.TAVILY_API_KEY:
            project_name = None
            properties = state.get("recommended_properties", [])
            if properties:
                project_name = properties[0].get("project_name")
            web_results = web_search_tool.search_context(message, project_name)
            state["web_search_results"] = web_results
        else:
            state["web_search_results"] = None

        return state

    def _handle_booking(self, state: AgentState) -> AgentState:
        """Handle property visit booking."""
        properties = state.get("recommended_properties", [])
        lead_info = state.get("lead_info", {})

        # Use existing booking_project or get from recommended properties
        if not state.get("booking_project") and properties:
            if isinstance(properties[0], dict):
                state["booking_project"] = properties[0].get("project_name")
            elif hasattr(properties[0], "project_name"):
                state["booking_project"] = properties[0].project_name

        if properties:
            state["selected_property"] = properties[0]

        missing = []
        if not lead_info.get("first_name"):
            missing.append("name")
        if not lead_info.get("email"):
            missing.append("email")

        state["needs_more_info"] = len(missing) > 0
        state["missing_preferences"] = missing

        return state

    def _collect_lead_info(self, state: AgentState) -> AgentState:
        """Collect lead contact information."""
        message = state.get("user_message", "")
        current_lead = state.get("lead_info", {})

        prompt = LEAD_EXTRACTION_PROMPT.format(
            message=message,
            previous_lead_info=json.dumps(current_lead)
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        new_info = extract_json(response.content)

        for key, value in new_info.items():
            if value is not None and value != "null" and value != "":
                current_lead[key] = value

        state["lead_info"] = current_lead

        # Get booking_project from recommended properties if not set
        if not state.get("booking_project"):
            properties = state.get("recommended_properties", [])
            if properties:
                state["booking_project"] = properties[0].get("project_name")

        if current_lead.get("first_name") and current_lead.get("email"):
            state["booking_confirmed"] = True
            state["missing_preferences"] = []
        else:
            state["booking_confirmed"] = False
            missing = []
            if not current_lead.get("first_name"):
                missing.append("name")
            if not current_lead.get("email"):
                missing.append("email")
            state["missing_preferences"] = missing

        return state

    def _generate_response(self, state: AgentState) -> AgentState:
        """Generate final response based on state."""
        intent = state.get("intent")

        if state.get("response"):
            return state

        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        user_message = state.get("user_message", "")

        if intent == "general_conversation":
            context = ""
            for msg in state.get("messages", [])[-4:]:
                context += f"{msg['role']}: {msg['content']}\n"

            prompt = GENERAL_RESPONSE_PROMPT.format(
                message=user_message,
                context=context or "No previous context"
            )
            messages.append(HumanMessage(content=prompt))

        elif intent in ("searching_properties", "gathering_preferences"):
            properties = state.get("recommended_properties", [])
            prefs = state.get("preferences", {})
            missing = state.get("missing_preferences", [])

            if properties:
                props_text = "\n".join([
                    f"- **{p['project_name']}**: ${p.get('price_usd', 0):,.0f}, "
                    f"{p.get('bedrooms', 'N/A')} bed, {p.get('city', 'Unknown')}"
                    for p in properties[:3]
                ])
                prompt = PROPERTY_RECOMMENDATION_PROMPT.format(
                    preferences=json.dumps(prefs, indent=2),
                    properties=props_text
                )
            elif missing:
                prompt = f"""The user is looking for a property.
Current preferences: {json.dumps(prefs)}
We still need: {', '.join(missing)}

Ask about the missing information in a friendly, conversational way."""
            else:
                prompt = """No properties found matching the criteria.
Apologize and ask if they'd like to adjust their requirements or explore different locations."""

            messages.append(HumanMessage(content=prompt))

        elif intent == "answering_question":
            sql_results = state.get("sql_results")
            web_results = state.get("web_search_results", "")

            prompt = QUESTION_ANSWERING_PROMPT.format(
                question=user_message,
                property_info=json.dumps(sql_results, indent=2) if sql_results else "No database results",
                web_results=web_results or "No web search performed"
            )
            messages.append(HumanMessage(content=prompt))

        elif intent in ("booking_visit", "collecting_lead_info"):
            lead_info = state.get("lead_info", {})
            missing = state.get("missing_preferences", [])
            property_name = state.get("booking_project", "the selected property")

            if state.get("booking_confirmed"):
                prompt = f"""Booking confirmed!
Property: {property_name}
Name: {lead_info.get('first_name')} {lead_info.get('last_name', '')}
Email: {lead_info.get('email')}

Confirm the booking enthusiastically. Let them know a representative will contact them soon."""
            else:
                prompt = BOOKING_PROMPT.format(
                    property_name=property_name,
                    lead_info=json.dumps(lead_info),
                    missing_info=', '.join(missing) if missing else "none"
                )
            messages.append(HumanMessage(content=prompt))

        else:
            messages.append(HumanMessage(content=f"User: {user_message}\n\nRespond helpfully."))

        response = self.llm.invoke(messages)
        state["response"] = response.content

        return state

    def process(
        self,
        message: str,
        conversation_id: str,
        messages_history: Optional[List[Dict[str, str]]] = None,
        preferences: Optional[Dict] = None,
        lead_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Process a user message and return response."""

        initial_state: AgentState = {
            "user_message": message,
            "conversation_id": conversation_id,
            "messages": messages_history or [],
            "preferences": preferences or {},
            "lead_info": lead_info or {},
            "recommended_properties": [],
            "response": "",
            "booking_confirmed": False,
            "needs_more_info": False,
            "missing_preferences": [],
            "error": None
        }

        try:
            final_state = self.graph.invoke(initial_state)

            return {
                "response": final_state.get("response", ""),
                "intent": final_state.get("intent"),
                "preferences": final_state.get("preferences", {}),
                "lead_info": final_state.get("lead_info", {}),
                "recommended_properties": final_state.get("recommended_properties", []),
                "booking_confirmed": final_state.get("booking_confirmed", False),
                "booking_project": final_state.get("booking_project")
            }

        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return {
                "response": "I apologize, but I encountered an issue. Could you please try again?",
                "error": str(e)
            }

    async def process_stream(
        self,
        message: str,
        conversation_id: str,
        messages_history: Optional[List[Dict[str, str]]] = None,
        preferences: Optional[Dict] = None,
        lead_info: Optional[Dict] = None,
        recommended_properties: Optional[List] = None,
        booking_project: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a user message with streaming response."""

        initial_state: AgentState = {
            "user_message": message,
            "conversation_id": conversation_id,
            "messages": messages_history or [],
            "preferences": preferences or {},
            "lead_info": lead_info or {},
            "recommended_properties": recommended_properties or [],
            "booking_project": booking_project,
            "response": "",
            "booking_confirmed": False,
            "needs_more_info": False,
            "missing_preferences": [],
            "error": None
        }

        try:
            state = initial_state.copy()
            state = await sync_to_async(self._classify_intent, thread_sensitive=True)(state)
            intent = state.get("intent")

            yield {"type": "intent", "data": intent}

            if intent == "greeting":
                state = self._handle_greeting(state)
                yield {"type": "content", "data": state.get("response", "")}
                yield {"type": "done", "data": state}
                return

            if intent == "gathering_preferences":
                state = await sync_to_async(self._gather_preferences, thread_sensitive=True)(state)
                state = await sync_to_async(self._search_properties, thread_sensitive=True)(state)
            elif intent == "searching_properties":
                state = await sync_to_async(self._search_properties, thread_sensitive=True)(state)
            elif intent == "answering_question":
                state = await sync_to_async(self._answer_question, thread_sensitive=True)(state)
            elif intent == "booking_visit":
                state = self._handle_booking(state)
            elif intent == "collecting_lead_info":
                state = await sync_to_async(self._collect_lead_info, thread_sensitive=True)(state)

            if state.get("recommended_properties"):
                yield {"type": "properties", "data": state["recommended_properties"]}

            messages = self._build_response_messages(state)

            full_response = ""
            async for chunk in self.streaming_llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield {"type": "content", "data": chunk.content}

            state["response"] = full_response
            yield {"type": "done", "data": {
                "intent": state.get("intent"),
                "preferences": state.get("preferences", {}),
                "lead_info": state.get("lead_info", {}),
                "recommended_properties": state.get("recommended_properties", []),
                "booking_confirmed": state.get("booking_confirmed", False)
            }}

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {"type": "error", "data": str(e)}

    def _build_response_messages(self, state: AgentState) -> List:
        """Build messages for response generation."""
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        intent = state.get("intent")
        user_message = state.get("user_message", "")

        if intent == "general_conversation":
            context = "\n".join([
                f"{m['role']}: {m['content']}"
                for m in state.get("messages", [])[-4:]
            ])
            prompt = GENERAL_RESPONSE_PROMPT.format(
                message=user_message,
                context=context or "No previous context"
            )

        elif intent in ("searching_properties", "gathering_preferences"):
            properties = state.get("recommended_properties", [])
            prefs = state.get("preferences", {})
            missing = state.get("missing_preferences", [])

            if properties:
                props_text = "\n".join([
                    f"- **{p['project_name']}**: ${p.get('price_usd', 0):,.0f}, "
                    f"{p.get('bedrooms', 'N/A')} bed, {p.get('city', 'Unknown')}"
                    for p in properties[:3]
                ])
                prompt = PROPERTY_RECOMMENDATION_PROMPT.format(
                    preferences=json.dumps(prefs, indent=2),
                    properties=props_text
                )
            elif missing:
                prompt = f"""User preferences so far: {json.dumps(prefs)}
Still need: {', '.join(missing)}
Ask about missing info in a friendly way."""
            else:
                prompt = "No matching properties found. Suggest adjusting criteria."

        elif intent == "answering_question":
            prompt = QUESTION_ANSWERING_PROMPT.format(
                question=user_message,
                property_info=json.dumps(state.get("sql_results"), indent=2) or "None",
                web_results=state.get("web_search_results") or "None"
            )

        elif intent in ("booking_visit", "collecting_lead_info"):
            lead_info = state.get("lead_info", {})
            missing = state.get("missing_preferences", [])
            if state.get("booking_confirmed"):
                prompt = f"Confirm booking for {state.get('booking_project')}. Lead: {lead_info}"
            else:
                prompt = BOOKING_PROMPT.format(
                    property_name=state.get("booking_project", "selected property"),
                    lead_info=json.dumps(lead_info),
                    missing_info=', '.join(missing) or "none"
                )
        else:
            prompt = f"Respond to: {user_message}"

        messages.append(HumanMessage(content=prompt))
        return messages


_property_agent = None


def get_property_agent():
    """Lazy initialization of property agent."""
    global _property_agent
    if _property_agent is None:
        _property_agent = PropertySalesAgent()
    return _property_agent


# For backward compatibility
class LazyPropertyAgent:
    """Lazy proxy for PropertySalesAgent."""

    def process(self, *args, **kwargs):
        return get_property_agent().process(*args, **kwargs)

    def process_stream(self, *args, **kwargs):
        return get_property_agent().process_stream(*args, **kwargs)


property_agent = LazyPropertyAgent()

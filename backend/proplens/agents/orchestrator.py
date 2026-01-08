"""LangGraph orchestrator for property sales agent."""
import json
import re
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator, Literal

from django.conf import settings
from asgiref.sync import sync_to_async
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

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


class IntentClassification(BaseModel):
    """Schema for intent classification using function calling."""

    intent: Literal[
        "greeting",
        "gathering_preferences",
        "searching_properties",
        "answering_question",
        "booking_visit",
        "collecting_lead_info",
        "general_conversation"
    ] = Field(
        description="The classified intent of the user message"
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1",
        ge=0,
        le=1
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )
    needs_web_search: bool = Field(
        default=False,
        description="Whether the question requires external web search (e.g., about schools, transport, neighborhood)"
    )
    interested_property: Optional[str] = Field(
        default=None,
        description="Name of specific property user expresses interest in (e.g., 'The OWO', 'Damac Tower'). Only set if user explicitly mentions a property name."
    )


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
        """Classify user intent using function calling for reliable structured output."""
        message = state.get("user_message", "")
        messages_history = state.get("messages", [])

        print(f"[INTENT] Classifying message: '{message}'", flush=True)

        context = "No previous context"
        if messages_history:
            recent = messages_history[-4:] if len(messages_history) > 4 else messages_history
            context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

        # Use structured output with function calling
        intent_classifier = self.llm.with_structured_output(IntentClassification)

        classification_prompt = f"""Classify the user's intent for a property sales assistant.

User message: "{message}"

Conversation context:
{context}

Intent definitions:
- greeting: Greetings like hello, hi, halo, hai
- gathering_preferences: User expresses interest in a city/location, mentions budget, bedrooms
- searching_properties: User asks to see/find/show properties, or wants property options
- answering_question: User asks about schools, transport, neighborhood, amenities (external info)
- booking_visit: User wants to book/visit/schedule viewing, OR selects a specific property
- collecting_lead_info: User provides contact info (name, email, phone) or message contains @
- general_conversation: Other casual conversation

CRITICAL PRIORITY RULES (in order):
1. If message contains @ → collecting_lead_info
2. If context shows properties were just listed AND user mentions a PROPERTY NAME → booking_visit
   Examples: "JDS Group", "yes jds group", "the first one", "I want Damac Tower"
3. Affirmative responses after property shown (yes, ok, mau, want, book, iya, boleh) → booking_visit
4. Questions about schools/transport/neighborhood → answering_question with needs_web_search=true
5. "show me", "give me options", "list properties", "what properties" → searching_properties
6. Mentions city/budget/bedrooms without asking to see properties → gathering_preferences

BOOKING DETECTION - VERY IMPORTANT:
When properties were shown in context and user responds with:
- A property name (full or partial): "JDS Group", "jds", "The OWO" → booking_visit
- "yes" + property name: "yes jds group" → booking_visit
- Selection phrases: "the first one", "that one", "I like it" → booking_visit
- Affirmatives: "yes", "ok", "sure", "book it", "I want it" → booking_visit

Set needs_web_search=true ONLY for questions about schools, transport, neighborhood.

PROPERTY INTEREST DETECTION:
Set interested_property to the property name user mentions.
Examples:
- "JDS Group" (after properties shown) → intent=booking_visit, interested_property="JDS Group"
- "yes jds group" → intent=booking_visit, interested_property="JDS Group"
- "I like The OWO" → intent=booking_visit, interested_property="The OWO" """

        try:
            result = intent_classifier.invoke([HumanMessage(content=classification_prompt)])
            state["intent"] = result.intent
            state["needs_web_search"] = result.needs_web_search

            # Track explicitly interested properties
            if result.interested_property:
                interested = state.get("interested_properties", [])
                if result.interested_property not in interested:
                    interested.append(result.interested_property)
                state["interested_properties"] = interested
                print(f"[INTENT] Interested in property: {result.interested_property}", flush=True)

            print(f"[INTENT] Result: intent={result.intent}, confidence={result.confidence:.2f}, "
                  f"needs_web_search={result.needs_web_search}", flush=True)
            print(f"[INTENT] Reasoning: {result.reasoning}", flush=True)
        except Exception as e:
            print(f"[INTENT] ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
            state["intent"] = "general_conversation"
            state["needs_web_search"] = False

        return state

    def _route_by_intent(self, state: AgentState) -> str:
        return state.get("intent", "general_conversation")

    def _handle_greeting(self, state: AgentState) -> AgentState:
        """Handle greeting intent with natural LLM response."""
        user_message = state.get("user_message", "")
        messages_history = state.get("messages", [])

        # Build context from recent messages
        context = ""
        if messages_history:
            recent = messages_history[-4:] if len(messages_history) > 4 else messages_history
            context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

        prompt = f"""You are Silvy, a friendly and warm property assistant at Silver Land Properties.
The user just greeted you with: "{user_message}"

Previous conversation (if any):
{context or "This is the start of the conversation."}

Respond naturally to their greeting. Be warm, friendly, and conversational - not robotic.
- Mirror their language style (formal/casual)
- If they said their name, use it warmly
- Introduce yourself briefly as Silvy from Silver Land Properties
- Gently guide toward property preferences (city, budget, bedrooms) but don't make it feel like a checklist

Keep your response concise (2-4 sentences) and natural."""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        state["response"] = response.content
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
        prefs = state.get("preferences", {}).copy()
        user_message = state.get("user_message", "")

        # Always check current message for city - user might have changed their mind
        extract_prompt = f"""From this message, extract the city/location the user wants properties in.

Message: "{user_message}"

Return ONLY a JSON object: {{"city": "city name or null"}}
If no specific city is mentioned in THIS message, return {{"city": null}}"""

        try:
            response = self.llm.invoke([HumanMessage(content=extract_prompt)])
            location_data = extract_json(response.content)
            new_city = location_data.get("city")
            if new_city and new_city != "null":
                prefs["city"] = new_city
                print(f"[SEARCH] City from current message: {new_city}", flush=True)
        except Exception as e:
            print(f"[SEARCH] Failed to extract city: {e}", flush=True)

        # If still no city, try conversation context
        if not prefs.get("city"):
            messages = state.get("messages", [])
            if messages:
                context_text = "\n".join([m.get('content', '') for m in messages[-4:]])
                context_prompt = f"""From this conversation context, what city is the user interested in?

Context:
{context_text}

Return ONLY: {{"city": "city name or null"}}"""
                try:
                    response = self.llm.invoke([HumanMessage(content=context_prompt)])
                    location_data = extract_json(response.content)
                    if location_data.get("city") and location_data["city"] != "null":
                        prefs["city"] = location_data["city"]
                        print(f"[SEARCH] City from context: {prefs['city']}", flush=True)
                except Exception:
                    pass

        # Save updated prefs back to state so response generation can use it
        state["preferences"] = prefs
        print(f"[SEARCH] Searching with prefs: {prefs}", flush=True)

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

        print(f"[ANSWER] Processing question: '{message}'", flush=True)

        sql_result = sql_tool.query(message)
        state["sql_results"] = sql_result.get("results")
        print(f"[ANSWER] SQL results: {len(sql_result.get('results', [])) if sql_result.get('results') else 0} rows", flush=True)

        # Use the needs_web_search flag from intent classification (function calling)
        needs_web_search = state.get("needs_web_search", False)
        print(f"[ANSWER] needs_web_search={needs_web_search}, TAVILY_API_KEY={'SET' if settings.TAVILY_API_KEY else 'NOT SET'}", flush=True)

        if needs_web_search and settings.TAVILY_API_KEY:
            # Only use property name if user explicitly mentioned it in their message
            # Check if user refers to a specific property by name
            interested_props = state.get("interested_properties", [])
            properties = state.get("recommended_properties", [])

            # Get the property name ONLY if user mentioned it or we detected interest
            project_name = None
            if interested_props:
                # Use the most recently interested property
                project_name = interested_props[-1]
            else:
                # Check if user's message contains a property name
                message_lower = message.lower()
                for prop in properties:
                    prop_name = prop.get("project_name", "") if isinstance(prop, dict) else getattr(prop, "project_name", "")
                    if prop_name and prop_name.lower() in message_lower:
                        project_name = prop_name
                        break

            # Get city from preferences
            city = state.get("preferences", {}).get("city")
            if not city and properties:
                prop = properties[0]
                city = prop.get("city") if isinstance(prop, dict) else getattr(prop, "city", None)

            print(f"[WEB_SEARCH] Question: '{message}', Project: {project_name}, City: {city}", flush=True)

            try:
                # Pass the actual question + context (only property if explicitly mentioned)
                web_results = web_search_tool.search_context(
                    question=message,
                    property_name=project_name,  # Will be None if user didn't mention specific property
                    city=city
                )
                state["web_search_results"] = web_results
                print(f"[WEB_SEARCH] Results length: {len(web_results) if web_results else 0}", flush=True)
            except Exception as e:
                print(f"[WEB_SEARCH] Error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                state["web_search_results"] = None
        else:
            state["web_search_results"] = None
            if needs_web_search and not settings.TAVILY_API_KEY:
                print("[WEB_SEARCH] Skipped - TAVILY_API_KEY not set", flush=True)
            elif not needs_web_search:
                print("[WEB_SEARCH] Skipped - not needed for this query", flush=True)

        return state

    def _handle_booking(self, state: AgentState) -> AgentState:
        """Handle property visit booking."""
        properties = state.get("recommended_properties", [])
        lead_info = state.get("lead_info", {})
        user_message = state.get("user_message", "").lower()
        interested_props = state.get("interested_properties", [])

        print(f"[BOOKING] Properties: {len(properties)}, interested: {interested_props}", flush=True)
        print(f"[BOOKING] User message: '{user_message}'", flush=True)

        # Priority 1: Use interested_property from intent classification
        if interested_props and not state.get("booking_project"):
            state["booking_project"] = interested_props[-1]
            print(f"[BOOKING] Set booking_project from interested: {state['booking_project']}", flush=True)

        # Priority 2: Try to match user message against recommended properties
        if not state.get("booking_project") and properties:
            for prop in properties:
                prop_name = prop.get("project_name", "") if isinstance(prop, dict) else getattr(prop, "project_name", "")
                if prop_name and prop_name.lower() in user_message:
                    state["booking_project"] = prop_name
                    print(f"[BOOKING] Matched property from message: {prop_name}", flush=True)
                    break
                # Also check partial match (e.g., "jds" matches "JDS Group - Miami")
                if prop_name:
                    words = user_message.split()
                    for word in words:
                        if len(word) > 2 and word in prop_name.lower():
                            state["booking_project"] = prop_name
                            print(f"[BOOKING] Partial match: '{word}' in '{prop_name}'", flush=True)
                            break

        # Priority 3: Default to first recommended property
        if not state.get("booking_project") and properties:
            if isinstance(properties[0], dict):
                state["booking_project"] = properties[0].get("project_name")
            elif hasattr(properties[0], "project_name"):
                state["booking_project"] = properties[0].project_name
            print(f"[BOOKING] Default to first property: {state.get('booking_project')}", flush=True)

        if properties:
            state["selected_property"] = properties[0]

        missing = []
        if not lead_info.get("first_name"):
            missing.append("name")
        if not lead_info.get("email"):
            missing.append("email")

        state["needs_more_info"] = len(missing) > 0
        state["missing_preferences"] = missing

        print(f"[BOOKING] Final booking_project: {state.get('booking_project')}, missing: {missing}", flush=True)
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
                if isinstance(properties[0], dict):
                    state["booking_project"] = properties[0].get("project_name")
                elif hasattr(properties[0], "project_name"):
                    state["booking_project"] = properties[0].project_name

        # Only confirm booking if we have a property AND name + email
        has_property = state.get("booking_project") or state.get("recommended_properties")
        has_complete_info = current_lead.get("first_name") and current_lead.get("email")

        if has_property and has_complete_info:
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
            # Flag that we need property preferences first
            if not has_property:
                state["needs_property_first"] = True

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
            searched_city = prefs.get("city")

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
            elif searched_city:
                # User asked for a specific city but no properties found
                prompt = f"""The user asked about properties in {searched_city}, but we have NO properties there.

Tell them honestly: "I'm sorry, we don't currently have any properties in {searched_city}."
Suggest our top locations: Dubai (76 properties), Miami (39), Phuket (26), Bangkok (23), London (12), Abu Dhabi (6).
Ask which city interests them."""
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

            # Debug logging
            print(f"[GENERATE] answering_question - sql_results count: {len(sql_results) if sql_results else 0}", flush=True)
            print(f"[GENERATE] answering_question - web_results length: {len(web_results) if web_results else 0}", flush=True)
            if web_results:
                print(f"[GENERATE] Web results preview (first 500 chars):\n{web_results[:500]}", flush=True)

            prompt = QUESTION_ANSWERING_PROMPT.format(
                question=user_message,
                property_info=json.dumps(sql_results, indent=2) if sql_results else "No database results",
                web_results=web_results or "No web search performed"
            )
            print(f"[GENERATE] Full prompt length: {len(prompt)} chars", flush=True)
            messages.append(HumanMessage(content=prompt))

        elif intent in ("booking_visit", "collecting_lead_info"):
            lead_info = state.get("lead_info", {})
            missing = state.get("missing_preferences", [])
            property_name = state.get("booking_project")

            # Handle case when user provides name but no property context yet
            if state.get("needs_property_first") or not property_name:
                name = lead_info.get('first_name', '')
                prompt = f"""The user has introduced themselves{' as ' + name if name else ''}.
Lead info collected: {json.dumps(lead_info)}

Thank them warmly for introducing themselves, then ask about their property preferences:
- Which city are they interested in?
- What's their budget range?
- How many bedrooms do they need?

Be friendly and guide them to find the perfect property."""
            elif state.get("booking_confirmed"):
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
            "needs_web_search": False,
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
                "interested_properties": final_state.get("interested_properties", []),
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
            "needs_web_search": False,
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
                "interested_properties": state.get("interested_properties", []),
                "booking_confirmed": state.get("booking_confirmed", False),
                "booking_project": state.get("booking_project")
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
            searched_city = prefs.get("city")

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
            elif searched_city:
                prompt = f"""The user asked about properties in {searched_city}, but we have NO properties there.
Tell them honestly we don't have properties in {searched_city}.
Suggest our top locations: Dubai (76), Miami (39), Phuket (26), Bangkok (23), London (12), Abu Dhabi (6)."""
            elif missing:
                prompt = f"""User preferences so far: {json.dumps(prefs)}
Still need: {', '.join(missing)}
Ask about missing info in a friendly way."""
            else:
                prompt = "No matching properties found. Suggest adjusting criteria."

        elif intent == "answering_question":
            sql_results = state.get("sql_results")
            web_results = state.get("web_search_results")

            # Debug logging
            print(f"[BUILD_MESSAGES] answering_question - sql_results: {len(sql_results) if sql_results else 0}", flush=True)
            print(f"[BUILD_MESSAGES] answering_question - web_results length: {len(web_results) if web_results else 0}", flush=True)
            if web_results:
                print(f"[BUILD_MESSAGES] Web results preview:\n{web_results[:500]}", flush=True)

            prompt = QUESTION_ANSWERING_PROMPT.format(
                question=user_message,
                property_info=json.dumps(sql_results, indent=2) if sql_results else "No database results",
                web_results=web_results or "No web search performed"
            )

        elif intent in ("booking_visit", "collecting_lead_info"):
            lead_info = state.get("lead_info", {})
            missing = state.get("missing_preferences", [])
            property_name = state.get("booking_project")

            # Handle case when user provides name but no property context yet
            if state.get("needs_property_first") or not property_name:
                name = lead_info.get('first_name', '')
                prompt = f"""The user has introduced themselves{' as ' + name if name else ''}.
Lead info: {json.dumps(lead_info)}

Thank them warmly, then ask about property preferences (city, budget, bedrooms)."""
            elif state.get("booking_confirmed"):
                prompt = f"Confirm booking for {property_name}. Lead: {lead_info}"
            else:
                prompt = BOOKING_PROMPT.format(
                    property_name=property_name,
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

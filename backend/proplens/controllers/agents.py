"""Agents controller for chat functionality."""
import json
import asyncio
from uuid import UUID
from typing import List
from ninja_extra import api_controller, http_post
from ninja_extra.exceptions import NotFound
from django.http import StreamingHttpResponse

from proplens.schemas import (
    ChatRequestSchema,
    ChatResponseSchema,
    ProjectSummarySchema,
    ChatMetadataSchema
)
from proplens.services.conversation import conversation_service
from proplens.agents.orchestrator import property_agent


@api_controller("/agents", tags=["Agents"])
class AgentsController:
    """Controller for AI agent chat functionality."""

    @http_post("/chat", response=ChatResponseSchema)
    def chat(self, request: ChatRequestSchema):
        """Process a chat message."""
        conversation = conversation_service.get_conversation(request.conversation_id)
        if not conversation:
            raise NotFound("Conversation not found")

        messages_history = conversation_service.get_messages(request.conversation_id)
        context = conversation.context or {}
        preferences = context.get("preferences", {})
        lead_info = context.get("lead_info", {})

        conversation_service.add_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message
        )

        result = property_agent.process(
            message=request.message,
            conversation_id=str(request.conversation_id),
            messages_history=messages_history,
            preferences=preferences,
            lead_info=lead_info
        )

        conversation_service.add_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=result["response"],
            extra_data={
                "intent": result.get("intent"),
                "recommended_properties": [
                    p.get("project_name") for p in result.get("recommended_properties", [])
                ]
            }
        )

        new_context = {
            "preferences": result.get("preferences", {}),
            "lead_info": result.get("lead_info", {})
        }
        conversation_service.update_context(request.conversation_id, new_context)

        if result.get("booking_confirmed"):
            lead_info_result = result.get("lead_info", {})
            if lead_info_result.get("email"):
                lead = conversation_service.get_or_create_lead(
                    request.conversation_id, lead_info_result
                )

                if result.get("preferences"):
                    conversation_service.update_lead_preferences(
                        lead.id, result["preferences"]
                    )

                if result.get("booking_project"):
                    project = conversation_service.find_project_by_name(
                        result["booking_project"]
                    )
                    if project:
                        conversation_service.create_booking(
                            lead_id=lead.id,
                            project_id=project.id
                        )

        recommended: List[ProjectSummarySchema] = []
        for prop in result.get("recommended_properties", []):
            recommended.append(ProjectSummarySchema(
                id=UUID(prop["id"]) if prop.get("id") else None,
                project_name=prop.get("project_name", ""),
                city=prop.get("city"),
                country=prop.get("country"),
                price_usd=prop.get("price_usd"),
                bedrooms=prop.get("bedrooms"),
                property_type=prop.get("property_type")
            ))

        return ChatResponseSchema(
            response=result["response"],
            conversation_id=request.conversation_id,
            recommended_projects=recommended if recommended else None,
            metadata=ChatMetadataSchema(
                intent=result.get("intent"),
                booking_confirmed=result.get("booking_confirmed", False)
            )
        )

    @http_post("/chat/stream")
    def chat_stream(self, request: ChatRequestSchema):
        """Process a chat message with streaming response."""
        conversation = conversation_service.get_conversation(request.conversation_id)
        if not conversation:
            raise NotFound("Conversation not found")

        messages_history = conversation_service.get_messages(request.conversation_id)
        context = conversation.context or {}
        preferences = context.get("preferences", {})
        lead_info = context.get("lead_info", {})

        conversation_service.add_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message
        )

        def generate():
            full_response = ""
            final_data = {}

            async def stream_async():
                nonlocal full_response, final_data

                async for chunk in property_agent.process_stream(
                    message=request.message,
                    conversation_id=str(request.conversation_id),
                    messages_history=messages_history,
                    preferences=preferences,
                    lead_info=lead_info
                ):
                    chunk_type = chunk.get("type")
                    data = chunk.get("data")

                    if chunk_type == "content":
                        full_response += data
                        yield f"data: {json.dumps({'type': 'content', 'data': data})}\n\n"

                    elif chunk_type == "properties":
                        props = [
                            {
                                "id": str(p.get("id", "")),
                                "project_name": p.get("project_name", ""),
                                "city": p.get("city"),
                                "price_usd": p.get("price_usd"),
                                "bedrooms": p.get("bedrooms")
                            }
                            for p in data
                        ]
                        yield f"data: {json.dumps({'type': 'properties', 'data': props})}\n\n"

                    elif chunk_type == "intent":
                        yield f"data: {json.dumps({'type': 'intent', 'data': data})}\n\n"

                    elif chunk_type == "done":
                        final_data = data
                        yield f"data: {json.dumps({'type': 'done', 'data': data})}\n\n"

                    elif chunk_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'data': data})}\n\n"

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                async_gen = stream_async()
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
            finally:
                if full_response:
                    conversation_service.add_message(
                        conversation_id=request.conversation_id,
                        role="assistant",
                        content=full_response,
                        extra_data={"intent": final_data.get("intent")}
                    )

                    conversation_service.update_context(
                        request.conversation_id,
                        {
                            "preferences": final_data.get("preferences", {}),
                            "lead_info": final_data.get("lead_info", {})
                        }
                    )

                loop.close()

        response = StreamingHttpResponse(
            generate(),
            content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

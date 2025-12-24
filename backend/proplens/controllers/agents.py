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
    def chat(self, data: ChatRequestSchema):
        """Process a chat message."""
        conversation = conversation_service.get_conversation(data.conversation_id)
        if not conversation:
            raise NotFound("Conversation not found")

        messages_history = conversation_service.get_messages(data.conversation_id)
        context = conversation.context or {}
        preferences = context.get("preferences", {})
        lead_info = context.get("lead_info", {})

        conversation_service.add_message(
            conversation_id=data.conversation_id,
            role="user",
            content=data.message
        )

        result = property_agent.process(
            message=data.message,
            conversation_id=str(data.conversation_id),
            messages_history=messages_history,
            preferences=preferences,
            lead_info=lead_info
        )

        conversation_service.add_message(
            conversation_id=data.conversation_id,
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
        conversation_service.update_context(data.conversation_id, new_context)

        if result.get("booking_confirmed"):
            lead_info_result = result.get("lead_info", {})
            if lead_info_result.get("email"):
                lead = conversation_service.get_or_create_lead(
                    data.conversation_id, lead_info_result
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
            conversation_id=data.conversation_id,
            recommended_projects=recommended if recommended else None,
            metadata=ChatMetadataSchema(
                intent=result.get("intent"),
                booking_confirmed=result.get("booking_confirmed", False)
            )
        )

    @http_post("/chat/stream")
    def chat_stream(self, data: ChatRequestSchema):
        """Process a chat message with streaming response."""
        conversation = conversation_service.get_conversation(data.conversation_id)
        if not conversation:
            raise NotFound("Conversation not found")

        messages_history = conversation_service.get_messages(data.conversation_id)
        context = conversation.context or {}
        prefs = context.get("preferences", {})
        lead = context.get("lead_info", {})
        recommended = context.get("recommended_properties", [])
        booking_project = context.get("booking_project")

        conversation_service.add_message(
            conversation_id=data.conversation_id,
            role="user",
            content=data.message
        )

        # Capture for closure
        msg = data.message
        conv_id = str(data.conversation_id)
        conv_id_uuid = data.conversation_id
        prev_recommended = recommended
        prev_booking_project = booking_project
        prev_lead = lead

        def generate():
            full_response = ""
            final_result = {}

            async def stream_async():
                nonlocal full_response, final_result

                async for chunk in property_agent.process_stream(
                    message=msg,
                    conversation_id=conv_id,
                    messages_history=messages_history,
                    preferences=prefs,
                    lead_info=prev_lead,
                    recommended_properties=prev_recommended,
                    booking_project=prev_booking_project
                ):
                    chunk_type = chunk.get("type")
                    chunk_data = chunk.get("data")

                    if chunk_type == "content":
                        full_response += chunk_data
                        yield f"data: {json.dumps({'type': 'content', 'data': chunk_data})}\n\n"

                    elif chunk_type == "properties":
                        props = [
                            {
                                "id": str(p.get("id", "")),
                                "project_name": p.get("project_name", ""),
                                "city": p.get("city"),
                                "price_usd": p.get("price_usd"),
                                "bedrooms": p.get("bedrooms")
                            }
                            for p in chunk_data
                        ]
                        yield f"data: {json.dumps({'type': 'properties', 'data': props})}\n\n"

                    elif chunk_type == "intent":
                        yield f"data: {json.dumps({'type': 'intent', 'data': chunk_data})}\n\n"

                    elif chunk_type == "done":
                        final_result = chunk_data
                        yield f"data: {json.dumps({'type': 'done', 'data': chunk_data})}\n\n"

                    elif chunk_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'data': chunk_data})}\n\n"

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
                        conversation_id=conv_id_uuid,
                        role="assistant",
                        content=full_response,
                        extra_data={"intent": final_result.get("intent")}
                    )

                    # Save all context including recommended properties
                    recommended = final_result.get("recommended_properties", [])
                    booking_project = None
                    if recommended:
                        booking_project = recommended[0].get("project_name") if isinstance(recommended[0], dict) else None

                    conversation_service.update_context(
                        conv_id_uuid,
                        {
                            "preferences": final_result.get("preferences", {}),
                            "lead_info": final_result.get("lead_info", {}),
                            "recommended_properties": recommended,
                            "booking_project": booking_project
                        }
                    )

                    # Save lead and create booking if confirmed
                    if final_result.get("booking_confirmed"):
                        lead_info_result = final_result.get("lead_info", {})
                        if lead_info_result.get("email"):
                            saved_lead = conversation_service.get_or_create_lead(
                                conv_id_uuid, lead_info_result
                            )

                            if final_result.get("preferences"):
                                conversation_service.update_lead_preferences(
                                    saved_lead.id, final_result["preferences"]
                                )

                            bp = final_result.get("booking_project") or prev_booking_project
                            if bp:
                                project = conversation_service.find_project_by_name(bp)
                                if project:
                                    conversation_service.create_booking(
                                        lead_id=saved_lead.id,
                                        project_id=project.id
                                    )

                loop.close()

        response = StreamingHttpResponse(
            generate(),
            content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

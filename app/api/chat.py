"""Chat API endpoints."""
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.models import (
    ChatRequest, ChatResponse, ConversationResponse, ProjectSummary
)
from app.services.conversation_service import conversation_service
from app.agents.orchestrator import property_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation session."""
    conversation = await conversation_service.create_conversation(db)
    return ConversationResponse(
        id=conversation.id,
        status=conversation.status,
        context=conversation.context or {},
        created_at=conversation.created_at
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get conversation by ID."""
    conversation = await conversation_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=conversation.id,
        status=conversation.status,
        context=conversation.context or {},
        created_at=conversation.created_at
    )


@router.post("/agents/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process a chat message."""
    conversation = await conversation_service.get_conversation(
        db, request.conversation_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_history = await conversation_service.get_messages(
        db, request.conversation_id
    )

    context = conversation.context or {}
    preferences = context.get("preferences", {})
    lead_info = context.get("lead_info", {})

    await conversation_service.add_message(
        db,
        conversation_id=request.conversation_id,
        role="user",
        content=request.message
    )

    result = await property_agent.process(
        message=request.message,
        conversation_id=str(request.conversation_id),
        messages_history=messages_history,
        preferences=preferences,
        lead_info=lead_info
    )

    await conversation_service.add_message(
        db,
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
    await conversation_service.update_context(
        db, request.conversation_id, new_context
    )

    if result.get("booking_confirmed"):
        lead_info = result.get("lead_info", {})
        if lead_info.get("email"):
            lead = await conversation_service.get_or_create_lead(
                db, request.conversation_id, lead_info
            )

            if result.get("preferences"):
                await conversation_service.update_lead_preferences(
                    db, lead.id, result["preferences"]
                )

            if result.get("booking_project"):
                project = await conversation_service.find_project_by_name(
                    db, result["booking_project"]
                )
                if project:
                    await conversation_service.create_booking(
                        db,
                        lead_id=lead.id,
                        project_id=project.id
                    )

    recommended = []
    for prop in result.get("recommended_properties", []):
        recommended.append(ProjectSummary(
            id=UUID(prop["id"]) if prop.get("id") else None,
            project_name=prop.get("project_name", ""),
            city=prop.get("city"),
            country=prop.get("country"),
            price_usd=prop.get("price_usd"),
            bedrooms=prop.get("bedrooms"),
            property_type=prop.get("property_type")
        ))

    return ChatResponse(
        response=result["response"],
        conversation_id=request.conversation_id,
        recommended_projects=recommended if recommended else None,
        metadata={
            "intent": result.get("intent"),
            "booking_confirmed": result.get("booking_confirmed", False)
        }
    )


@router.post("/agents/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process a chat message with streaming response."""
    conversation = await conversation_service.get_conversation(
        db, request.conversation_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_history = await conversation_service.get_messages(
        db, request.conversation_id
    )

    context = conversation.context or {}
    preferences = context.get("preferences", {})
    lead_info = context.get("lead_info", {})

    await conversation_service.add_message(
        db,
        conversation_id=request.conversation_id,
        role="user",
        content=request.message
    )

    async def generate():
        full_response = ""
        final_data = {}

        try:
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

            # Save the response
            if full_response:
                await conversation_service.add_message(
                    db,
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=full_response,
                    extra_data={"intent": final_data.get("intent")}
                )

                await conversation_service.update_context(
                    db,
                    request.conversation_id,
                    {
                        "preferences": final_data.get("preferences", {}),
                        "lead_info": final_data.get("lead_info", {})
                    }
                )

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

"""Health check endpoints."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "PropLens API",
        "version": "1.0.0",
        "description": "Property Sales Conversational Agent for Silver Land Properties"
    }

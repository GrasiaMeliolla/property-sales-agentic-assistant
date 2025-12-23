"""API endpoint tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PropLens API"
    assert "version" in data


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient):
    """Test conversation creation."""
    response = await client.post("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_get_conversation(client: AsyncClient):
    """Test getting conversation by ID."""
    # Create conversation first
    create_response = await client.post("/api/conversations")
    conversation_id = create_response.json()["id"]

    # Get the conversation
    response = await client.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 200
    assert response.json()["id"] == conversation_id


@pytest.mark.asyncio
async def test_get_nonexistent_conversation(client: AsyncClient):
    """Test getting nonexistent conversation returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/conversations/{fake_id}")
    assert response.status_code == 404

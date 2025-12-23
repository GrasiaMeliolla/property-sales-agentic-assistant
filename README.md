# Property Sales Conversational Agent

AI-powered property sales assistant for Silver Land Properties. Built with Django Ninja Extra, LangGraph, and Vanna AI.

## Features

- **Conversational Property Search**: Natural language interface for property discovery
- **Text-to-SQL with Vanna AI**: Intelligent database queries using natural language
- **LangGraph Orchestration**: Structured agent workflow for consistent conversations
- **Property Recommendations**: Smart matching based on user preferences
- **Web Search Integration**: Tavily-powered search for additional property information
- **Lead Management**: Automatic lead capture and booking system
- **Modern React Frontend**: Clean chat widget interface

## Architecture

```
backend/
  config/              # Django settings
  proplens/
    agents/            # LangGraph orchestration
    controllers/       # Ninja Extra OOP controllers
    services/          # Business logic
    tools/             # SQL & web search tools
    models.py          # Django ORM models
    schemas.py         # Pydantic schemas
    api.py             # API registration
frontend/              # Next.js frontend
```

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL
- **Agent Framework**: LangGraph
- **Text-to-SQL**: Vanna AI with ChromaDB
- **LLM**: OpenAI GPT-4o-mini
- **Web Search**: Tavily API
- **Frontend**: Next.js 14, React, TailwindCSS

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- Tavily API key (optional, for web search)

### Setup

1. Clone and configure environment:

```bash
cp .env.example .env
# Edit .env with your API keys
```

2. Start with Docker Compose:

```bash
docker-compose up --build
```

3. Access the application:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Local Development

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Start PostgreSQL:

```bash
docker-compose up postgres -d
```

3. Initialize database:

```bash
python scripts/init_db.py
```

4. Run backend:

```bash
uvicorn app.main:app --reload
```

5. Run frontend:

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### POST /api/conversations
Create a new conversation session.

**Response:**
```json
{
  "id": "uuid",
  "status": "active",
  "context": {},
  "created_at": "2024-01-01T00:00:00Z"
}
```

### POST /api/agents/chat
Send a message to the agent.

**Request:**
```json
{
  "conversation_id": "uuid",
  "message": "I'm looking for a 2-bedroom apartment in Dubai"
}
```

**Response:**
```json
{
  "response": "I found several properties...",
  "conversation_id": "uuid",
  "recommended_projects": [...],
  "metadata": {
    "intent": "searching_properties",
    "booking_confirmed": false
  }
}
```

## Agent Workflow

The LangGraph agent follows this workflow:

1. **Intent Classification**: Determine user intent (greeting, search, booking, etc.)
2. **Preference Gathering**: Extract property preferences from messages
3. **Property Search**: Query database using Vanna AI text-to-SQL
4. **Question Answering**: Answer specific questions with optional web search
5. **Booking Handling**: Collect lead info and create bookings
6. **Response Generation**: Generate natural language response

## Database Schema

- **projects**: Property listings with details
- **leads**: Customer information and preferences
- **bookings**: Property visit bookings
- **conversations**: Chat sessions
- **messages**: Chat message history

## Testing

```bash
pytest tests/ -v
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| OPENAI_API_KEY | OpenAI API key | required |
| TAVILY_API_KEY | Tavily API key | optional |
| POSTGRES_HOST | Database host | localhost |
| POSTGRES_PORT | Database port | 5432 |
| POSTGRES_USER | Database user | proplens |
| POSTGRES_PASSWORD | Database password | proplens123 |
| POSTGRES_DB | Database name | proplens |

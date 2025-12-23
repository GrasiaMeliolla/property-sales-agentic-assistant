"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import chat, health
from app.services.vanna_service import vanna_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    import asyncio

    logger.info("Starting PropLens API...")

    # Initialize Vanna asynchronously in the background (don't block startup)
    async def init_vanna_background():
        try:
            logger.info("Starting Vanna AI initialization (background)...")
            vn = await vanna_service.initialize_async(timeout=120.0)
            if vn:
                vanna_service.train()
                logger.info("Vanna AI initialized and trained successfully")
            else:
                logger.warning("Vanna AI initialization skipped - text-to-SQL will be unavailable")
        except Exception as e:
            logger.error(f"Failed to initialize Vanna: {e}")

    # Start initialization in background - don't await
    asyncio.create_task(init_vanna_background())
    logger.info("Vanna AI initialization started in background")

    yield

    logger.info("Shutting down PropLens API...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Property Sales Conversational Agent for Silver Land Properties",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(chat.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

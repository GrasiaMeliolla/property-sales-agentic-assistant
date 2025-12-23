"""Vanna AI service for text-to-SQL conversion."""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid initialization at module load
_PropertyVanna = None


def _get_vanna_class():
    """Lazy load Vanna class to avoid slow imports at startup."""
    global _PropertyVanna
    if _PropertyVanna is None:
        from vanna.chromadb import ChromaDB_VectorStore
        from vanna.openai import OpenAI_Chat

        class PropertyVanna(ChromaDB_VectorStore, OpenAI_Chat):
            """Custom Vanna class for property database queries."""

            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                OpenAI_Chat.__init__(self, config=config)

        _PropertyVanna = PropertyVanna
    return _PropertyVanna


class VannaService:
    """Service for managing Vanna AI text-to-SQL operations."""

    def __init__(self):
        self._vanna = None
        self._is_trained = False
        self._is_initializing = False
        self._init_error: Optional[str] = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _sync_initialize(self):
        """Synchronous initialization (runs in thread pool)."""
        PropertyVanna = _get_vanna_class()

        config = {
            "api_key": settings.openai_api_key,
            "model": settings.openai_model,
            "path": settings.chroma_persist_directory
        }

        vanna = PropertyVanna(config=config)

        # Connect to PostgreSQL
        vanna.connect_to_postgres(
            host=settings.postgres_host,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            port=settings.postgres_port
        )

        return vanna

    async def initialize_async(self, timeout: float = 120.0):
        """Initialize Vanna asynchronously with timeout."""
        if self._vanna is not None:
            return self._vanna

        if self._is_initializing:
            # Wait for existing initialization
            for _ in range(int(timeout)):
                await asyncio.sleep(1)
                if self._vanna is not None:
                    return self._vanna
                if self._init_error:
                    raise Exception(self._init_error)
            return None

        self._is_initializing = True
        logger.info("Initializing Vanna AI service asynchronously...")

        try:
            loop = asyncio.get_event_loop()
            self._vanna = await asyncio.wait_for(
                loop.run_in_executor(self._executor, self._sync_initialize),
                timeout=timeout
            )
            logger.info("Vanna connected to PostgreSQL")
            return self._vanna
        except asyncio.TimeoutError:
            self._init_error = "Vanna initialization timed out"
            logger.warning(f"Vanna initialization timed out after {timeout}s - text-to-SQL disabled")
            return None
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Vanna initialization failed: {e}")
            return None
        finally:
            self._is_initializing = False

    def initialize(self):
        """Initialize Vanna with OpenAI and ChromaDB (synchronous, may timeout)."""
        if self._vanna is not None:
            return self._vanna

        logger.info("Initializing Vanna AI service...")

        try:
            self._vanna = self._sync_initialize()
            return self._vanna
        except Exception as e:
            logger.error(f"Vanna initialization failed: {e}")
            self._init_error = str(e)
            return None

    @property
    def is_available(self) -> bool:
        """Check if Vanna is initialized and available."""
        return self._vanna is not None

    def train(self, force: bool = False) -> None:
        """Train Vanna on the database schema and sample queries."""
        if self._is_trained and not force:
            logger.info("Vanna already trained, skipping")
            return

        vn = self.initialize()
        if vn is None:
            logger.warning("Vanna not available, skipping training")
            return

        logger.info("Training Vanna on database schema...")

        # Train on DDL
        ddl_projects = """
        CREATE TABLE projects (
            id UUID PRIMARY KEY,
            project_name VARCHAR(500) NOT NULL,
            bedrooms INTEGER,
            bathrooms INTEGER,
            completion_status VARCHAR(50),
            unit_type VARCHAR(100),
            developer_name VARCHAR(255),
            price_usd FLOAT,
            area_sqm FLOAT,
            property_type VARCHAR(50),
            city VARCHAR(100),
            country VARCHAR(10),
            completion_date VARCHAR(50),
            features JSON,
            facilities JSON,
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        """

        ddl_leads = """
        CREATE TABLE leads (
            id UUID PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(255),
            phone VARCHAR(50),
            preferences JSON,
            conversation_id UUID,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        """

        ddl_bookings = """
        CREATE TABLE bookings (
            id UUID PRIMARY KEY,
            lead_id UUID REFERENCES leads(id),
            project_id UUID REFERENCES projects(id),
            status VARCHAR(20),
            preferred_date TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        """

        vn.train(ddl=ddl_projects)
        vn.train(ddl=ddl_leads)
        vn.train(ddl=ddl_bookings)

        # Train with documentation
        docs = [
            "The projects table contains property listings from Silver Land Properties.",
            "price_usd column contains the property price in US Dollars.",
            "city column contains the city where the property is located.",
            "country column uses 2-letter country codes (US, SG, AE, CO, TC, etc.).",
            "bedrooms column indicates number of bedrooms, can be 1, 2, 3, 4, or 5.",
            "completion_status can be 'available' for ready properties or 'off_plan' for under construction.",
            "property_type can be 'apartment' or 'villa'.",
            "developer_name is the company that developed the property.",
            "area_sqm is the property area in square meters.",
        ]

        for doc in docs:
            vn.train(documentation=doc)

        # Train with sample SQL queries
        sample_queries = [
            {
                "question": "Show all properties in Dubai",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE LOWER(city) = 'dubai' LIMIT 10"
            },
            {
                "question": "Find 2 bedroom apartments under 1 million dollars",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE bedrooms = 2 AND price_usd < 1000000 AND property_type = 'apartment' LIMIT 10"
            },
            {
                "question": "What properties are available in Singapore?",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE LOWER(city) = 'singapore' OR country = 'SG' LIMIT 10"
            },
            {
                "question": "Show the most expensive properties",
                "sql": "SELECT project_name, price_usd, bedrooms, city, country FROM projects WHERE price_usd IS NOT NULL ORDER BY price_usd DESC LIMIT 5"
            },
            {
                "question": "Find properties with 3 or more bedrooms",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE bedrooms >= 3 LIMIT 10"
            },
            {
                "question": "List all available properties",
                "sql": "SELECT project_name, price_usd, bedrooms, city, completion_status FROM projects WHERE completion_status = 'available' LIMIT 10"
            },
            {
                "question": "What developers have properties in the database?",
                "sql": "SELECT DISTINCT developer_name, COUNT(*) as property_count FROM projects WHERE developer_name IS NOT NULL GROUP BY developer_name ORDER BY property_count DESC LIMIT 10"
            },
            {
                "question": "Find properties between 500000 and 2000000 dollars",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE price_usd BETWEEN 500000 AND 2000000 LIMIT 10"
            },
            {
                "question": "Show properties in United States",
                "sql": "SELECT project_name, price_usd, bedrooms, city FROM projects WHERE country = 'US' LIMIT 10"
            },
            {
                "question": "List all cities with properties",
                "sql": "SELECT DISTINCT city, country, COUNT(*) as count FROM projects WHERE city IS NOT NULL GROUP BY city, country ORDER BY count DESC LIMIT 20"
            }
        ]

        for q in sample_queries:
            vn.train(question=q["question"], sql=q["sql"])

        self._is_trained = True
        logger.info("Vanna training complete")

    def generate_sql(self, question: str) -> Optional[str]:
        """Generate SQL query from natural language question."""
        vn = self.initialize()
        if vn is None:
            logger.warning("Vanna not available for SQL generation")
            return None

        if not self._is_trained:
            self.train()

        try:
            sql = vn.generate_sql(question=question)
            logger.info(f"Generated SQL: {sql}")
            return sql
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return None

    def run_sql(self, sql: str) -> Optional[List[Dict[str, Any]]]:
        """Execute SQL query and return results as list of dicts."""
        vn = self.initialize()
        if vn is None:
            logger.warning("Vanna not available for SQL execution")
            return None

        try:
            df = vn.run_sql(sql=sql)
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Failed to run SQL: {e}")
            return None

    def ask(self, question: str) -> Dict[str, Any]:
        """Ask a question and get SQL + results."""
        if not self.is_available:
            return {"error": "Vanna AI not available", "sql": None, "results": None}

        sql = self.generate_sql(question)

        if not sql:
            return {"error": "Could not generate SQL query", "sql": None, "results": None}

        results = self.run_sql(sql)

        return {
            "sql": sql,
            "results": results,
            "error": None if results is not None else "Query execution failed"
        }

    async def ask_async(self, question: str) -> Dict[str, Any]:
        """Ask a question asynchronously."""
        # Try to initialize if not already
        if not self.is_available:
            await self.initialize_async(timeout=60.0)

        if not self.is_available:
            return {"error": "Vanna AI not available", "sql": None, "results": None}

        # Run the synchronous ask in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.ask, question)


# Singleton instance
vanna_service = VannaService()

"""SQL tool using Vanna AI for text-to-SQL."""
import logging
from typing import Optional, List, Dict, Any

from proplens.services.vanna import vanna_service

logger = logging.getLogger(__name__)


class SQLTool:
    """Tool for querying the property database using natural language."""

    def query(self, question: str) -> Dict[str, Any]:
        """Query the database using natural language."""
        logger.info(f"SQL Tool processing question: {question}")
        return vanna_service.ask(question)

    def search_properties(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for properties with specific criteria."""
        conditions = ["1=1"]

        if city:
            conditions.append(f"LOWER(city) LIKE LOWER('%{city}%')")
        if min_price:
            conditions.append(f"price_usd >= {min_price}")
        if max_price:
            conditions.append(f"price_usd <= {max_price}")
        if bedrooms:
            conditions.append(f"bedrooms = {bedrooms}")
        if property_type:
            conditions.append(f"property_type = '{property_type.lower()}'")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            id, project_name, bedrooms, bathrooms, price_usd,
            area_sqm, city, country, property_type, completion_status,
            developer_name, description
        FROM projects
        WHERE {where_clause}
        AND price_usd IS NOT NULL
        ORDER BY price_usd ASC
        LIMIT {limit}
        """

        results = vanna_service.run_sql(sql)
        logger.info(f"Property search returned {len(results) if results else 0} results")
        return results or []

    def get_project_details(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific project."""
        sql = f"""
        SELECT * FROM projects
        WHERE LOWER(project_name) LIKE LOWER('%{project_name}%')
        LIMIT 1
        """

        results = vanna_service.run_sql(sql)
        if results and len(results) > 0:
            return results[0]
        return None


sql_tool = SQLTool()

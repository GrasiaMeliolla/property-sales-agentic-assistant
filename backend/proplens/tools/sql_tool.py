"""SQL tool using Vanna AI for text-to-SQL with Django ORM fallback."""
import logging
from typing import Optional, List, Dict, Any

from django.db.models import Q
from asgiref.sync import sync_to_async

from proplens.models import Project
from proplens.services.vanna import vanna_service

logger = logging.getLogger(__name__)


class SQLTool:
    """Tool for querying the property database using natural language."""

    def query(self, question: str) -> Dict[str, Any]:
        """Query the database using natural language."""
        logger.info(f"SQL Tool processing question: {question}")
        if vanna_service.is_available:
            return vanna_service.ask(question)
        return {"error": "Vanna AI not available", "sql": None, "results": None}

    def search_properties(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for properties with specific criteria using Django ORM."""
        logger.info(f"Searching properties: city={city}, price={min_price}-{max_price}, beds={bedrooms}")

        queryset = Project.objects.filter(price_usd__isnull=False)

        if city:
            queryset = queryset.filter(
                Q(city__icontains=city) | Q(country__iexact=city)
            )
        if min_price:
            queryset = queryset.filter(price_usd__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_usd__lte=max_price)
        if bedrooms:
            queryset = queryset.filter(bedrooms=bedrooms)
        if property_type:
            queryset = queryset.filter(property_type__iexact=property_type)

        queryset = queryset.order_by('price_usd')[:limit]

        results = []
        for p in queryset:
            results.append({
                "id": str(p.id),
                "project_name": p.project_name,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "price_usd": p.price_usd,
                "area_sqm": p.area_sqm,
                "city": p.city,
                "country": p.country,
                "property_type": p.property_type,
                "completion_status": p.completion_status,
                "developer_name": p.developer_name,
                "description": p.description[:500] if p.description else None
            })

        logger.info(f"Property search returned {len(results)} results")
        return results

    def get_project_details(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific project."""
        try:
            p = Project.objects.filter(project_name__icontains=project_name).first()
            if p:
                return {
                    "id": str(p.id),
                    "project_name": p.project_name,
                    "bedrooms": p.bedrooms,
                    "bathrooms": p.bathrooms,
                    "price_usd": p.price_usd,
                    "area_sqm": p.area_sqm,
                    "city": p.city,
                    "country": p.country,
                    "property_type": p.property_type,
                    "completion_status": p.completion_status,
                    "developer_name": p.developer_name,
                    "description": p.description,
                    "features": p.features,
                    "facilities": p.facilities
                }
        except Exception as e:
            logger.error(f"Error getting project details: {e}")
        return None

    async def search_properties_async(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Async version of search_properties for streaming endpoints."""
        return await sync_to_async(self.search_properties, thread_sensitive=True)(
            city=city,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            limit=limit
        )

    async def query_async(self, question: str) -> Dict[str, Any]:
        """Async version of query for streaming endpoints."""
        return await sync_to_async(self.query, thread_sensitive=True)(question)


sql_tool = SQLTool()

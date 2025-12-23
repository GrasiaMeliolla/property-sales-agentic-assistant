"""Health check controller."""
from ninja_extra import api_controller, http_get

from django.conf import settings
from proplens.schemas import HealthResponseSchema
from proplens.services.vanna import vanna_service


@api_controller("/health", tags=["Health"])
class HealthController:
    """Controller for health check endpoints."""

    @http_get("", response=HealthResponseSchema)
    def health_check(self):
        """Check API health status."""
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "vanna_available": vanna_service.is_available
        }

"""API configuration with ninja-extra."""
import logging
from ninja_extra import NinjaExtraAPI

logger = logging.getLogger(__name__)

api = NinjaExtraAPI(
    title="PropLens API",
    version="1.0.0",
    description="Property Sales Conversational Agent for Silver Land Properties"
)

# Register controllers with error handling
try:
    from proplens.controllers.health import HealthController
    api.register_controllers(HealthController)
    logger.info("HealthController registered")
except Exception as e:
    logger.error(f"Failed to register HealthController: {e}")

try:
    from proplens.controllers.conversations import ConversationController
    api.register_controllers(ConversationController)
    logger.info("ConversationController registered")
except Exception as e:
    logger.error(f"Failed to register ConversationController: {e}")

try:
    from proplens.controllers.agents import AgentsController
    api.register_controllers(AgentsController)
    logger.info("AgentsController registered")
except Exception as e:
    logger.error(f"Failed to register AgentsController: {e}")

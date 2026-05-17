from src.routes.configs import router as configs_router
from src.routes.entities import router as entities_router
from src.routes.health import router as health_router
from src.routes.investigate import router as investigate_router
from src.routes.search import router as search_router
from src.routes.stream import router as stream_router

__all__ = [
    "configs_router",
    "entities_router",
    "health_router",
    "investigate_router",
    "search_router",
    "stream_router",
]

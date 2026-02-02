from aiogram import Router

from .middleware import PassiveCollectionMiddleware
from .settings import router as settings_router
from .members import router as members_router
from .common import router as common_router

# Main router that bundles all feature routers
router = Router()

# Register sub-routers
# Order matters: specific commands first, generic text handlers last
router.include_router(settings_router)
router.include_router(members_router)
router.include_router(common_router)

__all__ = ["router", "PassiveCollectionMiddleware"]

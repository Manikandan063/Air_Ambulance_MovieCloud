# routes/__init__.py

from .auth import router as auth_router
from .users import router as users_router
from .patients import router as patients_router
from .hospitals import router as hospitals_router
from .aircraft import router as aircraft_router
from .bookings import router as bookings_router
from .reports import router as reports_router
from .dashboard import router as dashboard_router
from .settings import router as settings_router
from .notifications import router as notifications_router

__all__ = [
    "auth_router",
    "users_router", 
    "patients_router",
    "hospitals_router",
    "aircraft_router",
    "bookings_router",
    "reports_router",
    "dashboard_router",
    "settings_router",
    "notifications_router"
]
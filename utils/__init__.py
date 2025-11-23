# utils/__init__.py

# Import auth utilities
from .auth import verify_password, get_password_hash, create_access_token, verify_token

# Import notification service (with error handling)
try:
    from .notification import NotificationService
except ImportError as e:
    print(f"Warning: Could not import NotificationService - {e}")
    
    # Create a simple mock as fallback
    class NotificationService:
        @staticmethod
        async def send_booking_notification(*args, **kwargs):
            print("📧 Mock: Booking notification")
        
        @staticmethod
        async def send_emergency_alert(*args, **kwargs):
            print("🚨 Mock: Emergency alert")
        
        @staticmethod
        async def send_maintenance_reminder(*args, **kwargs):
            print("🔧 Mock: Maintenance reminder")
        
        @staticmethod
        async def send_system_notification(*args, **kwargs):
            print("📢 Mock: System notification")
        
        @staticmethod
        async def test_email_notification(*args, **kwargs):
            return {"success": False, "message": "Notification service not available"}
        
        @staticmethod
        async def test_sms_notification(*args, **kwargs):
            return {"success": False, "message": "Notification service not available"}
        
        @staticmethod
        async def check_notification_config():
            return {
                "email": {"configured": False, "message": "Service not available"},
                "sms": {"configured": False, "message": "Service not available"},
                "push": {"configured": False, "message": "Service not available"}
            }

__all__ = [
    "verify_password", 
    "get_password_hash", 
    "create_access_token", 
    "verify_token",
    "NotificationService"
]
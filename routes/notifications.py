# routes/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from models.user import User
from routes.auth import get_current_active_user
from typing import Annotated
import logging

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

# Import NotificationService with fallback
try:
    from utils.notification import NotificationService
except ImportError:
    # Fallback mock service
    class NotificationService:
        @staticmethod
        async def check_notification_config():
            return {
                "email": {"configured": False, "message": "Notification service not available"},
                "sms": {"configured": False, "message": "Notification service not available"},
                "push": {"configured": False, "message": "Notification service not available"}
            }
        
        @staticmethod
        async def test_email_notification(user, message):
            return {
                "success": False,
                "message": "Notification service not configured",
                "details": "Email service not available"
            }
        
        @staticmethod
        async def test_sms_notification(phone, message):
            return {
                "success": False,
                "message": "Notification service not configured", 
                "details": "SMS service not available"
            }

@router.get("/config")
async def get_notification_config(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get notification service configuration status"""
    try:
        config_status = await NotificationService.check_notification_config()
        return {
            "status": "success",
            "config": config_status,
            "message": "Notification configuration retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting notification config: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving notification configuration")

@router.post("/test/email")
async def test_email_notification(
    current_user: Annotated[User, Depends(get_current_active_user)],
    test_data: Dict[str, Any] = None
):
    """Test email notification functionality"""
    try:
        test_message = "This is a test email from the Air Ambulance System to verify email notifications are working properly."
        if test_data and "message" in test_data:
            test_message = test_data["message"]
        
        result = await NotificationService.test_email_notification(current_user, test_message)
        
        return {
            "service": "email",
            "user_email": current_user.email,
            "test_result": result
        }
        
    except Exception as e:
        logger.error(f"Error testing email notification: {e}")
        raise HTTPException(status_code=500, detail="Error testing email notification")

@router.post("/test/sms")
async def test_sms_notification(
    current_user: Annotated[User, Depends(get_current_active_user)],
    test_data: Dict[str, Any] = None
):
    """Test SMS notification functionality"""
    try:
        if not current_user.phone:
            raise HTTPException(status_code=400, detail="User phone number not available")
        
        test_message = "This is a test SMS from the Air Ambulance System."
        if test_data and "message" in test_data:
            test_message = test_data["message"]
        
        result = await NotificationService.test_sms_notification(current_user.phone, test_message)
        
        return {
            "service": "sms",
            "user_phone": current_user.phone,
            "test_result": result
        }
        
    except Exception as e:
        logger.error(f"Error testing SMS notification: {e}")
        raise HTTPException(status_code=500, detail="Error testing SMS notification")

@router.post("/test/all")
async def test_all_notifications(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Test all notification services"""
    try:
        results = {}
        
        # Test email
        email_result = await NotificationService.test_email_notification(
            current_user, 
            "Comprehensive test of all notification services"
        )
        results["email"] = email_result
        
        # Test SMS if phone available
        if current_user.phone:
            sms_result = await NotificationService.test_sms_notification(
                current_user.phone,
                "Comprehensive test of all notification services"
            )
            results["sms"] = sms_result
        else:
            results["sms"] = {
                "success": False,
                "message": "User phone number not available for testing"
            }
        
        # Get config status
        config_status = await NotificationService.check_notification_config()
        results["config"] = config_status
        
        return {
            "status": "completed",
            "user": {
                "email": current_user.email,
                "phone": current_user.phone
            },
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error testing all notifications: {e}")
        raise HTTPException(status_code=500, detail="Error testing notifications")
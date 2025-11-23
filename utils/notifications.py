import smtplib
import requests
import logging
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models.user import User  # Add this import
from models.booking import Booking
from database.connection import get_collection
from datetime import datetime
import os
from twilio.rest import Client

# Set up logging
logger = logging.getLogger(__name__)

class NotificationService:
    # Email configuration
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    
    # Twilio configuration (for SMS)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # Push notification service (OneSignal, Firebase, etc.)
    PUSH_NOTIFICATION_API_KEY = os.getenv("PUSH_NOTIFICATION_API_KEY", "")
    PUSH_NOTIFICATION_APP_ID = os.getenv("PUSH_NOTIFICATION_APP_ID", "")

    # ... (keep all your existing methods here)

    # ADD THESE TEST METHODS AT THE END OF THE CLASS:

    @staticmethod
    async def test_email_notification(user: User, test_message: str = "Test email from Air Ambulance System"):
        """Test email notification functionality"""
        try:
            if not NotificationService.SMTP_USERNAME or not NotificationService.SMTP_PASSWORD:
                return {
                    "success": False,
                    "message": "SMTP credentials not configured",
                    "details": "Set SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD environment variables"
                }

            print(f"📧 Attempting to send test email to {user.email}")
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = NotificationService.SMTP_USERNAME
            msg['To'] = user.email
            msg['Subject'] = "Test Email - Air Ambulance System"
            
            html_content = f"""
            <html>
                <body>
                    <h2>Test Email - Air Ambulance System</h2>
                    <p>{test_message}</p>
                    <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <hr>
                    <p><small>This is a test email to verify email notifications are working correctly.</small></p>
                </body>
            </html>
            """

            msg.attach(MIMEText(html_content, 'html'))

            # Send email
            with smtplib.SMTP(NotificationService.SMTP_SERVER, NotificationService.SMTP_PORT) as server:
                server.starttls()
                server.login(NotificationService.SMTP_USERNAME, NotificationService.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"✅ Test email sent successfully to {user.email}")
            return {
                "success": True,
                "message": f"Test email sent successfully to {user.email}",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Error sending test email: {e}")
            return {
                "success": False,
                "message": f"Failed to send test email: {str(e)}",
                "error": str(e)
            }

    @staticmethod
    async def test_sms_notification(phone_number: str, test_message: str = "Test SMS from Air Ambulance System"):
        """Test SMS notification functionality"""
        try:
            if not all([NotificationService.TWILIO_ACCOUNT_SID, 
                       NotificationService.TWILIO_AUTH_TOKEN, 
                       NotificationService.TWILIO_PHONE_NUMBER]):
                return {
                    "success": False,
                    "message": "Twilio credentials not configured",
                    "details": "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables"
                }

            print(f"📱 Attempting to send test SMS to {phone_number}")
            
            client = Client(NotificationService.TWILIO_ACCOUNT_SID, NotificationService.TWILIO_AUTH_TOKEN)

            message = client.messages.create(
                body=f"🚑 Air Ambulance Test: {test_message}",
                from_=NotificationService.TWILIO_PHONE_NUMBER,
                to=phone_number
            )

            logger.info(f"✅ Test SMS sent successfully to {phone_number}: {message.sid}")
            return {
                "success": True,
                "message": f"Test SMS sent successfully to {phone_number}",
                "message_sid": message.sid,
                "status": message.status,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Error sending test SMS: {e}")
            return {
                "success": False,
                "message": f"Failed to send test SMS: {str(e)}",
                "error": str(e)
            }

    @staticmethod
    async def check_notification_config():
        """Check notification service configuration"""
        config_status = {
            "email": {
                "configured": bool(NotificationService.SMTP_USERNAME and NotificationService.SMTP_PASSWORD),
                "server": NotificationService.SMTP_SERVER,
                "port": NotificationService.SMTP_PORT,
                "username": NotificationService.SMTP_USERNAME[:3] + "***" if NotificationService.SMTP_USERNAME else None,
                "message": "Ready to send emails" if NotificationService.SMTP_USERNAME and NotificationService.SMTP_PASSWORD else "SMTP credentials missing"
            },
            "sms": {
                "configured": bool(NotificationService.TWILIO_ACCOUNT_SID and NotificationService.TWILIO_AUTH_TOKEN),
                "account_sid": NotificationService.TWILIO_ACCOUNT_SID[:8] + "***" if NotificationService.TWILIO_ACCOUNT_SID else None,
                "phone_number": NotificationService.TWILIO_PHONE_NUMBER,
                "message": "Ready to send SMS" if NotificationService.TWILIO_ACCOUNT_SID and NotificationService.TWILIO_AUTH_TOKEN else "Twilio credentials missing"
            },
            "push": {
                "configured": bool(NotificationService.PUSH_NOTIFICATION_API_KEY),
                "app_id": NotificationService.PUSH_NOTIFICATION_APP_ID,
                "message": "Push notifications configured" if NotificationService.PUSH_NOTIFICATION_API_KEY else "Push notifications not configured"
            }
        }
        
        return config_status

# Simplified version for development/testing
class MockNotificationService:
    """
    Mock notification service for development without external dependencies
    """
    
    @staticmethod
    async def send_booking_notification(booking: Booking, recipients: List[User], message: str, notification_type: str = "info"):
        print(f"📧 MOCK NOTIFICATION: {message}")
        print(f"   Recipients: {[user.email for user in recipients]}")
        print(f"   Booking: {booking.id}")
        print(f"   Type: {notification_type}")
        print("---")

    @staticmethod
    async def send_emergency_alert(booking: Booking, message: str):
        print(f"🚨 MOCK EMERGENCY ALERT: {message}")
        print(f"   Booking: {booking.id}")
        print("---")

    @staticmethod
    async def send_maintenance_reminder(aircraft_id: str, message: str):
        print(f"🔧 MOCK MAINTENANCE REMINDER: {message}")
        print(f"   Aircraft: {aircraft_id}")
        print("---")

    @staticmethod
    async def send_system_notification(users: List[User], title: str, message: str, notification_type: str = "info"):
        print(f"📢 MOCK SYSTEM NOTIFICATION: {title}")
        print(f"   Message: {message}")
        print(f"   Recipients: {[user.email for user in users]}")
        print("---")

    # Test methods for mock service
    @staticmethod
    async def test_email_notification(user: User, test_message: str = "Test email from Air Ambulance System"):
        print(f"📧 MOCK EMAIL TEST: Would send email to {user.email}")
        return {
            "success": True,
            "message": f"Mock email test - would send to {user.email}",
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def test_sms_notification(phone_number: str, test_message: str = "Test SMS from Air Ambulance System"):
        print(f"📱 MOCK SMS TEST: Would send SMS to {phone_number}")
        return {
            "success": True,
            "message": f"Mock SMS test - would send to {phone_number}",
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def check_notification_config():
        return {
            "email": {"configured": False, "message": "Using mock service - no real email configured"},
            "sms": {"configured": False, "message": "Using mock service - no real SMS configured"},
            "push": {"configured": False, "message": "Push notifications not configured"}
        }

# Use mock service if email/SMS credentials are not configured
def get_notification_service():
    """
    Factory function to return appropriate notification service
    """
    if (NotificationService.SMTP_USERNAME and NotificationService.SMTP_PASSWORD) or \
       (NotificationService.TWILIO_ACCOUNT_SID and NotificationService.TWILIO_AUTH_TOKEN):
        return NotificationService
    else:
        logger.warning("Using MockNotificationService - configure SMTP/Twilio for real notifications")
        return MockNotificationService

# Export the appropriate service
NotificationService = get_notification_service()
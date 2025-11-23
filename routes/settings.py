from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from database.connection import get_collection
from models.settings import (
    UserSettings, UserSettingsCreate, UserSettingsUpdate, 
    SettingsResponse, NotificationPreferenceUpdate,
    Theme, TimeFormat, DateFormat
)
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime, timezone
import pytz
import logging

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

# Available options
AVAILABLE_TIMEZONES = [
    "UTC", "US/Eastern", "US/Central", "US/Pacific", 
    "Europe/London", "Europe/Paris", "Asia/Kolkata",
    "Asia/Tokyo", "Australia/Sydney"
]

AVAILABLE_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "hi", "name": "Hindi"},
    {"code": "ja", "name": "Japanese"}
]

def get_default_settings(user_id: str) -> Dict[str, Any]:
    """Get default settings for a new user"""
    return {
        "user_id": user_id,
        "theme": Theme.LIGHT,
        "time_format": TimeFormat.H12,
        "date_format": DateFormat.MM_DD_YYYY,
        "timezone": "UTC",
        "language": "en",
        "notifications_enabled": True,
        "email_notifications": True,
        "sms_notifications": False,
        "push_notifications": True,
        "browser_notifications": True,
        "notify_booking_updates": True,
        "notify_emergency_alerts": True,
        "notify_system_maintenance": False,
        "notify_promotions": False,
        "email_digest_frequency": "daily",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

@router.get("/", response_model=SettingsResponse)
async def get_user_settings(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get user settings with user info and server time"""
    try:
        settings_collection = get_collection("user_settings")
        users_collection = get_collection("users")
        
        # Get user settings
        settings_data = settings_collection.find_one({"user_id": str(current_user.id)})
        
        # If no settings exist, create default ones
        if not settings_data:
            default_settings = get_default_settings(str(current_user.id))
            result = settings_collection.insert_one(default_settings)
            settings_data = settings_collection.find_one({"_id": result.inserted_id})
        
        # Convert to UserSettings model
        settings_data["id"] = str(settings_data["_id"])
        user_settings = UserSettings(**settings_data)
        
        # Get updated user data
        user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})
        user_info = {
            "id": str(user_data["_id"]),
            "email": user_data["email"],
            "full_name": user_data.get("full_name", ""),
            "role": user_data["role"],
            "phone": user_data.get("phone", ""),
            "department": user_data.get("department", ""),
            "created_at": user_data.get("created_at")
        }
        
        return SettingsResponse(
            user=user_info,
            settings=user_settings,
            server_time=datetime.utcnow(),
            available_timezones=AVAILABLE_TIMEZONES,
            available_languages=AVAILABLE_LANGUAGES
        )
    
    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving settings")

@router.post("/", response_model=UserSettings)
async def create_user_settings(
    settings_data: UserSettingsCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create user settings (usually called automatically)"""
    try:
        settings_collection = get_collection("user_settings")
        
        # Check if settings already exist
        existing_settings = settings_collection.find_one({"user_id": str(current_user.id)})
        if existing_settings:
            raise HTTPException(status_code=400, detail="Settings already exist for this user")
        
        # Create new settings
        settings_dict = settings_data.dict()
        settings_dict["user_id"] = str(current_user.id)
        settings_dict["created_at"] = datetime.utcnow()
        settings_dict["updated_at"] = datetime.utcnow()
        
        result = settings_collection.insert_one(settings_dict)
        
        # Return created settings
        created_settings = settings_collection.find_one({"_id": result.inserted_id})
        created_settings["id"] = str(created_settings["_id"])
        
        logger.info(f"Settings created for user {current_user.email}")
        return UserSettings(**created_settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user settings: {e}")
        raise HTTPException(status_code=500, detail="Error creating settings")

@router.put("/", response_model=UserSettings)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update user settings"""
    try:
        settings_collection = get_collection("user_settings")
        
        # Get current settings
        current_settings = settings_collection.find_one({"user_id": str(current_user.id)})
        if not current_settings:
            # Create default settings if they don't exist
            default_settings = get_default_settings(str(current_user.id))
            result = settings_collection.insert_one(default_settings)
            current_settings = settings_collection.find_one({"_id": result.inserted_id})
        
        # Prepare update data
        update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow()
        
        # Update settings
        result = settings_collection.update_one(
            {"user_id": str(current_user.id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Settings not found or no changes made")
        
        # Return updated settings
        updated_settings = settings_collection.find_one({"user_id": str(current_user.id)})
        updated_settings["id"] = str(updated_settings["_id"])
        
        logger.info(f"Settings updated for user {current_user.email}")
        return UserSettings(**updated_settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        raise HTTPException(status_code=500, detail="Error updating settings")

@router.put("/notifications/{notification_type}")
async def update_notification_preference(
    notification_type: str,
    preference_update: NotificationPreferenceUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update specific notification preference"""
    try:
        settings_collection = get_collection("user_settings")
        
        # Map notification types to setting fields
        notification_field_map = {
            "email": "email_notifications",
            "sms": "sms_notifications", 
            "push": "push_notifications",
            "browser": "browser_notifications"
        }
        
        if notification_type not in notification_field_map:
            raise HTTPException(status_code=400, detail="Invalid notification type")
        
        field_name = notification_field_map[notification_type]
        
        # Update the specific notification setting
        result = settings_collection.update_one(
            {"user_id": str(current_user.id)},
            {"$set": {
                field_name: preference_update.enabled,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        # Return updated settings
        updated_settings = settings_collection.find_one({"user_id": str(current_user.id)})
        updated_settings["id"] = str(updated_settings["_id"])
        
        logger.info(f"Notification preference updated for user {current_user.email}: {notification_type} = {preference_update.enabled}")
        return UserSettings(**updated_settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification preference: {e}")
        raise HTTPException(status_code=500, detail="Error updating notification preference")

@router.put("/theme/{theme_name}")
async def update_theme(
    theme_name: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update user theme preference"""
    try:
        if theme_name not in ["light", "dark", "auto"]:
            raise HTTPException(status_code=400, detail="Invalid theme")
        
        settings_collection = get_collection("user_settings")
        
        result = settings_collection.update_one(
            {"user_id": str(current_user.id)},
            {"$set": {
                "theme": theme_name,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        updated_settings = settings_collection.find_one({"user_id": str(current_user.id)})
        updated_settings["id"] = str(updated_settings["_id"])
        
        logger.info(f"Theme updated for user {current_user.email}: {theme_name}")
        return UserSettings(**updated_settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating theme: {e}")
        raise HTTPException(status_code=500, detail="Error updating theme")

@router.delete("/")
async def delete_user_settings(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Delete user settings (reset to defaults)"""
    try:
        settings_collection = get_collection("user_settings")
        
        # Delete existing settings
        result = settings_collection.delete_one({"user_id": str(current_user.id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Settings not found")
        
        # Create default settings
        default_settings = get_default_settings(str(current_user.id))
        settings_collection.insert_one(default_settings)
        
        logger.info(f"Settings reset to defaults for user {current_user.email}")
        return {"message": "Settings reset to defaults successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail="Error resetting settings")

@router.get("/timezones")
async def get_available_timezones():
    """Get list of available timezones"""
    return {"timezones": AVAILABLE_TIMEZONES}

@router.get("/languages")
async def get_available_languages():
    """Get list of available languages"""
    return {"languages": AVAILABLE_LANGUAGES}

@router.get("/server-time")
async def get_server_time():
    """Get current server time"""
    return {
        "server_time": datetime.utcnow(),
        "timezone": "UTC",
        "iso_format": datetime.utcnow().isoformat()
    }
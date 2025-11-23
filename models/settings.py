from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId
from models.user import User

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    BROWSER = "browser"

class TimeFormat(str, Enum):
    H12 = "12h"
    H24 = "24h"

class DateFormat(str, Enum):
    MM_DD_YYYY = "MM/DD/YYYY"
    DD_MM_YYYY = "DD/MM/YYYY"
    YYYY_MM_DD = "YYYY-MM-DD"

class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"

class UserSettings(BaseModel):
    id: Optional[str] = None
    user_id: str
    theme: Theme = Theme.LIGHT
    time_format: TimeFormat = TimeFormat.H12
    date_format: DateFormat = DateFormat.MM_DD_YYYY
    timezone: str = "UTC"
    language: str = "en"
    
    # Notification preferences
    notifications_enabled: bool = True
    email_notifications: bool = True
    sms_notifications: bool = False
    push_notifications: bool = True
    browser_notifications: bool = True
    
    # Specific notification types
    notify_booking_updates: bool = True
    notify_emergency_alerts: bool = True
    notify_system_maintenance: bool = False
    notify_promotions: bool = False
    
    # Email frequency
    email_digest_frequency: str = "daily"  # daily, weekly, never
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserSettingsCreate(BaseModel):
    theme: Optional[Theme] = Theme.LIGHT
    time_format: Optional[TimeFormat] = TimeFormat.H12
    date_format: Optional[DateFormat] = DateFormat.MM_DD_YYYY
    timezone: Optional[str] = "UTC"
    language: Optional[str] = "en"
    notifications_enabled: Optional[bool] = True
    email_notifications: Optional[bool] = True
    sms_notifications: Optional[bool] = False
    push_notifications: Optional[bool] = True
    browser_notifications: Optional[bool] = True
    notify_booking_updates: Optional[bool] = True
    notify_emergency_alerts: Optional[bool] = True
    notify_system_maintenance: Optional[bool] = False
    notify_promotions: Optional[bool] = False
    email_digest_frequency: Optional[str] = "daily"

class UserSettingsUpdate(BaseModel):
    theme: Optional[Theme] = None
    time_format: Optional[TimeFormat] = None
    date_format: Optional[DateFormat] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    browser_notifications: Optional[bool] = None
    notify_booking_updates: Optional[bool] = None
    notify_emergency_alerts: Optional[bool] = None
    notify_system_maintenance: Optional[bool] = None
    notify_promotions: Optional[bool] = None
    email_digest_frequency: Optional[str] = None

class SettingsResponse(BaseModel):
    user: dict
    settings: UserSettings
    server_time: datetime
    available_timezones: list
    available_languages: list

class NotificationPreferenceUpdate(BaseModel):
    notification_type: NotificationType
    enabled: bool
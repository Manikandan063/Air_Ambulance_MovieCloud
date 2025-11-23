# Add settings to models exports
from .settings import (
    UserSettings, UserSettingsCreate, UserSettingsUpdate,
    SettingsResponse, NotificationPreferenceUpdate,
    Theme, TimeFormat, DateFormat, NotificationType
)

__all__ = [
    # ... existing exports
    "UserSettings", "UserSettingsCreate", "UserSettingsUpdate",
    "SettingsResponse", "NotificationPreferenceUpdate", 
    "Theme", "TimeFormat", "DateFormat", "NotificationType"
]
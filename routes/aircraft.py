from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.aircraft import Aircraft, AircraftCreate, AircraftUpdate, AircraftStatus
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime
import logging

router = APIRouter(prefix="/api/aircraft", tags=["aircraft"])
logger = logging.getLogger(__name__)

# Import NotificationService with fallback
try:
    from utils.notification import NotificationService
except ImportError:
    # Fallback mock service
    class NotificationService:
        @staticmethod
        async def send_system_notification(users, title, message, notification_type="info"):
            print(f"📢 MOCK SYSTEM: {title} - {message}")
        
        @staticmethod
        async def send_maintenance_reminder(aircraft_id, message):
            print(f"🔧 MOCK MAINTENANCE: {message}")

async def get_aircraft_notification_recipients(current_user: User, action: str, aircraft_data: dict = None) -> List[User]:
    users_collection = get_collection("users")
    recipients = []
    
    try:
        recipients.append(current_user)
        
        if action in ["created", "updated", "maintenance"]:
            relevant_staff = users_collection.find({
                "role": {"$in": [UserRole.AIRLINE_COORDINATOR, UserRole.SUPERADMIN, UserRole.DISPATCHER]},
                "is_active": True
            })
            recipients.extend([User(**user) for user in relevant_staff])
        
        unique_recipients = []
        seen_ids = set()
        for recipient in recipients:
            if str(recipient.id) not in seen_ids:
                unique_recipients.append(recipient)
                seen_ids.add(str(recipient.id))
        
        return unique_recipients
        
    except Exception as e:
        logger.error(f"Error getting aircraft notification recipients: {e}")
        return [current_user]

@router.post("/", response_model=Aircraft)
async def create_aircraft(
    aircraft_data: AircraftCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.AIRLINE_COORDINATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        aircraft_collection = get_collection("aircraft")
        aircraft_dict = aircraft_data.dict()
        aircraft_dict["created_at"] = aircraft_dict["updated_at"] = datetime.utcnow()
        aircraft_dict["maintenance_records"] = []
        
        if "status" not in aircraft_dict or not aircraft_dict["status"]:
            aircraft_dict["status"] = AircraftStatus.AVAILABLE
        
        result = aircraft_collection.insert_one(aircraft_dict)
        aircraft_id = str(result.inserted_id)
        aircraft_dict["id"] = aircraft_id
        
        recipients = await get_aircraft_notification_recipients(current_user, "created", aircraft_dict)
        notification_message = f"New aircraft registered: {aircraft_dict['registration']} ({aircraft_dict['aircraft_type']}). Base: {aircraft_dict.get('base_location', 'Unknown')}. Status: {aircraft_dict['status']}"
        
        await NotificationService.send_system_notification(
            users=recipients,
            title="New Aircraft Registered",
            message=notification_message,
            notification_type="info"
        )
        
        logger.info(f"✅ Aircraft created: {aircraft_dict['registration']} by user {current_user.email}")
        return Aircraft(**aircraft_dict)
    
    except Exception as e:
        logger.error(f"❌ Error creating aircraft: {e}")
        raise HTTPException(status_code=500, detail="Error creating aircraft")

@router.get("/", response_model=List[Aircraft])
async def get_aircrafts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    status: Optional[AircraftStatus] = None,
    skip: int = 0,
    limit: int = 100
):
    try:
        aircraft_collection = get_collection("aircraft")
        query = {}
        if status:
            query["status"] = status
        
        cursor = aircraft_collection.find(query).skip(skip).limit(limit)
        aircraft_list = []
        for aircraft in cursor:
            aircraft["id"] = str(aircraft["_id"])
            aircraft_list.append(Aircraft(**aircraft))
        
        logger.info(f"📋 Retrieved {len(aircraft_list)} aircraft for user {current_user.email}")
        return aircraft_list
    
    except Exception as e:
        logger.error(f"❌ Error retrieving aircraft: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving aircraft")

@router.get("/available/count")
async def get_available_aircraft_count(current_user: Annotated[User, Depends(get_current_active_user)]):
    try:
        aircraft_collection = get_collection("aircraft")
        count = aircraft_collection.count_documents({"status": "available"})
        logger.info(f"📊 Available aircraft count: {count}")
        return {"available_aircraft_count": count}
    
    except Exception as e:
        logger.error(f"❌ Error getting available aircraft count: {e}")
        raise HTTPException(status_code=500, detail="Error getting available aircraft count")

@router.get("/{aircraft_id}", response_model=Aircraft)
async def get_aircraft(aircraft_id: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    try:
        aircraft_collection = get_collection("aircraft")
        
        if not ObjectId.is_valid(aircraft_id):
            raise HTTPException(status_code=400, detail="Invalid aircraft ID format")
        
        aircraft_data = aircraft_collection.find_one({"_id": ObjectId(aircraft_id)})
        
        if not aircraft_data:
            raise HTTPException(status_code=404, detail="Aircraft not found")
        
        aircraft_data["id"] = str(aircraft_data["_id"])
        return Aircraft(**aircraft_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving aircraft {aircraft_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving aircraft")

@router.put("/{aircraft_id}", response_model=Aircraft)
async def update_aircraft(
    aircraft_id: str,
    aircraft_update: AircraftUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.AIRLINE_COORDINATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        aircraft_collection = get_collection("aircraft")
        
        if not ObjectId.is_valid(aircraft_id):
            raise HTTPException(status_code=400, detail="Invalid aircraft ID format")
        
        current_aircraft = aircraft_collection.find_one({"_id": ObjectId(aircraft_id)})
        if not current_aircraft:
            raise HTTPException(status_code=404, detail="Aircraft not found")
        
        update_data = {k: v for k, v in aircraft_update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow()
        
        old_status = current_aircraft.get("status")
        new_status = update_data.get('status')
        status_changed = new_status and new_status != old_status
        
        result = aircraft_collection.update_one(
            {"_id": ObjectId(aircraft_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Aircraft not found or no changes made")
        
        aircraft_data = aircraft_collection.find_one({"_id": ObjectId(aircraft_id)})
        aircraft_data["id"] = str(aircraft_data["_id"])
        
        if status_changed:
            recipients = await get_aircraft_notification_recipients(current_user, "status_change", aircraft_data)
            status_message = f"Aircraft {aircraft_data['registration']} status changed: {old_status} → {new_status}"
            
            await NotificationService.send_system_notification(
                users=recipients,
                title="Aircraft Status Updated",
                message=status_message,
                notification_type="warning" if new_status == "maintenance" else "info"
            )
            
            if new_status == "maintenance":
                maintenance_message = f"Aircraft {aircraft_data['registration']} requires maintenance. Please schedule service immediately."
                await NotificationService.send_maintenance_reminder(
                    aircraft_id=aircraft_id,
                    message=maintenance_message
                )
        
        logger.info(f"✅ Aircraft updated: {aircraft_data['registration']} by user {current_user.email}")
        return Aircraft(**aircraft_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating aircraft {aircraft_id}: {e}")
        raise HTTPException(status_code=500, detail="Error updating aircraft")
    
    
@router.delete("/{aircraft_id}")
async def delete_aircraft(
    aircraft_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role not in [
        UserRole.SUPERADMIN,
        UserRole.DISPATCHER,
        UserRole.AIRLINE_COORDINATOR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete aircraft"
        )

    try:
        aircraft_collection = get_collection("aircraft")

        if not ObjectId.is_valid(aircraft_id):
            raise HTTPException(status_code=400, detail="Invalid aircraft ID format")

        aircraft_data = aircraft_collection.find_one({"_id": ObjectId(aircraft_id)})

        if not aircraft_data:
            raise HTTPException(status_code=404, detail="Aircraft not found")

        # Delete aircraft
        aircraft_collection.delete_one({"_id": ObjectId(aircraft_id)})

        # Prepare notification
        aircraft_data["id"] = str(aircraft_data["_id"])
        registration = aircraft_data.get("registration", "Unknown")

        recipients = await get_aircraft_notification_recipients(current_user, "deleted", aircraft_data)
        message = f"Aircraft {registration} has been permanently deleted from the system."

        await NotificationService.send_system_notification(
            users=recipients,
            title="Aircraft Deleted",
            message=message,
            notification_type="danger"
        )

        logger.info(f"🗑️ Aircraft deleted: {registration} by user {current_user.email}")
        return {"message": f"Aircraft {registration} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting aircraft {aircraft_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting aircraft")

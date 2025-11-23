from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.connection import get_collection
from models.booking import Booking, BookingWithDetails
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/recent-bookings", response_model=List[BookingWithDetails])
async def get_recent_bookings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 10
):
    bookings_collection = get_collection("bookings")
    
    # Role-based filtering
    query = {}
    if current_user.role == UserRole.HOSPITAL_STAFF:
        query["created_by"] = current_user.id
    
    bookings = bookings_collection.find(query).sort("created_at", -1).limit(limit)
    
    recent_bookings = []
    async for booking in bookings:
        # Convert to BookingWithDetails (simplified - in real implementation, fetch related data)
        booking_dict = booking.copy()
        booking_dict["id"] = str(booking["_id"])
        recent_bookings.append(BookingWithDetails(**booking_dict))
    
    return recent_bookings

@router.get("/activity-transfers")
async def get_activity_transfers(current_user: Annotated[User, Depends(get_current_active_user)]):
    # Return recent activity and transfers
    bookings_collection = get_collection("bookings")
    
    recent_activities = bookings_collection.find().sort("updated_at", -1).limit(20)
    
    activities = []
    async for activity in recent_activities:
        activities.append({
            "id": str(activity["_id"]),
            "type": "booking_update",
            "status": activity["status"],
            "timestamp": activity["updated_at"],
            "description": f"Booking {activity['status']}"
        })
    
    return {"activities": activities}
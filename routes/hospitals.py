from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.hospital import Hospital, HospitalCreate, HospitalUpdate
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])

@router.post("/", response_model=Hospital)
async def create_hospital(
    hospital_data: HospitalCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create a new hospital"""
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    hospitals_collection = get_collection("hospitals")
    
    # Check if hospital with same name already exists
    existing_hospital = hospitals_collection.find_one({"hospital_name": hospital_data.hospital_name})
    if existing_hospital:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hospital with this name already exists"
        )
    
    hospital_dict = hospital_data.dict()
    hospital_dict["created_at"] = hospital_dict["updated_at"] = datetime.utcnow()
    
    result = hospitals_collection.insert_one(hospital_dict)
    hospital_dict["id"] = str(result.inserted_id)
    
    return Hospital(**hospital_dict)

@router.get("/", response_model=List[Hospital])
async def get_hospitals(
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
    level_of_care: Optional[str] = None
):
    """Get all hospitals with optional filtering"""
    hospitals_collection = get_collection("hospitals")
    
    query = {}
    if level_of_care:
        query["level_of_care"] = level_of_care
    
    cursor = hospitals_collection.find(query).skip(skip).limit(limit)
    hospital_list = []
    for hospital in cursor:
        hospital["id"] = str(hospital["_id"])
        hospital_list.append(Hospital(**hospital))
    
    return hospital_list

@router.get("/{hospital_id}", response_model=Hospital)
async def get_hospital(
    hospital_id: str, 
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get a specific hospital by ID"""
    hospitals_collection = get_collection("hospitals")
    hospital_data = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})
    
    if not hospital_data:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    hospital_data["id"] = str(hospital_data["_id"])
    return Hospital(**hospital_data)

@router.put("/{hospital_id}", response_model=Hospital)
async def update_hospital(
    hospital_id: str,
    hospital_update: HospitalUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update a hospital"""
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    hospitals_collection = get_collection("hospitals")
    
    # Check if hospital exists
    existing_hospital = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})
    if not existing_hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Check if new name conflicts with other hospitals
    if hospital_update.hospital_name:
        duplicate_hospital = hospitals_collection.find_one({
            "hospital_name": hospital_update.hospital_name,
            "_id": {"$ne": ObjectId(hospital_id)}
        })
        if duplicate_hospital:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hospital with this name already exists"
            )
    
    update_data = {k: v for k, v in hospital_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = hospitals_collection.update_one(
        {"_id": ObjectId(hospital_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Hospital not found or no changes made")
    
    # Return updated hospital
    updated_hospital = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})
    updated_hospital["id"] = str(updated_hospital["_id"])
    return Hospital(**updated_hospital)

@router.delete("/{hospital_id}")
async def delete_hospital(
    hospital_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Delete a hospital"""
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can delete hospitals"
        )
    
    hospitals_collection = get_collection("hospitals")
    
    # Check if hospital exists
    existing_hospital = hospitals_collection.find_one({"_id": ObjectId(hospital_id)})
    if not existing_hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Check if hospital is being used in any bookings
    bookings_collection = get_collection("bookings")
    bookings_using_hospital = bookings_collection.count_documents({
        "$or": [
            {"origin_hospital_id": hospital_id},
            {"destination_hospital_id": hospital_id}
        ]
    })
    
    if bookings_using_hospital > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete hospital. It is being used in {bookings_using_hospital} booking(s)."
        )
    
    result = hospitals_collection.delete_one({"_id": ObjectId(hospital_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    return {"message": "Hospital deleted successfully"}

@router.get("/search/{hospital_name}", response_model=List[Hospital])
async def search_hospitals(
    hospital_name: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 50
):
    """Search hospitals by name"""
    hospitals_collection = get_collection("hospitals")
    
    # Case-insensitive search
    query = {
        "hospital_name": {"$regex": hospital_name, "$options": "i"}
    }
    
    cursor = hospitals_collection.find(query).skip(skip).limit(limit)
    hospital_list = []
    for hospital in cursor:
        hospital["id"] = str(hospital["_id"])
        hospital_list.append(Hospital(**hospital))
    
    return hospital_list

@router.get("/stats/count")
async def get_hospitals_count(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get total count of hospitals"""
    hospitals_collection = get_collection("hospitals")
    total_count = hospitals_collection.count_documents({})
    
    # Count by level of care
    levels_of_care = hospitals_collection.aggregate([
        {"$group": {"_id": "$level_of_care", "count": {"$sum": 1}}}
    ])
    
    level_counts = {}
    for level in levels_of_care:
        level_counts[level["_id"]] = level["count"]
    
    return {
        "total_hospitals": total_count,
        "hospitals_by_level": level_counts
    }
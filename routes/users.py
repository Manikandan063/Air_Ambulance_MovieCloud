from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.user import User, UserUpdate, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/", response_model=List[User])
async def get_users(
    current_user: Annotated[User, Depends(get_current_active_user)],
    role: Optional[UserRole] = None,
    skip: int = 0,
    limit: int = 100
):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users_collection = get_collection("users")
    query = {}
    if role:
        query["role"] = role
    
    cursor = users_collection.find(query).skip(skip).limit(limit)
    user_list = []
    
    for user in cursor:
        try:
            # Build user data safely
            user_data = {
                "id": str(user["_id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "phone": user.get("phone", ""),
                "role": user["role"],
                "is_active": user.get("is_active", True),
                "profile_picture": user.get("profile_picture"),
                "created_at": user.get("created_at"),
                "updated_at": user.get("updated_at")
            }
            
            # Validate and create User object
            user_list.append(User(**user_data))
            
        except Exception as e:
            print(f"Warning: Skipping user {user.get('email')} due to validation error: {e}")
            continue
    
    return user_list

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    users_collection = get_collection("users")
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build user data safely
    user_response = {
        "id": str(user_data["_id"]),
        "email": user_data["email"],
        "full_name": user_data["full_name"],
        "phone": user_data.get("phone", ""),
        "role": user_data["role"],
        "is_active": user_data.get("is_active", True),
        "profile_picture": user_data.get("profile_picture"),
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at")
    }
    
    return User(**user_response)

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role != UserRole.SUPERADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users_collection = get_collection("users")
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    
    from datetime import datetime
    update_data["updated_at"] = datetime.utcnow()
    
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    
    # Build user data safely
    user_response = {
        "id": str(user_data["_id"]),
        "email": user_data["email"],
        "full_name": user_data["full_name"],
        "phone": user_data.get("phone", ""),
        "role": user_data["role"],
        "is_active": user_data.get("is_active", True),
        "profile_picture": user_data.get("profile_picture"),
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at")
    }
    
    return User(**user_response)

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users_collection = get_collection("users")
    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}
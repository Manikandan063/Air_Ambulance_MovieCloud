from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.user import (
    User,
    UserCreate,
    UserUpdate,
    UserRole,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from utils.auth import (
    get_password_hash,
    generate_otp,
    send_email_otp
)
from routes.auth import get_current_active_user
from bson import ObjectId
from datetime import datetime
from typing import Annotated

router = APIRouter(prefix="/api/users", tags=["Users"])


# ============================
# REGISTER USER
# ============================
@router.post("/", response_model=User)
async def register_user(user: UserCreate):
    users_collection = get_collection("users")

    # Check duplicate email
    existing = users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_pw = get_password_hash(user.password)

    new_user = {
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "gender": user.gender,           # ADD GENDER
        "role": user.role,
        "profile_picture": None,
        "hashed_password": hashed_pw,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = users_collection.insert_one(new_user)
    new_user["id"] = str(result.inserted_id)

    return User(**new_user)


# ============================
# GET ALL USERS
# ============================
@router.get("/", response_model=List[User])
async def get_users(
    current_user: Annotated[User, Depends(get_current_active_user)],
    role: Optional[UserRole] = None,
    skip: int = 0,
    limit: int = 100
):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(403, "Not enough permissions")

    users_collection = get_collection("users")

    query = {}
    if role:
        query["role"] = role

    cursor = users_collection.find(query).skip(skip).limit(limit)
    users = []

    for u in cursor:
        users.append(User(
            id=str(u["_id"]),
            email=u["email"],
            full_name=u["full_name"],
            phone=u.get("phone"),
            gender=u.get("gender"),
            role=u["role"],
            profile_picture=u.get("profile_picture"),
            is_active=u.get("is_active", True),
            created_at=u.get("created_at"),
            updated_at=u.get("updated_at")
        ))

    return users


# ============================
# GET ONE USER BY ID
# ============================
@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    users_collection = get_collection("users")

    u = users_collection.find_one({"_id": ObjectId(user_id)})
    if not u:
        raise HTTPException(404, "User not found")

    return User(
        id=str(u["_id"]),
        email=u["email"],
        full_name=u["full_name"],
        phone=u.get("phone"),
        gender=u.get("gender"),
        role=u["role"],
        profile_picture=u.get("profile_picture"),
        is_active=u.get("is_active", True),
        created_at=u.get("created_at"),
        updated_at=u.get("updated_at")
    )


# ============================
# UPDATE USER
# ============================
@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role != UserRole.SUPERADMIN and current_user.id != user_id:
        raise HTTPException(403, "Not enough permissions")

    users_collection = get_collection("users")

    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    u = users_collection.find_one({"_id": ObjectId(user_id)})
    if not u:
        raise HTTPException(404, "User not found")

    return User(
        id=str(u["_id"]),
        email=u["email"],
        full_name=u["full_name"],
        phone=u.get("phone"),
        gender=u.get("gender"),
        role=u["role"],
        profile_picture=u.get("profile_picture"),
        is_active=u.get("is_active"),
        created_at=u.get("created_at"),
        updated_at=u.get("updated_at")
    )


# ============================
# DELETE USER
# ============================
@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(403, "Not enough permissions")

    users_collection = get_collection("users")

    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "User not found")

    return {"message": "User deleted successfully"}


# ============================
# SEND OTP (FORGOT PASSWORD)
# ============================
@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    users_collection = get_collection("users")

    user = users_collection.find_one({"email": data.email})
    if not user:
        raise HTTPException(404, "Email not registered")

    otp = generate_otp()

    users_collection.update_one(
        {"email": data.email},
        {"$set": {"otp": otp, "otp_expiry": datetime.utcnow()}}
    )

    send_email_otp(data.email, otp)

    return {"message": "OTP sent successfully"}


# ============================
# VERIFY OTP (RESET PASSWORD)
# ============================
@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    users_collection = get_collection("users")

    user = users_collection.find_one({"email": data.email})

    if not user:
        raise HTTPException(404, "User not found")

    if user.get("otp") != data.otp:
        raise HTTPException(400, "Invalid OTP")

    new_hash = get_password_hash(data.new_password)

    users_collection.update_one(
        {"email": data.email},
        {"$set": {
            "hashed_password": new_hash,
            "otp": None,
            "otp_expiry": None,
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": "Password reset successful"}

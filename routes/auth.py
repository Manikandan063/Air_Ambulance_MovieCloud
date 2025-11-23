# routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from typing import Annotated

from database.connection import get_collection
from models.user import (
    User, UserCreate, UserRole, Token, LoginRequest,
    ForgotPasswordRequest, ResetPasswordRequest
)
from utils.auth import (
    verify_password, get_password_hash,
    create_access_token, verify_token,
    generate_otp, send_email_otp
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


# =======================================================
# GET CURRENT USER HELPERS
# =======================================================
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    users_collection = get_collection("users")
    user_data = users_collection.find_one({"email": token_data.email})

    if user_data is None:
        raise credentials_exception

    return User(
        id=str(user_data["_id"]),
        email=user_data["email"],
        full_name=user_data["full_name"],
        phone=user_data.get("phone", ""),
        role=user_data["role"],
        is_active=user_data.get("is_active", True),
        profile_picture=user_data.get("profile_picture"),
        created_at=user_data.get("created_at", datetime.utcnow()),
        updated_at=user_data.get("updated_at", datetime.utcnow()),
    )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# =======================================================
# REGISTER
# =======================================================
@router.post("/register", response_model=User)
async def register(user_data: UserCreate):
    users_collection = get_collection("users")

    if users_collection.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)

    user_dict = user_data.dict()
    user_dict["hashed_password"] = hashed_password
    user_dict.pop("password")
    user_dict["created_at"] = user_dict["updated_at"] = datetime.utcnow()

    result = users_collection.insert_one(user_dict)

    return User(
        id=str(result.inserted_id),
        email=user_dict["email"],
        full_name=user_dict["full_name"],
        phone=user_dict.get("phone", ""),
        role=user_dict["role"],
        is_active=user_dict.get("is_active", True),
        profile_picture=user_dict.get("profile_picture"),
        created_at=user_dict["created_at"],
        updated_at=user_dict["updated_at"],
    )


# =======================================================
# LOGIN
# =======================================================
@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    users_collection = get_collection("users")
    user_data = users_collection.find_one({"email": login_data.email})

    if not user_data:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not verify_password(login_data.password, user_data.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user_data.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token({
        "sub": user_data["email"],
        "role": user_data["role"]
    })

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=User(
            id=str(user_data["_id"]),
            email=user_data["email"],
            full_name=user_data["full_name"],
            phone=user_data.get("phone", ""),
            role=user_data["role"],
            is_active=user_data.get("is_active", True),
            profile_picture=user_data.get("profile_picture"),
            created_at=user_data.get("created_at", datetime.utcnow()),
            updated_at=user_data.get("updated_at", datetime.utcnow()),
        )
    )


# =======================================================
# FORGOT PASSWORD — Send OTP
# =======================================================
@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    users_collection = get_collection("users")
    user = users_collection.find_one({"email": request.email})

    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    # Save OTP in MongoDB
    users_collection.update_one(
        {"email": request.email},
        {"$set": {"reset_otp": otp, "otp_expiry": expiry}}
    )

    # Send OTP via Email
    send_email_otp(request.email, otp)

    return {
        "message": "OTP sent to email",
        "otp": otp  # Remove in production
    }


# =======================================================
# RESET PASSWORD — Verify OTP
# =======================================================
@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    users_collection = get_collection("users")
    user = users_collection.find_one({"email": data.email})

    if not user:
        raise HTTPException(status_code=404, detail="Invalid email")

    if user.get("reset_otp") != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user["otp_expiry"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    hashed_password = get_password_hash(data.new_password)

    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "hashed_password": hashed_password,
                "updated_at": datetime.utcnow()
            },
            "$unset": {"reset_otp": "", "otp_expiry": ""}
        }
    )

    return {"message": "Password reset successful"}

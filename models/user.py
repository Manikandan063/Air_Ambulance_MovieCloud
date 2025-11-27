from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    DISPATCHER = "dispatcher"
    HOSPITAL_STAFF = "hospital_staff"
    MEDICAL_TEAM = "medical_team"
    AIRLINE_COORDINATOR = "airline_coordinator"
    PILOT = "pilot"
    DOCTOR = "doctor"
    PARAMEDIC = "paramedic"
    PATIENT = "patient"
    CLINICIAN = "clinician"

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    gender: Optional[Gender] = None     # ⬅️ Added gender here
    role: UserRole
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[Gender] = None     # ⬅️ Added gender here
    profile_picture: Optional[str] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: str
    profile_picture: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserInDB(User):
    hashed_password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

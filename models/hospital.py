from pydantic import BaseModel, EmailStr
from typing import Optional, List
from enum import Enum
from datetime import datetime

class LevelOfCare(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"
    TERTIARY = "tertiary"
    TRAUMA_CENTER = "trauma_center"

class ContactPerson(BaseModel):
    name: str
    phone: str
    email: EmailStr
    position: str

class HospitalBase(BaseModel):
    hospital_name: str
    address: str
    latitude: float
    longitude: float
    level_of_care: LevelOfCare
    icu_capacity: int
    contact_information: ContactPerson
    preferred_pickup_location: str

class HospitalCreate(HospitalBase):
    pass

class HospitalUpdate(BaseModel):
    hospital_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    level_of_care: Optional[LevelOfCare] = None
    icu_capacity: Optional[int] = None
    preferred_pickup_location: Optional[str] = None

class Hospital(HospitalBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
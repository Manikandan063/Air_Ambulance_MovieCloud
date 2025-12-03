from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime, date
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class AcuityLevel(str, Enum):
    CRITICAL = "critical"
    URGENT = "urgent"
    STABLE = "stable"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


# ✅ New Blood Group Enum
class BloodGroup(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class NextOfKin(BaseModel):
    name: str
    relationship: str
    phone: str
    email: Optional[str] = None


class InsuranceDetails(BaseModel):
    provider: str
    policy_number: str
    group_number: Optional[str] = None
    verification_status: str = "pending"


class CurrentVitals(BaseModel):
    heart_rate: Optional[int] = None
    blood_pressure: Optional[str] = None
    oxygen_saturation: Optional[int] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None


class PatientBase(BaseModel):
    full_name: str
    date_of_birth: date
    gender: Gender
    weight_kg: float = Field(..., gt=0)
    diagnosis: str
    acuity_level: AcuityLevel

    # ✅ Added blood group
    blood_group: BloodGroup

    allergies: List[str] = []
    current_vitals: Optional[CurrentVitals] = None
    special_equipment_needed: List[str] = []
    insurance_details: InsuranceDetails
    next_of_kin: NextOfKin


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    diagnosis: Optional[str] = None
    acuity_level: Optional[AcuityLevel] = None
    blood_group: Optional[BloodGroup] = None   # ✅ Added here
    allergies: Optional[List[str]] = None
    current_vitals: Optional[CurrentVitals] = None
    special_equipment_needed: Optional[List[str]] = None


class Patient(PatientBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}

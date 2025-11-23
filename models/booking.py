from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime, date, time
from .patient import Patient, AcuityLevel
from .hospital import Hospital
from .aircraft import Aircraft
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

class BookingStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    EN_ROUTE = "en_route"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class EquipmentType(str, Enum):
    VENTILATOR = "ventilator"
    ECG_MONITOR = "ecg_monitor"
    DEFIBRILLATOR = "defibrillator"
    OXYGEN_SUPPLY = "oxygen_supply"
    INFUSION_PUMP = "infusion_pump"
    PATIENT_MONITOR = "patient_monitor"

class BookingBase(BaseModel):
    patient_id: str
    urgency: AcuityLevel
    origin_hospital_id: str
    destination_hospital_id: str
    preferred_date: date  # Keep as date for API
    preferred_time: time  # Keep as time for API
    required_equipment: List[EquipmentType]
    special_instructions: Optional[str] = None

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    urgency: Optional[AcuityLevel] = None
    preferred_date: Optional[date] = None
    preferred_time: Optional[time] = None
    required_equipment: Optional[List[EquipmentType]] = None
    special_instructions: Optional[str] = None
    status: Optional[BookingStatus] = None
    assigned_aircraft_id: Optional[str] = None
    assigned_crew_ids: Optional[List[str]] = None
    actual_cost: Optional[float] = None  # Add this line
    flight_duration: Optional[int] = None 

class Booking(BookingBase):
    id: str
    status: BookingStatus
    assigned_aircraft_id: Optional[str] = None
    assigned_crew_ids: List[str] = []
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    flight_duration: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}

class BookingWithDetails(Booking):
    patient: Optional[Patient] = None
    origin_hospital: Optional[Hospital] = None
    destination_hospital: Optional[Hospital] = None
    assigned_aircraft: Optional[Aircraft] = None

class FlightSchedule(BaseModel):
    booking_id: str
    aircraft_id: str
    crew_ids: List[str]
    scheduled_departure: datetime
    scheduled_arrival: datetime
    actual_departure: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    route_coordinates: List[List[float]] = []
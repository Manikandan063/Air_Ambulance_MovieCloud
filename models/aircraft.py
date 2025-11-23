from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime, date

class AircraftType(str, Enum):
    HELICOPTER = "helicopter"
    FIXED_WING = "fixed_wing"
    JET = "jet"

class AircraftStatus(str, Enum):
    AVAILABLE = "available"
    IN_MAINTENANCE = "in_maintenance"
    IN_USE = "in_use"
    OUT_OF_SERVICE = "out_of_service"

class MedicalEquipment(BaseModel):
    name: str
    quantity: int
    operational: bool = True

class AircraftBase(BaseModel):
    aircraft_type: AircraftType
    registration: str
    airline_operator: str
    range_km: int = Field(..., gt=0)
    speed_kmh: int = Field(..., gt=0)
    max_payload_kg: int = Field(..., gt=0)
    cabin_configuration: str
    base_location: str
    medical_equipment: List[MedicalEquipment]
    status: AircraftStatus = AircraftStatus.AVAILABLE

class AircraftCreate(AircraftBase):
    pass

class AircraftUpdate(BaseModel):
    aircraft_type: Optional[AircraftType] = None
    registration: Optional[str] = None
    range_km: Optional[int] = None
    speed_kmh: Optional[int] = None
    max_payload_kg: Optional[int] = None
    cabin_configuration: Optional[str] = None
    base_location: Optional[str] = None
    status: Optional[AircraftStatus] = None

class MaintenanceRecord(BaseModel):
    id: str
    aircraft_id: str
    maintenance_type: str
    description: str
    date_performed: date
    next_due_date: date
    cost: float
    performed_by: str

class Aircraft(AircraftBase):
    id: str
    created_at: datetime
    updated_at: datetime
    maintenance_records: List[MaintenanceRecord] = []

    class Config:
        from_attributes = True
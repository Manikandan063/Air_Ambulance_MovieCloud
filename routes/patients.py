from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.patient import Patient, PatientCreate, PatientUpdate, AcuityLevel
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime, date
import logging
import json

router = APIRouter(prefix="/api/patients", tags=["patients"])
logger = logging.getLogger(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


# =====================================================
# CREATE PATIENT
# =====================================================
@router.post("/", response_model=Patient)
async def create_patient(
    patient_data: PatientCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    allowed_roles = [
        UserRole.SUPERADMIN,
        UserRole.DISPATCHER,
        UserRole.HOSPITAL_STAFF,
        UserRole.DOCTOR,
    ]

    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    try:
        patients_collection = get_collection("patients")

        patient_dict = json.loads(patient_data.json())

        # Convert date_of_birth → datetime
        if patient_dict.get("date_of_birth"):
            patient_dict["date_of_birth"] = datetime.fromisoformat(patient_dict["date_of_birth"])

        patient_dict["created_at"] = patient_dict["updated_at"] = datetime.utcnow()
        patient_dict["created_by"] = str(current_user.id)

        result = patients_collection.insert_one(patient_dict)
        inserted = patients_collection.find_one({"_id": result.inserted_id})

        inserted["id"] = str(inserted["_id"])

        if isinstance(inserted.get("date_of_birth"), datetime):
            inserted["date_of_birth"] = inserted["date_of_birth"].date()

        return Patient(**inserted)

    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=500, detail="Error creating patient")


# =====================================================
# GET ALL PATIENTS
# =====================================================
@router.get("/", response_model=List[Patient])
async def get_patients(
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
    acuity_level: Optional[AcuityLevel] = None
):
    try:
        patients_collection = get_collection("patients")
        query = {}

        if acuity_level:
            query["acuity_level"] = acuity_level.value

        cursor = patients_collection.find(query).skip(skip).limit(limit)

        patients = []
        for patient in cursor:
            patient_dict = dict(patient)
            patient_dict["id"] = str(patient["_id"])

            if isinstance(patient_dict.get("date_of_birth"), datetime):
                patient_dict["date_of_birth"] = patient_dict["date_of_birth"].date()

            patients.append(Patient(**patient_dict))

        return patients

    except Exception:
        raise HTTPException(status_code=500, detail="Error retrieving patients")


# =====================================================
# GET PATIENT BY ID
# =====================================================
@router.get("/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    try:
        patients_collection = get_collection("patients")
        patient = patients_collection.find_one({"_id": ObjectId(patient_id)})

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        patient["id"] = str(patient["_id"])

        if isinstance(patient.get("date_of_birth"), datetime):
            patient["date_of_birth"] = patient["date_of_birth"].date()

        return Patient(**patient)

    except Exception:
        raise HTTPException(status_code=500, detail="Error retrieving patient")


# =====================================================
# UPDATE PATIENT
# =====================================================
@router.put("/{patient_id}", response_model=Patient)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    allowed_roles = [
        UserRole.SUPERADMIN,
        UserRole.DISPATCHER,
        UserRole.HOSPITAL_STAFF,
        UserRole.DOCTOR,
    ]

    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    try:
        patients_collection = get_collection("patients")
        existing = patients_collection.find_one({"_id": ObjectId(patient_id)})

        if not existing:
            raise HTTPException(status_code=404, detail="Patient not found")

        update_data = patient_update.dict(exclude_unset=True)

        # Handle nested objects
        for key, value in update_data.items():
            if hasattr(value, "dict"):
                update_data[key] = value.dict()

        # Convert date_of_birth
        if update_data.get("date_of_birth"):
            dob = update_data["date_of_birth"]
            if isinstance(dob, date):
                update_data["date_of_birth"] = datetime.combine(dob, datetime.min.time())
            else:
                update_data["date_of_birth"] = datetime.fromisoformat(dob)

        update_data["updated_at"] = datetime.utcnow()

        patients_collection.update_one({"_id": ObjectId(patient_id)}, {"$set": update_data})

        updated = patients_collection.find_one({"_id": ObjectId(patient_id)})
        updated["id"] = str(updated["_id"])

        if isinstance(updated.get("date_of_birth"), datetime):
            updated["date_of_birth"] = updated["date_of_birth"].date()

        return Patient(**updated)

    except Exception:
        raise HTTPException(status_code=500, detail="Error updating patient")


# =====================================================
# DELETE PATIENT (NEW)
# =====================================================
@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    allowed_roles = [
        UserRole.SUPERADMIN,
        UserRole.DISPATCHER,
        UserRole.HOSPITAL_STAFF,
        UserRole.DOCTOR,
    ]

    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not ObjectId.is_valid(patient_id):
        raise HTTPException(status_code=400, detail="Invalid patient ID")

    try:
        patients_collection = get_collection("patients")
        result = patients_collection.delete_one({"_id": ObjectId(patient_id)})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Patient not found")

        return {"message": "Patient deleted successfully"}

    except Exception:
        raise HTTPException(status_code=500, detail="Error deleting patient")


# =====================================================
# CRITICAL COUNT
# =====================================================
@router.get("/critical/count")
async def get_critical_patients_count(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    try:
        patients_collection = get_collection("patients")
        count = patients_collection.count_documents({"acuity_level": "critical"})
        return {"critical_patients_count": count}
    except Exception:
        raise HTTPException(status_code=500, detail="Error getting critical patients count")

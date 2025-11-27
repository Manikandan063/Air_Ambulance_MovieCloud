# routes/hospital_staff.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database.connection import get_collection
from models.hospital import HospitalStaff, StaffLogin
from models.user import User, UserRole
from utils.auth import get_password_hash, verify_password, create_access_token, decode_access_token
from bson import ObjectId

router = APIRouter(prefix="/api/hospital-staff", tags=["Hospital Staff"])

# Separate OAuth2 scheme for hospital staff login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/hospital-staff/login")

# ======================================================================
# DEPENDENCY: GET CURRENT HOSPITAL STAFF FROM TOKEN
# ======================================================================
async def get_current_hospital_staff(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload or payload.get("type") != "hospital_staff":
        raise HTTPException(status_code=403, detail="Only hospital staff can access this")

    hospitals = get_collection("hospitals")
    hospital = hospitals.find_one(
        {"_id": ObjectId(payload["hospital_id"])},
        {"staff": 1, "hospital_name": 1}
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    staff_data = next((s for s in hospital.get("staff", []) if s["id"] == payload["staff_id"]), None)
    if not staff_data:
        raise HTTPException(status_code=404, detail="Staff not found")

    return {
        "hospital_id": payload["hospital_id"],
        "hospital_name": hospital["hospital_name"],
        "staff": staff_data
    }


# ======================================================================
# ADD STAFF (Only SuperAdmin)
# ======================================================================
@router.post("/{hospital_id}/add")
async def add_hospital_staff(
    hospital_id: str,
    staff: HospitalStaff,
    token: str = Depends(oauth2_scheme)
):
    # Verify superadmin
    payload = decode_access_token(token)
    if not payload or payload.get("role") != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only superadmin can add staff")

    hospitals = get_collection("hospitals")
    hospital = hospitals.find_one({"_id": ObjectId(hospital_id)})
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    for s in hospital.get("staff", []):
        if s["email"] == staff.email:
            raise HTTPException(status_code=400, detail="Staff email already exists")

    staff_data = staff.model_dump()
    staff_data["id"] = str(ObjectId())
    staff_data["password"] = get_password_hash(staff.password)

    hospitals.update_one(
        {"_id": ObjectId(hospital_id)},
        {"$push": {"staff": staff_data}}
    )

    return {"message": "Staff added successfully", "staff": staff_data}


# ======================================================================
# STAFF LOGIN
# ======================================================================
@router.post("/login")
async def hospital_staff_login(data: StaffLogin):
    hospitals = get_collection("hospitals")

    hospital = hospitals.find_one(
        {"staff.email": data.email},
        {"hospital_name": 1, "staff.$": 1}
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Staff not found")

    staff = hospital["staff"][0]

    if not verify_password(data.password, staff["password"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token_payload = {
        "sub": staff["email"],
        "staff_id": staff["id"],
        "hospital_id": str(hospital["_id"]),
        "hospital_name": hospital["hospital_name"],
        "role": staff["role"],
        "type": "hospital_staff"
    }

    access_token = create_access_token(token_payload)

    return {"access_token": access_token, "token_type": "bearer"}


# ======================================================================
# GET CURRENT LOGGED-IN STAFF
# ======================================================================
@router.get("/me")
async def me(current_staff=Depends(get_current_hospital_staff)):
    return current_staff


# ======================================================================
# GET ALL STAFF OF A HOSPITAL
# ======================================================================
@router.get("/{hospital_id}/staff")
async def get_hospital_staff(
    hospital_id: str,
    token: str = Depends(oauth2_scheme)
):
    hospitals = get_collection("hospitals")
    hospital = hospitals.find_one({"_id": ObjectId(hospital_id)})

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    return hospital.get("staff", [])


# ======================================================================
# DELETE STAFF (Only SuperAdmin)
# ======================================================================
@router.delete("/{hospital_id}/{staff_id}")
async def delete_staff(
    hospital_id: str,
    staff_id: str,
    token: str = Depends(oauth2_scheme)
):
    payload = decode_access_token(token)
    if not payload or payload.get("role") != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only superadmin can delete staff")

    hospitals = get_collection("hospitals")
    result = hospitals.update_one(
        {"_id": ObjectId(hospital_id)},
        {"$pull": {"staff": {"id": staff_id}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Staff not found or already deleted")

    return {"message": "Staff deleted successfully"}

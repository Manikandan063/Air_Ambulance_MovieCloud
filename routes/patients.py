from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.patient import Patient, PatientCreate, PatientUpdate, AcuityLevel, Gender
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

@router.post("/", response_model=Patient)
async def create_patient(
    patient_data: PatientCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create a new patient"""
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.HOSPITAL_STAFF, UserRole.DOCTOR]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        patients_collection = get_collection("patients")
        
        # DEBUG: Get database and collection info
        db_name = patients_collection.database.name
        collection_name = patients_collection.name
        logger.info(f" Using database: {db_name}, collection: {collection_name}")
        
        # Count documents before insertion
        count_before = patients_collection.count_documents({})
        logger.info(f" Patients count BEFORE insertion: {count_before}")
        
        # Convert Pydantic model to JSON string first, then to dict to ensure proper serialization
        patient_json = patient_data.json()
        patient_dict = json.loads(patient_json)
        
        logger.info(f" Creating patient with data: {json.dumps(patient_dict, cls=CustomJSONEncoder, indent=2)}")
        logger.info(f" Current user ID: {current_user.id}, Role: {current_user.role}")
        
        # Convert date string to datetime for MongoDB
        if 'date_of_birth' in patient_dict and patient_dict['date_of_birth']:
            patient_dict['date_of_birth'] = datetime.fromisoformat(patient_dict['date_of_birth'])
        
        # Add metadata
        patient_dict["created_at"] = patient_dict["updated_at"] = datetime.utcnow()
        patient_dict["created_by"] = str(current_user.id)
        
        logger.info(f" Final patient data for MongoDB: {json.dumps(patient_dict, cls=CustomJSONEncoder, indent=2)}")
        
        # Test database connection
        try:
            patients_collection.database.command('ping')
            logger.info(" Database connection successful")
        except Exception as db_error:
            logger.error(f" Database connection failed: {db_error}")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Insert into database
        try:
            result = patients_collection.insert_one(patient_dict)
            
            if not result.acknowledged:
                logger.error(" Insert operation not acknowledged by MongoDB")
                raise HTTPException(status_code=500, detail="Insert operation failed")
            
            patient_id = str(result.inserted_id)
            logger.info(f" Insert operation acknowledged, patient ID: {patient_id}")
            
        except Exception as insert_error:
            logger.error(f" Error during insert operation: {insert_error}")
            raise HTTPException(status_code=500, detail=f"Insert operation failed: {str(insert_error)}")
        
        # Verify the insertion by reading back
        try:
            inserted_patient = patients_collection.find_one({"_id": result.inserted_id})
            if inserted_patient:
                logger.info(f" Patient created successfully with ID: {patient_id}")
                logger.info(f" Patient name: {inserted_patient.get('full_name', 'N/A')}")
            else:
                logger.error(" Insertion verification failed - patient not found after insert")
                raise HTTPException(status_code=500, detail="Patient creation verification failed")
                
        except Exception as verify_error:
            logger.error(f" Error during insertion verification: {verify_error}")
            raise HTTPException(status_code=500, detail="Verification of patient creation failed")
        
        # Count documents after insertion
        count_after = patients_collection.count_documents({})
        logger.info(f" Patients count AFTER insertion: {count_after}")
        
        # List all patients for debugging
        all_patients = list(patients_collection.find({}, {"full_name": 1, "_id": 1}).limit(5))
        logger.info(f" Recent patients in collection: {all_patients}")
        
        # Prepare response data
        response_data = dict(inserted_patient)
        response_data["id"] = patient_id
        
        # Convert datetime back to date for response
        if 'date_of_birth' in response_data and isinstance(response_data['date_of_birth'], datetime):
            response_data['date_of_birth'] = response_data['date_of_birth'].date()
        
        # Convert ObjectId to string for nested documents if any
        for key, value in response_data.items():
            if isinstance(value, ObjectId):
                response_data[key] = str(value)
        
        logger.info(f" Successfully returning patient with ID: {patient_id}")
        return Patient(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Unexpected error creating patient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating patient: {str(e)}")

@router.get("/", response_model=List[Patient])
async def get_patients(
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
    acuity_level: Optional[AcuityLevel] = None
):
    """Get patients with optional acuity level filter"""
    try:
        patients_collection = get_collection("patients")
        
        # Debug info
        db_name = patients_collection.database.name
        total_count = patients_collection.count_documents({})
        logger.info(f" Retrieving patients from {db_name}.patients, total documents: {total_count}")
        
        query = {}
        if acuity_level:
            query["acuity_level"] = acuity_level.value
        
        cursor = patients_collection.find(query).skip(skip).limit(limit)
        patient_list = []
        
        for patient in cursor:
            try:
                patient_data = dict(patient)
                patient_data["id"] = str(patient["_id"])
                
                if 'date_of_birth' in patient_data and isinstance(patient_data['date_of_birth'], datetime):
                    patient_data['date_of_birth'] = patient_data['date_of_birth'].date()
                
                patient_list.append(Patient(**patient_data))
            except Exception as parse_error:
                logger.warning(f"⚠️ Error parsing patient {patient.get('_id')}: {parse_error}")
                continue
        
        logger.info(f"📋 Retrieved {len(patient_list)} patients")
        return patient_list
    
    except Exception as e:
        logger.error(f"❌ Error retrieving patients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving patients")

@router.get("/{patient_id}", response_model=Patient)
async def get_patient(patient_id: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get a specific patient by ID"""
    try:
        patients_collection = get_collection("patients")
        
        # Validate ObjectId format
        if not ObjectId.is_valid(patient_id):
            raise HTTPException(status_code=400, detail="Invalid patient ID format")
        
        logger.info(f"🔍 Retrieving patient with ID: {patient_id}")
        
        patient_data = patients_collection.find_one({"_id": ObjectId(patient_id)})
        
        if not patient_data:
            logger.warning(f"⚠️ Patient not found with ID: {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Convert to response format
        patient_dict = dict(patient_data)
        patient_dict["id"] = str(patient_data["_id"])
        
        if 'date_of_birth' in patient_dict and isinstance(patient_dict['date_of_birth'], datetime):
            patient_dict['date_of_birth'] = patient_dict['date_of_birth'].date()
        
        logger.info(f"✅ Successfully retrieved patient: {patient_id}")
        return Patient(**patient_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving patient")

@router.put("/{patient_id}", response_model=Patient)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update a patient"""
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.HOSPITAL_STAFF, UserRole.DOCTOR]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        patients_collection = get_collection("patients")
        
        # Validate ObjectId format
        if not ObjectId.is_valid(patient_id):
            raise HTTPException(status_code=400, detail="Invalid patient ID format")
        
        # Check if patient exists
        existing_patient = patients_collection.find_one({"_id": ObjectId(patient_id)})
        if not existing_patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        update_data = {k: v for k, v in patient_update.dict(exclude_unset=True).items() if v is not None}
        
        # Convert nested models to dicts
        def convert_nested_models(data):
            if isinstance(data, dict):
                return {k: convert_nested_models(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [convert_nested_models(item) for item in data]
            elif hasattr(data, 'dict'):
                return data.dict()
            else:
                return data
        
        update_data = convert_nested_models(update_data)
        
        # Convert date to datetime for MongoDB update
        if 'date_of_birth' in update_data and update_data['date_of_birth']:
            if isinstance(update_data['date_of_birth'], str):
                update_data['date_of_birth'] = datetime.fromisoformat(update_data['date_of_birth'].replace('Z', '+00:00'))
            else:
                update_data['date_of_birth'] = datetime.combine(
                    update_data['date_of_birth'], 
                    datetime.min.time()
                )
        
        update_data["updated_at"] = datetime.utcnow()
        
        logger.info(f"🔍 Updating patient {patient_id} with data: {json.dumps(update_data, cls=CustomJSONEncoder, indent=2)}")
        
        result = patients_collection.update_one(
            {"_id": ObjectId(patient_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to patient {patient_id}")
            raise HTTPException(status_code=404, detail="Patient not found or no changes made")
        
        # Get updated patient
        patient_data = patients_collection.find_one({"_id": ObjectId(patient_id)})
        
        # Convert to response format
        patient_dict = dict(patient_data)
        patient_dict["id"] = str(patient_data["_id"])
        
        if 'date_of_birth' in patient_dict and isinstance(patient_dict['date_of_birth'], datetime):
            patient_dict['date_of_birth'] = patient_dict['date_of_birth'].date()
        
        logger.info(f"✅ Patient updated: {patient_id}")
        return Patient(**patient_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating patient")

@router.get("/critical/count")
async def get_critical_patients_count(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get count of critical patients"""
    try:
        patients_collection = get_collection("patients")
        count = patients_collection.count_documents({"acuity_level": "critical"})
        
        logger.info(f"📊 Critical patients count: {count}")
        
        return {"critical_patients_count": count}
    
    except Exception as e:
        logger.error(f"❌ Error getting critical patients count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting critical patients count")

# ===== DEBUGGING ENDPOINTS =====

@router.get("/debug/database-info")
async def debug_database_info(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get detailed database information"""
    try:
        patients_collection = get_collection("patients")
        
        db = patients_collection.database
        client = db.client
        
        # Get all databases
        database_names = client.list_database_names()
        
        # Get all collections in current database
        collection_names = db.list_collection_names()
        
        # Get detailed info about patients collection
        patients_count = patients_collection.count_documents({})
        
        # Get sample of patients
        sample_patients = list(patients_collection.find().limit(5))
        
        return {
            "current_database": db.name,
            "all_databases": database_names,
            "collections_in_current_db": collection_names,
            "patients_count": patients_count,
            "sample_patients": sample_patients,
            "connection_info": f"Connected to {client.address}"
        }
    except Exception as e:
        logger.error(f"❌ Debug error: {e}", exc_info=True)
        return {"error": str(e)}

@router.post("/debug/test-insert")
async def debug_test_insert(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Test insertion with simple document"""
    try:
        patients_collection = get_collection("patients")
        
        db_name = patients_collection.database.name
        count_before = patients_collection.count_documents({})
        
        # Simple test document
        test_doc = {
            "test": True,
            "timestamp": datetime.utcnow(),
            "message": "Test insertion from FastAPI",
            "created_by": str(current_user.id),
            "simple_field": "This should appear in MongoDB",
            "database": db_name,
            "created_at": datetime.utcnow()
        }
        
        logger.info(f"🔍 Attempting to insert test document into {db_name}.patients")
        logger.info(f"🔍 Count before: {count_before}")
        
        result = patients_collection.insert_one(test_doc)
        
        # Verify
        inserted = patients_collection.find_one({"_id": result.inserted_id})
        count_after = patients_collection.count_documents({})
        
        return {
            "success": True,
            "inserted_id": str(result.inserted_id),
            "verified": bool(inserted),
            "database": db_name,
            "collection": "patients",
            "count_before": count_before,
            "count_after": count_after,
            "document": inserted
        }
        
    except Exception as e:
        logger.error(f"❌ Test insert error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@router.delete("/debug/cleanup-test")
async def debug_cleanup_test(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Clean up test documents"""
    try:
        patients_collection = get_collection("patients")
        
        result = patients_collection.delete_many({"test": True})
        
        return {
            "success": True,
            "deleted_count": result.deleted_count,
            "message": f"Deleted {result.deleted_count} test documents"
        }
        
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")
        return {"success": False, "error": str(e)}
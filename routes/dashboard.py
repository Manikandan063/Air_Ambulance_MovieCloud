from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database.connection import get_collection
from models.booking import Booking, BookingWithDetails, BookingStatus, EquipmentType
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime, time, date, timedelta
import logging
import traceback

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

def safe_object_id_conversion(obj_id):
    """Safely convert to ObjectId"""
    try:
        if obj_id and ObjectId.is_valid(obj_id):
            return ObjectId(obj_id)
        return None
    except Exception:
        return None

def normalize_equipment_data(equipment_list: List) -> List[EquipmentType]:
    """Convert equipment data to proper enum values"""
    if not equipment_list:
        return []
    
    normalized_equipment = []
    for equipment in equipment_list:
        try:
            if isinstance(equipment, EquipmentType):
                normalized_equipment.append(equipment)
            elif isinstance(equipment, str):
                normalized = equipment.lower().replace(' ', '_')
                normalized_equipment.append(EquipmentType(normalized))
        except Exception:
            logger.warning(f"Could not normalize equipment: {equipment}")
            continue
    
    return normalized_equipment

def convert_booking_data(booking_data: dict) -> dict:
    """Convert booking data from database format to API format"""
    try:
        if not booking_data:
            return {}
            
        converted_data = booking_data.copy()
        converted_data["id"] = str(booking_data.get("_id", ""))
        
        # Handle missing required fields with safe defaults
        converted_data.setdefault("origin_hospital_id", "unknown")
        converted_data.setdefault("destination_hospital_id", "unknown")
        converted_data.setdefault("patient_id", None)
        converted_data.setdefault("urgency", "stable")
        converted_data.setdefault("status", BookingStatus.PENDING)
        converted_data.setdefault("required_equipment", [])
        converted_data.setdefault("pickup_location", "Unknown Location")
        converted_data.setdefault("destination", "Unknown Destination")
        converted_data.setdefault("assigned_crew_ids", [])
        converted_data.setdefault("estimated_cost", 0.0)
        converted_data.setdefault("actual_cost", 0.0)
        converted_data.setdefault("flight_duration", 0)
        converted_data.setdefault("created_by", "unknown")
        converted_data.setdefault("special_instructions", "")
        
        # Convert date/time fields safely
        try:
            if 'preferred_date' in converted_data:
                if isinstance(converted_data['preferred_date'], datetime):
                    converted_data['preferred_date'] = converted_data['preferred_date'].date()
                elif converted_data['preferred_date'] is None:
                    converted_data['preferred_date'] = date.today()
            else:
                converted_data['preferred_date'] = date.today()
        except Exception as e:
            logger.warning(f"Error converting preferred_date: {e}")
            converted_data['preferred_date'] = date.today()
        
        try:
            if 'preferred_time' in converted_data:
                if isinstance(converted_data['preferred_time'], str):
                    for time_format in ['%H:%M:%S', '%H:%M']:
                        try:
                            converted_data['preferred_time'] = datetime.strptime(converted_data['preferred_time'], time_format).time()
                            break
                        except ValueError:
                            continue
                    else:
                        converted_data['preferred_time'] = time(12, 0)
                elif converted_data['preferred_time'] is None:
                    converted_data['preferred_time'] = time(12, 0)
            else:
                converted_data['preferred_time'] = time(12, 0)
        except Exception as e:
            logger.warning(f"Error converting preferred_time: {e}")
            converted_data['preferred_time'] = time(12, 0)
        
        # Normalize equipment data
        try:
            if 'required_equipment' in converted_data and converted_data['required_equipment']:
                converted_data['required_equipment'] = normalize_equipment_data(converted_data['required_equipment'])
        except Exception as e:
            logger.warning(f"Error normalizing equipment: {e}")
            converted_data['required_equipment'] = []
        
        return converted_data
    
    except Exception as e:
        logger.error(f"Error in convert_booking_data: {e}")
        return {}

async def get_booking_with_details(booking_data: dict) -> Optional[BookingWithDetails]:
    """Convert raw booking data to BookingWithDetails with related data"""
    try:
        if not booking_data:
            return None
            
        patients_collection = get_collection("patients")
        hospitals_collection = get_collection("hospitals")
        aircraft_collection = get_collection("aircraft")
        
        booking_dict = convert_booking_data(booking_data)
        if not booking_dict:
            return None
        
        # Add patient details
        patient_id = booking_dict.get("patient_id")
        if patient_id and patient_id != "unknown":
            try:
                obj_id = safe_object_id_conversion(patient_id)
                if obj_id:
                    patient = patients_collection.find_one({"_id": obj_id})
                    if patient:
                        booking_dict["patient"] = {
                            "id": str(patient.get("_id", "")),
                            "full_name": patient.get("full_name", "Unknown Patient"),
                            "medical_record_number": patient.get("medical_record_number", ""),
                            "acuity_level": patient.get("acuity_level", "stable"),
                            "age": patient.get("age"),
                            "condition": patient.get("condition", ""),
                            "weight": patient.get("weight"),
                            "allergies": patient.get("allergies", [])
                        }
            except Exception as e:
                logger.warning(f"Could not fetch patient details: {e}")
        
        # Add origin hospital details
        origin_hospital_id = booking_dict.get("origin_hospital_id")
        if origin_hospital_id and origin_hospital_id != "unknown":
            try:
                obj_id = safe_object_id_conversion(origin_hospital_id)
                if obj_id:
                    origin_hospital = hospitals_collection.find_one({"_id": obj_id})
                    if origin_hospital:
                        booking_dict["origin_hospital"] = {
                            "id": str(origin_hospital.get("_id", "")),
                            "name": origin_hospital.get("name", "Unknown Hospital"),
                            "address": origin_hospital.get("address", ""),
                            "contact_number": origin_hospital.get("contact_number", "")
                        }
            except Exception as e:
                logger.warning(f"Could not fetch origin hospital details: {e}")
        
        # Add destination hospital details
        destination_hospital_id = booking_dict.get("destination_hospital_id")
        if destination_hospital_id and destination_hospital_id != "unknown":
            try:
                obj_id = safe_object_id_conversion(destination_hospital_id)
                if obj_id:
                    dest_hospital = hospitals_collection.find_one({"_id": obj_id})
                    if dest_hospital:
                        booking_dict["destination_hospital"] = {
                            "id": str(dest_hospital.get("_id", "")),
                            "name": dest_hospital.get("name", "Unknown Hospital"),
                            "address": dest_hospital.get("address", ""),
                            "contact_number": dest_hospital.get("contact_number", "")
                        }
            except Exception as e:
                logger.warning(f"Could not fetch destination hospital details: {e}")
        
        # Add assigned aircraft details
        assigned_aircraft_id = booking_dict.get("assigned_aircraft_id")
        if assigned_aircraft_id:
            try:
                obj_id = safe_object_id_conversion(assigned_aircraft_id)
                if obj_id:
                    aircraft = aircraft_collection.find_one({"_id": obj_id})
                    if aircraft:
                        booking_dict["assigned_aircraft"] = {
                            "id": str(aircraft.get("_id", "")),
                            "tail_number": aircraft.get("tail_number", ""),
                            "model": aircraft.get("model", ""),
                            "capacity": aircraft.get("capacity", 0)
                        }
            except Exception as e:
                logger.warning(f"Could not fetch aircraft details: {e}")
        
        # Ensure all optional fields are present
        booking_dict.setdefault("patient", None)
        booking_dict.setdefault("origin_hospital", None)
        booking_dict.setdefault("destination_hospital", None)
        booking_dict.setdefault("assigned_aircraft", None)
        
        return BookingWithDetails(**booking_dict)
    
    except Exception as e:
        logger.error(f"Error in get_booking_with_details: {e}")
        logger.error(traceback.format_exc())
        return None

# READ - Get dashboard statistics
@router.get("/stats")
async def get_dashboard_stats(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Get comprehensive dashboard statistics
    """
    try:
        logger.info(f"📊 Getting dashboard stats for user: {current_user.email}, role: {current_user.role}")
        
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        # Base query for role-based filtering
        base_query = {}
        if current_user.role == UserRole.HOSPITAL_STAFF:
            base_query["created_by"] = str(current_user.id)
            logger.info(f"Hospital staff query: {base_query}")
        
        # Initialize all counts to zero first
        status_counts = {
            "pending": 0,
            "approved": 0,
            "scheduled": 0,
            "en_route": 0,
            "completed": 0,
            "cancelled": 0
        }
        
        urgency_counts = {
            "critical": 0,
            "urgent": 0,
            "stable": 0
        }
        
        try:
            # Get total bookings count
            total_bookings = bookings_collection.count_documents(base_query)
            logger.info(f"Total bookings: {total_bookings}")
            
            # Get status counts - handle each status separately to isolate errors
            for status in status_counts.keys():
                try:
                    count = bookings_collection.count_documents({**base_query, "status": status})
                    status_counts[status] = count
                    logger.info(f"Status {status}: {count}")
                except Exception as status_error:
                    logger.warning(f"Error counting status {status}: {status_error}")
                    status_counts[status] = 0
            
            # Get urgency counts - handle each urgency separately
            for urgency in urgency_counts.keys():
                try:
                    count = bookings_collection.count_documents({**base_query, "urgency": urgency})
                    urgency_counts[urgency] = count
                    logger.info(f"Urgency {urgency}: {count}")
                except Exception as urgency_error:
                    logger.warning(f"Error counting urgency {urgency}: {urgency_error}")
                    urgency_counts[urgency] = 0
            
        except Exception as count_error:
            logger.error(f"Error in counting operations: {count_error}")
            # Continue with zero counts rather than failing completely
        
        # Revenue statistics (only for authorized roles)
        revenue_stats = {}
        if current_user.role in [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.AIRLINE_COORDINATOR]:
            try:
                completed_bookings = bookings_collection.find({**base_query, "status": BookingStatus.COMPLETED})
                
                total_revenue = 0
                total_estimated_revenue = 0
                completed_count = 0
                
                async for booking in completed_bookings:
                    try:
                        total_revenue += float(booking.get('actual_cost', 0) or 0)
                        total_estimated_revenue += float(booking.get('estimated_cost', 0) or 0)
                        completed_count += 1
                    except (ValueError, TypeError) as conv_error:
                        logger.warning(f"Error converting cost values: {conv_error}")
                        continue
                
                avg_revenue = total_revenue / completed_count if completed_count > 0 else 0
                
                revenue_stats = {
                    "total_revenue": round(total_revenue, 2),
                    "total_estimated_revenue": round(total_estimated_revenue, 2),
                    "completed_bookings_count": completed_count,
                    "average_revenue_per_booking": round(avg_revenue, 2)
                }
                logger.info(f"Revenue stats: {revenue_stats}")
            except Exception as revenue_error:
                logger.error(f"Error calculating revenue stats: {revenue_error}")
                revenue_stats = {
                    "total_revenue": 0,
                    "total_estimated_revenue": 0,
                    "completed_bookings_count": 0,
                    "average_revenue_per_booking": 0
                }
        
        # Patient statistics
        patient_stats = {}
        try:
            if current_user.role in [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.HOSPITAL_STAFF, UserRole.DOCTOR, UserRole.PARAMEDIC]:
                total_patients = patients_collection.count_documents({})
                
                # Patient acuity levels
                acuity_counts = {}
                for acuity in ["critical", "urgent", "stable"]:
                    try:
                        count = patients_collection.count_documents({"acuity_level": acuity})
                        acuity_counts[acuity] = count
                    except Exception as acuity_error:
                        logger.warning(f"Error counting acuity {acuity}: {acuity_error}")
                        acuity_counts[acuity] = 0
                
                patient_stats = {
                    "total_patients": total_patients,
                    "acuity_counts": acuity_counts
                }
                logger.info(f"Patient stats: {patient_stats}")
        except Exception as patient_error:
            logger.error(f"Error getting patient stats: {patient_error}")
            patient_stats = {
                "total_patients": 0,
                "acuity_counts": {"critical": 0, "urgent": 0, "stable": 0}
            }
        
        # Today's bookings
        today_bookings = 0
        try:
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_end = datetime.combine(date.today(), datetime.max.time())
            
            today_bookings = bookings_collection.count_documents({
                **base_query,
                "created_at": {
                    "$gte": today_start,
                    "$lte": today_end
                }
            })
            logger.info(f"Today's bookings: {today_bookings}")
        except Exception as today_error:
            logger.error(f"Error counting today's bookings: {today_error}")
        
        stats = {
            "bookings": {
                "total": total_bookings,
                "today": today_bookings,
                "by_status": status_counts,
                "by_urgency": urgency_counts
            },
            "revenue": revenue_stats,
            "patients": patient_stats,
            "user_role": current_user.role.value
        }
        
        logger.info(f"✅ Dashboard stats successfully retrieved for user {current_user.email}")
        return stats
    
    except Exception as e:
        logger.error(f"❌ Critical error retrieving dashboard stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving dashboard statistics: {str(e)}"
        )

# READ - Get recent bookings for dashboard
@router.get("/recent-bookings", response_model=List[BookingWithDetails])
async def get_recent_bookings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 10
):
    """
    Get recent bookings for dashboard display
    """
    try:
        logger.info(f"Getting recent bookings for user: {current_user.email}")
        
        bookings_collection = get_collection("bookings")
        
        # Role-based filtering
        query = {}
        if current_user.role == UserRole.HOSPITAL_STAFF:
            query["created_by"] = str(current_user.id)
        elif current_user.role in [UserRole.DOCTOR, UserRole.PARAMEDIC]:
            query["urgency"] = {"$in": ["critical", "urgent"]}
        
        cursor = bookings_collection.find(query).sort("created_at", -1).limit(limit)
        
        recent_bookings = []
        async for booking in cursor:
            try:
                booking_with_details = await get_booking_with_details(booking)
                if booking_with_details:
                    recent_bookings.append(booking_with_details)
            except Exception as e:
                logger.error(f"Error processing booking {booking.get('_id')}: {e}")
                continue
        
        logger.info(f"✅ Retrieved {len(recent_bookings)} recent bookings for user {current_user.email}")
        return recent_bookings
    
    except Exception as e:
        logger.error(f"❌ Error retrieving recent bookings: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving recent bookings"
        )

# READ - Get activity and transfers
@router.get("/activity-transfers")
async def get_activity_transfers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 20
):
    """
    Get recent activity and transfers for dashboard
    """
    try:
        logger.info(f"Getting activity transfers for user: {current_user.email}")
        
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        # Base query for role-based filtering
        base_query = {}
        if current_user.role == UserRole.HOSPITAL_STAFF:
            base_query["created_by"] = str(current_user.id)
        elif current_user.role in [UserRole.DOCTOR, UserRole.PARAMEDIC]:
            base_query["urgency"] = {"$in": ["critical", "urgent"]}
        
        # Get recent activities
        activities = []
        try:
            recent_activities_cursor = bookings_collection.find(base_query).sort("updated_at", -1).limit(limit)
            
            async for activity in recent_activities_cursor:
                try:
                    patient_name = "Unknown Patient"
                    patient_id = activity.get("patient_id")
                    
                    if patient_id:
                        obj_id = safe_object_id_conversion(patient_id)
                        if obj_id:
                            patient = patients_collection.find_one({"_id": obj_id})
                            if patient:
                                patient_name = patient.get("full_name", "Unknown Patient")
                    
                    status = activity.get("status", "unknown")
                    
                    status_descriptions = {
                        BookingStatus.PENDING: f"New booking created for {patient_name}",
                        BookingStatus.APPROVED: f"Booking approved for {patient_name}",
                        BookingStatus.SCHEDULED: f"Flight scheduled for {patient_name}",
                        BookingStatus.EN_ROUTE: f"Transport en route for {patient_name}",
                        BookingStatus.COMPLETED: f"Transport completed for {patient_name}",
                        BookingStatus.CANCELLED: f"Booking cancelled for {patient_name}"
                    }
                    
                    description = status_descriptions.get(status, f"Booking {status} for {patient_name}")
                    
                    activities.append({
                        "id": str(activity.get("_id", "")),
                        "type": "booking_update",
                        "status": status,
                        "urgency": activity.get("urgency", "stable"),
                        "timestamp": activity.get("updated_at", activity.get("created_at", datetime.utcnow())),
                        "description": description,
                        "patient_name": patient_name,
                        "booking_id": str(activity.get("_id", ""))
                    })
                except Exception as e:
                    logger.error(f"Error processing activity: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
        
        # Get recent transfers
        transfers = []
        try:
            recent_transfers_cursor = bookings_collection.find({
                **base_query,
                "status": BookingStatus.COMPLETED
            }).sort("updated_at", -1).limit(10)
            
            async for transfer in recent_transfers_cursor:
                try:
                    patient_name = "Unknown Patient"
                    patient_id = transfer.get("patient_id")
                    
                    if patient_id:
                        obj_id = safe_object_id_conversion(patient_id)
                        if obj_id:
                            patient = patients_collection.find_one({"_id": obj_id})
                            if patient:
                                patient_name = patient.get("full_name", "Unknown Patient")
                    
                    transfers.append({
                        "id": str(transfer.get("_id", "")),
                        "patient_name": patient_name,
                        "from_location": transfer.get("pickup_location", "Unknown Location"),
                        "to_location": transfer.get("destination", "Unknown Destination"),
                        "completed_at": transfer.get("updated_at", transfer.get("created_at", datetime.utcnow())),
                        "duration_minutes": transfer.get("flight_duration", 0),
                        "cost": transfer.get("actual_cost", 0),
                        "urgency": transfer.get("urgency", "stable")
                    })
                except Exception as e:
                    logger.error(f"Error processing transfer: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error getting transfers: {e}")
        
        result = {
            "activities": activities,
            "recent_transfers": transfers,
            "total_activities": len(activities),
            "total_transfers": len(transfers)
        }
        
        logger.info(f"✅ Retrieved {len(activities)} activities and {len(transfers)} transfers")
        return result
    
    except Exception as e:
        logger.error(f"❌ Error retrieving activity transfers: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving activity and transfers: {str(e)}"
        )

# Simple health check endpoint for dashboard
@router.get("/health")
async def dashboard_health_check():
    """Health check for dashboard endpoints"""
    try:
        bookings_collection = get_collection("bookings")
        count = bookings_collection.count_documents({})
        return {
            "status": "healthy",
            "total_bookings": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Dashboard health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard service unavailable"
        )
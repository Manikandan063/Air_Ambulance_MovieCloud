from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import List, Optional
from database.connection import get_collection
from models.booking import Booking, BookingCreate, BookingUpdate, BookingStatus, BookingWithDetails, EquipmentType
from models.user import User, UserRole
from routes.auth import get_current_active_user
from bson import ObjectId
from typing import Annotated
from datetime import datetime, time, date
import json
import random
import logging

router = APIRouter(prefix="/api/bookings", tags=["bookings"])
logger = logging.getLogger(__name__)

# Import NotificationService with fallback
try:
    from utils.notification import NotificationService
except ImportError:
    # Fallback mock service
    class NotificationService:
        @staticmethod
        async def send_booking_notification(booking, recipients, message, notification_type="info"):
            print(f"📧 MOCK: {message}")
        
        @staticmethod
        async def send_emergency_alert(booking, message):
            print(f"🚨 MOCK EMERGENCY: {message}")
        
        @staticmethod
        async def send_maintenance_reminder(aircraft_id, message):
            print(f"🔧 MOCK MAINTENANCE: {message}")
        
        @staticmethod
        async def send_system_notification(users, title, message, notification_type="info"):
            print(f"📢 MOCK SYSTEM: {title}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected_connections.append(connection)
        
        for connection in disconnected_connections:
            self.disconnect(connection)

manager = ConnectionManager()

def calculate_estimated_cost(booking_data: dict) -> float:
    base_cost = 5000
    urgency_multiplier = {
        "critical": 1.5,
        "urgent": 1.2,
        "stable": 1.0
    }
    
    equipment_cost = len(booking_data.get("required_equipment", [])) * 500
    return base_cost * urgency_multiplier.get(booking_data.get("urgency", "stable"), 1.0) + equipment_cost

def calculate_actual_cost(booking_data: dict, flight_duration: int) -> float:
    base_rate = 100
    urgency_multiplier = {
        "critical": 1.5,
        "urgent": 1.2,
        "stable": 1.0
    }
    
    equipment_cost = len(booking_data.get("required_equipment", [])) * 500
    return (base_rate * flight_duration * urgency_multiplier.get(booking_data.get("urgency", "stable"), 1.0)) + equipment_cost

def calculate_flight_duration() -> int:
    return random.randint(30, 180)

async def get_notification_recipients(booking: dict, current_user: User, action: str) -> List[User]:
    users_collection = get_collection("users")
    recipients = []
    
    try:
        recipients.append(current_user)
        
        if action in ["created", "updated", "emergency"]:
            dispatchers = users_collection.find({
                "role": {"$in": [UserRole.DISPATCHER, UserRole.SUPERADMIN, UserRole.AIRLINE_COORDINATOR]},
                "is_active": True
            })
            recipients.extend([User(**user) for user in dispatchers])
        
        if action == "emergency" or booking.get("urgency") == "critical":
            medical_staff = users_collection.find({
                "role": {"$in": [UserRole.DOCTOR, UserRole.PARAMEDIC]},
                "is_active": True
            })
            recipients.extend([User(**user) for user in medical_staff])
        
        unique_recipients = []
        seen_ids = set()
        for recipient in recipients:
            if str(recipient.id) not in seen_ids:
                unique_recipients.append(recipient)
                seen_ids.add(str(recipient.id))
        
        return unique_recipients
        
    except Exception as e:
        logger.error(f"Error getting notification recipients: {e}")
        return [current_user]

def normalize_equipment_data(equipment_list: List) -> List[EquipmentType]:
    """Convert equipment data to proper enum values"""
    normalized_equipment = []
    for equipment in equipment_list:
        if isinstance(equipment, EquipmentType):
            normalized_equipment.append(equipment)
        elif isinstance(equipment, str):
            # Normalize the string
            normalized = equipment.lower().replace(' ', '_')
            try:
                normalized_equipment.append(EquipmentType(normalized))
            except ValueError:
                # Handle common variations
                if 'ventilator' in normalized:
                    normalized_equipment.append(EquipmentType.VENTILATOR)
                elif 'ecg' in normalized or 'monitor' in normalized:
                    normalized_equipment.append(EquipmentType.ECG_MONITOR)
                elif 'defib' in normalized:
                    normalized_equipment.append(EquipmentType.DEFIBRILLATOR)
                elif 'oxygen' in normalized:
                    normalized_equipment.append(EquipmentType.OXYGEN_SUPPLY)
                elif 'infusion' in normalized:
                    normalized_equipment.append(EquipmentType.INFUSION_PUMP)
                elif 'patient' in normalized:
                    normalized_equipment.append(EquipmentType.PATIENT_MONITOR)
                else:
                    logger.warning(f"Unknown equipment type: {equipment}")
        else:
            logger.warning(f"Invalid equipment type: {equipment}")
    
    return normalized_equipment

def convert_booking_data(booking_data: dict) -> dict:
    """Convert booking data from database format to API format"""
    converted_data = dict(booking_data)
    converted_data["id"] = str(booking_data["_id"])
    
    # Handle missing required fields with defaults
    converted_data.setdefault("origin_hospital_id", "unknown")
    converted_data.setdefault("destination_hospital_id", "unknown")
    
    # Convert date/time fields
    if 'preferred_date' in converted_data:
        if isinstance(converted_data['preferred_date'], datetime):
            converted_data['preferred_date'] = converted_data['preferred_date'].date()
        elif converted_data['preferred_date'] is None:
            converted_data['preferred_date'] = date.today()
    else:
        converted_data['preferred_date'] = date.today()
    
    if 'preferred_time' in converted_data:
        if isinstance(converted_data['preferred_time'], str):
            try:
                converted_data['preferred_time'] = datetime.strptime(converted_data['preferred_time'], '%H:%M:%S').time()
            except ValueError:
                try:
                    converted_data['preferred_time'] = datetime.strptime(converted_data['preferred_time'], '%H:%M').time()
                except ValueError:
                    converted_data['preferred_time'] = time(12, 0)
        elif converted_data['preferred_time'] is None:
            converted_data['preferred_time'] = time(12, 0)
    else:
        converted_data['preferred_time'] = time(12, 0)
    
    # Normalize equipment data
    if 'required_equipment' in converted_data and converted_data['required_equipment']:
        converted_data['required_equipment'] = normalize_equipment_data(converted_data['required_equipment'])
    
    return converted_data

# CREATE - Create new booking
@router.post("/", response_model=Booking, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_data: BookingCreate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Create a new booking
    """
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.HOSPITAL_STAFF]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        booking_dict = booking_data.dict()
        
        # Get patient name
        patient_name = "Unknown Patient"
        if booking_dict.get("patient_id"):
            patient = patients_collection.find_one({"_id": ObjectId(booking_dict["patient_id"])})
            if patient:
                patient_name = patient.get("full_name", "Unknown Patient")
        
        # Prepare booking data for database
        if 'preferred_date' in booking_dict and booking_dict['preferred_date']:
            booking_dict['preferred_date'] = datetime.combine(
                booking_dict['preferred_date'], 
                datetime.min.time()
            )
        
        if 'preferred_time' in booking_dict and booking_dict['preferred_time']:
            booking_dict['preferred_time'] = booking_dict['preferred_time'].isoformat()
        
        # Normalize equipment data before saving
        if 'required_equipment' in booking_dict and booking_dict['required_equipment']:
            booking_dict['required_equipment'] = [eq.value for eq in normalize_equipment_data(booking_dict['required_equipment'])]
        
        # Set additional fields
        booking_dict["status"] = BookingStatus.PENDING
        booking_dict["assigned_crew_ids"] = []
        booking_dict["assigned_aircraft_id"] = None
        booking_dict["actual_cost"] = None
        booking_dict["flight_duration"] = None
        booking_dict["created_at"] = booking_dict["updated_at"] = datetime.utcnow()
        booking_dict["created_by"] = str(current_user.id)
        booking_dict["estimated_cost"] = calculate_estimated_cost(booking_dict)
        
        # Insert into database
        result = bookings_collection.insert_one(booking_dict)
        booking_id = str(result.inserted_id)
        
        # Retrieve the created booking
        created_booking = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        booking_response = convert_booking_data(created_booking)
        
        # Send notifications
        recipients = await get_notification_recipients(booking_response, current_user, "created")
        notification_message = f"New booking created for patient {patient_name}. Urgency: {booking_dict.get('urgency', 'unknown')}. Status: Pending"
        
        await NotificationService.send_booking_notification(
            booking=Booking(**booking_response),
            recipients=recipients,
            message=notification_message,
            notification_type="info"
        )
        
        if booking_dict.get("urgency") == "critical":
            emergency_message = f"CRITICAL PATIENT: {patient_name} requires immediate air ambulance transport from {booking_dict.get('pickup_location', 'Unknown')}"
            await NotificationService.send_emergency_alert(
                booking=Booking(**booking_response),
                message=emergency_message
            )
        
        # Broadcast via WebSocket
        await manager.broadcast(json.dumps({
            "type": "booking_created",
            "booking_id": booking_id,
            "message": "New booking created",
            "urgency": booking_dict.get("urgency"),
            "patient_name": patient_name
        }))
        
        logger.info(f"✅ Booking created: {booking_id} by user {current_user.email}")
        return Booking(**booking_response)
    
    except Exception as e:
        logger.error(f"❌ Error creating booking: {e}")
        raise HTTPException(status_code=500, detail="Error creating booking")

# READ - Get all bookings
@router.get("/", response_model=List[Booking])
async def get_bookings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    status: Optional[BookingStatus] = None,
    skip: int = 0,
    limit: int = 100
):
    """
    Get all bookings with optional filtering
    """
    try:
        bookings_collection = get_collection("bookings")
        query = {}
        
        # Filter by status if provided
        if status:
            query["status"] = status
        
        # Role-based filtering
        if current_user.role == UserRole.HOSPITAL_STAFF:
            query["created_by"] = str(current_user.id)
        elif current_user.role in [UserRole.DOCTOR, UserRole.PARAMEDIC]:
            # Medical staff can only see critical/urgent bookings
            query["urgency"] = {"$in": ["critical", "urgent"]}
        
        cursor = bookings_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        booking_list = []
        
        for booking in cursor:
            try:
                converted_booking = convert_booking_data(booking)
                booking_list.append(Booking(**converted_booking))
            except Exception as e:
                logger.error(f"❌ Error parsing booking {booking.get('_id')}: {e}")
                continue
        
        logger.info(f"📋 Retrieved {len(booking_list)} bookings for user {current_user.email}")
        return booking_list
    
    except Exception as e:
        logger.error(f"❌ Error retrieving bookings: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving bookings")

# READ - Get single booking by ID
@router.get("/{booking_id}", response_model=BookingWithDetails)
async def get_booking(booking_id: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Get a specific booking by ID with detailed information
    """
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        hospitals_collection = get_collection("hospitals")
        
        if not ObjectId.is_valid(booking_id):
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        booking_data = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Check permissions
        if (current_user.role == UserRole.HOSPITAL_STAFF and 
            booking_data.get("created_by") != str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        
        booking_dict = convert_booking_data(booking_data)
        
        # Add patient details
        if booking_dict.get("patient_id"):
            patient = patients_collection.find_one({"_id": ObjectId(booking_dict["patient_id"])})
            if patient:
                booking_dict["patient_details"] = {
                    "id": str(patient["_id"]),
                    "full_name": patient.get("full_name", "Unknown"),
                    "medical_record_number": patient.get("medical_record_number", ""),
                    "acuity_level": patient.get("acuity_level", "unknown"),
                    "age": patient.get("age"),
                    "condition": patient.get("condition", "")
                }
        
        # Add hospital details
        if booking_dict.get("origin_hospital_id") and booking_dict["origin_hospital_id"] != "unknown":
            origin_hospital = hospitals_collection.find_one({"_id": ObjectId(booking_dict["origin_hospital_id"])})
            if origin_hospital:
                booking_dict["origin_hospital_details"] = {
                    "id": str(origin_hospital["_id"]),
                    "name": origin_hospital.get("name", "Unknown Hospital"),
                    "address": origin_hospital.get("address", ""),
                    "contact_number": origin_hospital.get("contact_number", "")
                }
        
        if booking_dict.get("destination_hospital_id") and booking_dict["destination_hospital_id"] != "unknown":
            dest_hospital = hospitals_collection.find_one({"_id": ObjectId(booking_dict["destination_hospital_id"])})
            if dest_hospital:
                booking_dict["destination_hospital_details"] = {
                    "id": str(dest_hospital["_id"]),
                    "name": dest_hospital.get("name", "Unknown Hospital"),
                    "address": dest_hospital.get("address", ""),
                    "contact_number": dest_hospital.get("contact_number", "")
                }
        
        return BookingWithDetails(**booking_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving booking {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving booking")

# UPDATE - Update booking
@router.put("/{booking_id}", response_model=Booking)
async def update_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Update an existing booking
    """
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        if not ObjectId.is_valid(booking_id):
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        current_booking = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        if not current_booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Get patient name for notifications
        patient_name = "Unknown Patient"
        if current_booking.get("patient_id"):
            patient = patients_collection.find_one({"_id": ObjectId(current_booking["patient_id"])})
            if patient:
                patient_name = patient.get("full_name", "Unknown Patient")
        
        update_data = {k: v for k, v in booking_update.dict(exclude_unset=True).items() if v is not None}
        
        # Track status changes for notifications
        old_status = current_booking.get("status")
        new_status = update_data.get('status')
        status_changed = new_status and new_status != old_status
        
        # Handle completion logic
        if new_status == BookingStatus.COMPLETED:
            if 'flight_duration' not in update_data or update_data['flight_duration'] is None:
                update_data['flight_duration'] = calculate_flight_duration()
            
            if 'actual_cost' not in update_data or update_data['actual_cost'] is None:
                flight_duration = update_data.get('flight_duration', calculate_flight_duration())
                update_data['actual_cost'] = calculate_actual_cost(current_booking, flight_duration)
        
        # Convert date/time fields for database
        if 'preferred_date' in update_data and update_data['preferred_date']:
            update_data['preferred_date'] = datetime.combine(
                update_data['preferred_date'], 
                datetime.min.time()
            )
        
        if 'preferred_time' in update_data and update_data['preferred_time']:
            update_data['preferred_time'] = update_data['preferred_time'].isoformat()
        
        # Normalize equipment data
        if 'required_equipment' in update_data and update_data['required_equipment']:
            update_data['required_equipment'] = [eq.value for eq in normalize_equipment_data(update_data['required_equipment'])]
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Perform update
        result = bookings_collection.update_one(
            {"_id": ObjectId(booking_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found or no changes made")
        
        # Retrieve updated booking
        updated_booking = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        booking_response = convert_booking_data(updated_booking)
        
        # Send notifications for status changes
        if status_changed:
            recipients = await get_notification_recipients(booking_response, current_user, "status_change")
            status_message = f"Booking status changed for patient {patient_name}: {old_status} → {new_status}"
            
            await NotificationService.send_booking_notification(
                booking=Booking(**booking_response),
                recipients=recipients,
                message=status_message,
                notification_type="info" if new_status != "cancelled" else "warning"
            )
            
            if new_status == BookingStatus.COMPLETED:
                completion_message = f"Booking completed for patient {patient_name}. Flight duration: {booking_response.get('flight_duration', 0)} mins. Cost: ${booking_response.get('actual_cost', 0):.2f}"
                await NotificationService.send_booking_notification(
                    booking=Booking(**booking_response),
                    recipients=recipients,
                    message=completion_message,
                    notification_type="success"
                )
        
        # Broadcast update
        await manager.broadcast(json.dumps({
            "type": "booking_updated",
            "booking_id": booking_response["id"],
            "message": f"Booking {booking_response['id']} updated",
            "status": new_status if status_changed else None,
            "patient_name": patient_name
        }))
        
        logger.info(f"✅ Booking updated: {booking_response['id']} by user {current_user.email}")
        return Booking(**booking_response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating booking {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Error updating booking")

# DELETE - Delete booking
@router.delete("/{booking_id}", status_code=status.HTTP_200_OK)
async def delete_booking(
    booking_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Delete a booking
    """
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        if not ObjectId.is_valid(booking_id):
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        booking_data = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Get patient name for notification
        patient_name = "Unknown Patient"
        if booking_data.get("patient_id"):
            patient = patients_collection.find_one({"_id": ObjectId(booking_data["patient_id"])})
            if patient:
                patient_name = patient.get("full_name", "Unknown Patient")
        
        # Delete booking
        result = bookings_collection.delete_one({"_id": ObjectId(booking_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Send notification
        recipients = await get_notification_recipients(booking_data, current_user, "deleted")
        delete_message = f"Booking for patient {patient_name} has been deleted"
        
        await NotificationService.send_booking_notification(
            booking=Booking(**convert_booking_data(booking_data)),
            recipients=recipients,
            message=delete_message,
            notification_type="warning"
        )
        
        # Broadcast deletion
        await manager.broadcast(json.dumps({
            "type": "booking_deleted",
            "booking_id": booking_id,
            "message": "Booking deleted",
            "patient_name": patient_name
        }))
        
        logger.info(f"🗑️ Booking deleted: {booking_id} by user {current_user.email}")
        return {"message": "Booking deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting booking {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting booking")

# Emergency escalation endpoint
@router.put("/{booking_id}/emergency")
async def mark_booking_emergency(
    booking_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Mark a booking as emergency/critical
    """
    allowed_roles = [UserRole.SUPERADMIN, UserRole.DISPATCHER, UserRole.DOCTOR]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        
        if not ObjectId.is_valid(booking_id):
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        booking_data = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        if not booking_data:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        patient_name = "Unknown Patient"
        if booking_data.get("patient_id"):
            patient = patients_collection.find_one({"_id": ObjectId(booking_data["patient_id"])})
            if patient:
                patient_name = patient.get("full_name", "Unknown Patient")
        
        # Update to critical urgency
        result = bookings_collection.update_one(
            {"_id": ObjectId(booking_id)},
            {"$set": {
                "urgency": "critical",
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        updated_booking = bookings_collection.find_one({"_id": ObjectId(booking_id)})
        booking_response = convert_booking_data(updated_booking)
        
        # Send emergency alert
        emergency_message = f"🚨 EMERGENCY ESCALATION: Patient {patient_name} condition critical. Immediate transport required from {booking_data.get('pickup_location', 'Unknown')} to {booking_data.get('destination', 'Unknown')}"
        
        await NotificationService.send_emergency_alert(
            booking=Booking(**booking_response),
            message=emergency_message
        )
        
        # Broadcast emergency
        await manager.broadcast(json.dumps({
            "type": "emergency_alert",
            "booking_id": booking_id,
            "message": "Emergency alert triggered",
            "patient_name": patient_name,
            "urgency": "critical"
        }))
        
        logger.info(f"🚨 Emergency alert triggered for booking {booking_id} by {current_user.email}")
        return {"message": "Emergency alert sent successfully", "booking": Booking(**booking_response)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error triggering emergency alert: {e}")
        raise HTTPException(status_code=500, detail="Error triggering emergency alert")

# Additional endpoints...

@router.get("/pending/count")
async def get_pending_approvals_count(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Get count of pending bookings
    """
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        bookings_collection = get_collection("bookings")
        count = bookings_collection.count_documents({"status": "pending"})
        logger.info(f"📊 Pending approvals count: {count}")
        return {"pending_approvals_count": count}
    
    except Exception as e:
        logger.error(f"❌ Error getting pending count: {e}")
        raise HTTPException(status_code=500, detail="Error getting pending count")

@router.get("/completed/stats")
async def get_completed_bookings_stats(current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Get statistics for completed bookings
    """
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        bookings_collection = get_collection("bookings")
        completed_bookings = bookings_collection.find({"status": "completed"})
        
        total_revenue = 0
        total_flight_time = 0
        booking_count = 0
        
        for booking in completed_bookings:
            total_revenue += booking.get('actual_cost', 0)
            total_flight_time += booking.get('flight_duration', 0)
            booking_count += 1
        
        avg_flight_time = total_flight_time / booking_count if booking_count > 0 else 0
        avg_revenue = total_revenue / booking_count if booking_count > 0 else 0
        
        stats = {
            "total_completed": booking_count,
            "total_revenue": total_revenue,
            "total_flight_time": total_flight_time,
            "average_flight_time": round(avg_flight_time, 2),
            "average_revenue_per_booking": round(avg_revenue, 2)
        }
        
        logger.info(f"📊 Completed bookings stats: {stats}")
        return stats
    
    except Exception as e:
        logger.error(f"❌ Error getting completed stats: {e}")
        raise HTTPException(status_code=500, detail="Error getting completed stats")

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time updates
    """
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": f"Connected as client {client_id}"
        }))
        
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                logger.info(f"📡 WebSocket message from {client_id}: {message_data}")
                
                if message_data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "message": "WebSocket connection active"
                    }))
                    
            except json.JSONDecodeError:
                logger.warning(f"📡 Invalid JSON from WebSocket client {client_id}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"🔌 WebSocket client {client_id} disconnected")
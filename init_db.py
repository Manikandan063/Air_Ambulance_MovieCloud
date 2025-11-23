from database.connection import get_collection
from utils.auth import get_password_hash
from models.user import UserRole
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_existing_users():
    """Fix existing users with invalid roles"""
    users_collection = get_collection("users")
    
    # Update any users with 'clinician' role to 'doctor'
    result = users_collection.update_many(
        {"role": "clinician"},
        {"$set": {"role": UserRole.DOCTOR}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Fixed {result.modified_count} users with 'clinician' role")
    
    # Update any other invalid roles to 'hospital_staff' as default
    valid_roles = [role.value for role in UserRole]
    users_collection.update_many(
        {"role": {"$nin": valid_roles}},
        {"$set": {"role": UserRole.HOSPITAL_STAFF}}
    )

def initialize_settings_collection():
    """Initialize user settings collection with default settings for all users"""
    try:
        settings_collection = get_collection("user_settings")
        users_collection = get_collection("users")
        
        print("🛠️ Initializing user settings...")
        
        # Get all existing users
        all_users = list(users_collection.find({}))
        
        settings_created = 0
        for user in all_users:
            user_id = str(user["_id"])
            
            # Check if settings already exist for this user
            existing_settings = settings_collection.find_one({"user_id": user_id})
            
            if not existing_settings:
                # Create default settings for user
                default_settings = {
                    "user_id": user_id,
                    "theme": "light",
                    "time_format": "12h",
                    "date_format": "MM/DD/YYYY",
                    "timezone": "UTC",
                    "language": "en",
                    "notifications_enabled": True,
                    "email_notifications": True,
                    "sms_notifications": False,
                    "push_notifications": True,
                    "browser_notifications": True,
                    "notify_booking_updates": True,
                    "notify_emergency_alerts": True,
                    "notify_system_maintenance": False,
                    "notify_promotions": False,
                    "email_digest_frequency": "daily",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                settings_collection.insert_one(default_settings)
                settings_created += 1
                print(f"   ✅ Created settings for user: {user['email']}")
        
        # Create index for better performance
        settings_collection.create_index("user_id", unique=True)
        
        print(f"✅ Settings initialization completed: {settings_created} settings created")
        return settings_created
        
    except Exception as e:
        print(f"❌ Error initializing settings collection: {e}")
        return 0

def initialize_sample_patients():
    """Initialize sample patients for testing"""
    try:
        patients_collection = get_collection("patients")
        
        sample_patients = [
            {
                "full_name": "John Smith",
                "date_of_birth": datetime(1985, 5, 15),
                "gender": "male",
                "medical_record_number": "MRN001",
                "acuity_level": "critical",
                "medical_conditions": ["Cardiac Arrest", "Hypertension"],
                "allergies": ["Penicillin"],
                "current_medications": ["Aspirin", "Beta Blocker"],
                "emergency_contact": {
                    "name": "Jane Smith",
                    "relationship": "Spouse",
                    "phone": "+1234567890",
                    "email": "jane.smith@email.com"
                },
                "insurance_information": {
                    "provider": "HealthCare Plus",
                    "policy_number": "HCP123456",
                    "group_number": "GRP789"
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "full_name": "Maria Garcia",
                "date_of_birth": datetime(1978, 8, 22),
                "gender": "female",
                "medical_record_number": "MRN002",
                "acuity_level": "urgent",
                "medical_conditions": ["Pneumonia", "Diabetes"],
                "allergies": ["Sulfa"],
                "current_medications": ["Insulin", "Antibiotics"],
                "emergency_contact": {
                    "name": "Carlos Garcia",
                    "relationship": "Husband",
                    "phone": "+1234567891",
                    "email": "carlos.garcia@email.com"
                },
                "insurance_information": {
                    "provider": "MediCare",
                    "policy_number": "MC654321",
                    "group_number": "GRP456"
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "full_name": "Robert Johnson",
                "date_of_birth": datetime(1992, 12, 3),
                "gender": "male",
                "medical_record_number": "MRN003",
                "acuity_level": "stable",
                "medical_conditions": ["Broken Leg", "Minor Concussion"],
                "allergies": ["None"],
                "current_medications": ["Pain Relievers"],
                "emergency_contact": {
                    "name": "Lisa Johnson",
                    "relationship": "Sister",
                    "phone": "+1234567892",
                    "email": "lisa.johnson@email.com"
                },
                "insurance_information": {
                    "provider": "Blue Cross",
                    "policy_number": "BC987654",
                    "group_number": "GRP123"
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        patients_created = 0
        for patient_data in sample_patients:
            if not patients_collection.find_one({"medical_record_number": patient_data["medical_record_number"]}):
                patients_collection.insert_one(patient_data)
                patients_created += 1
                print(f"✅ Patient created: {patient_data['full_name']}")
        
        print(f"✅ Sample patients initialization completed: {patients_created} patients created")
        return patients_created
        
    except Exception as e:
        print(f"❌ Error initializing sample patients: {e}")
        return 0

def initialize_sample_bookings():
    """Initialize sample bookings for testing"""
    try:
        bookings_collection = get_collection("bookings")
        patients_collection = get_collection("patients")
        users_collection = get_collection("users")
        
        # Get sample patient and user IDs
        sample_patient = patients_collection.find_one({"medical_record_number": "MRN001"})
        hospital_staff = users_collection.find_one({"email": "hospital@medical.com"})
        
        if not sample_patient or not hospital_staff:
            print("❌ Sample patient or hospital staff not found for booking creation")
            return 0
        
        sample_bookings = [
            {
                "patient_id": str(sample_patient["_id"]),
                "pickup_location": "City General Hospital",
                "destination": "Regional Trauma Center",
                "urgency": "critical",
                "required_equipment": ["Ventilator", "ECG Monitor", "Defibrillator"],
                "special_instructions": "Patient requires continuous monitoring and ventilator support during transport",
                "status": "pending",
                "estimated_cost": 7500.00,
                "actual_cost": None,
                "flight_duration": None,
                "assigned_aircraft_id": None,
                "assigned_crew_ids": [],
                "created_by": str(hospital_staff["_id"]),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "patient_id": str(sample_patient["_id"]),
                "pickup_location": "Regional Trauma Center",
                "destination": "City General Hospital",
                "urgency": "urgent",
                "required_equipment": ["ECG Monitor", "Oxygen Supply"],
                "special_instructions": "Stable patient transfer for specialized care",
                "status": "approved",
                "estimated_cost": 4500.00,
                "actual_cost": None,
                "flight_duration": None,
                "assigned_aircraft_id": None,
                "assigned_crew_ids": [],
                "created_by": str(hospital_staff["_id"]),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        bookings_created = 0
        for booking_data in sample_bookings:
            # Check if similar booking already exists
            existing_booking = bookings_collection.find_one({
                "patient_id": booking_data["patient_id"],
                "pickup_location": booking_data["pickup_location"],
                "created_at": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
            })
            
            if not existing_booking:
                bookings_collection.insert_one(booking_data)
                bookings_created += 1
                print(f"✅ Booking created: {booking_data['pickup_location']} → {booking_data['destination']}")
        
        print(f"✅ Sample bookings initialization completed: {bookings_created} bookings created")
        return bookings_created
        
    except Exception as e:
        print(f"❌ Error initializing sample bookings: {e}")
        return 0

def initialize_database():
    print("🚀 Initializing database with default data...")
    
    # First, fix any existing users with invalid roles
    fix_existing_users()
    
    # Create superadmin user if not exists
    users_collection = get_collection("users")
    
    superadmin_email = "superadmin@airambulance.com"
    if not users_collection.find_one({"email": superadmin_email}):
        superadmin_data = {
            "email": superadmin_email,
            "full_name": "Super Administrator",
            "phone": "+1234567890",
            "role": UserRole.SUPERADMIN,
            "is_active": True,
            "hashed_password": get_password_hash("admin123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        users_collection.insert_one(superadmin_data)
        print("✅ Superadmin user created:")
        print(f"   Email: {superadmin_email}")
        print(f"   Password: admin123")
    else:
        print("✅ Superadmin user already exists")
    
    # Create some sample roles for testing
    sample_users = [
        {
            "email": "dispatcher@airambulance.com",
            "full_name": "John Dispatcher",
            "phone": "+1234567891",
            "role": UserRole.DISPATCHER,
            "is_active": True,
            "hashed_password": get_password_hash("dispatcher123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "email": "hospital@medical.com",
            "full_name": "Sarah Hospital Staff",
            "phone": "+1234567892",
            "role": UserRole.HOSPITAL_STAFF,
            "is_active": True,
            "hashed_password": get_password_hash("hospital123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "email": "pilot@airambulance.com",
            "full_name": "Mike Pilot",
            "phone": "+1234567893",
            "role": UserRole.PILOT,
            "is_active": True,
            "hashed_password": get_password_hash("pilot123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "email": "doctor@medical.com",
            "full_name": "Dr. Emily Chen",
            "phone": "+1234567894",
            "role": UserRole.DOCTOR,
            "is_active": True,
            "hashed_password": get_password_hash("doctor123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "email": "paramedic@medical.com",
            "full_name": "Alex Paramedic",
            "phone": "+1234567895",
            "role": UserRole.PARAMEDIC,
            "is_active": True,
            "hashed_password": get_password_hash("paramedic123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "email": "coordinator@airambulance.com",
            "full_name": "Lisa Coordinator",
            "phone": "+1234567896",
            "role": UserRole.AIRLINE_COORDINATOR,
            "is_active": True,
            "hashed_password": get_password_hash("coordinator123"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    for user_data in sample_users:
        if not users_collection.find_one({"email": user_data["email"]}):
            users_collection.insert_one(user_data)
            print(f"✅ {user_data['role']} user created: {user_data['email']}")
        else:
            # Update existing user to ensure correct role
            users_collection.update_one(
                {"email": user_data["email"]},
                {"$set": {"role": user_data["role"]}}
            )
            print(f"✅ {user_data['role']} user updated: {user_data['email']}")
    
    # Create sample hospitals
    hospitals_collection = get_collection("hospitals")
    sample_hospitals = [
        {
            "hospital_name": "City General Hospital",
            "address": "123 Main Street, Cityville",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "level_of_care": "tertiary",
            "icu_capacity": 50,
            "contact_information": {
                "name": "Dr. James Wilson",
                "phone": "+1234567890",
                "email": "james.wilson@citygeneral.com",
                "position": "Medical Director"
            },
            "preferred_pickup_location": "Main Helipad - Roof Top",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "hospital_name": "Regional Trauma Center",
            "address": "456 Oak Avenue, Townsville",
            "latitude": 34.0522,
            "longitude": -118.2437,
            "level_of_care": "trauma_center",
            "icu_capacity": 30,
            "contact_information": {
                "name": "Dr. Sarah Johnson",
                "phone": "+1234567891",
                "email": "sarah.johnson@traumacenter.com",
                "position": "Emergency Department Head"
            },
            "preferred_pickup_location": "Emergency Department Helipad",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    for hospital_data in sample_hospitals:
        if not hospitals_collection.find_one({"hospital_name": hospital_data["hospital_name"]}):
            hospitals_collection.insert_one(hospital_data)
            print(f"✅ Hospital created: {hospital_data['hospital_name']}")
    
    # Create sample aircraft
    aircraft_collection = get_collection("aircraft")
    sample_aircraft = [
        {
            "aircraft_type": "helicopter",
            "registration": "N123AB",
            "airline_operator": "Air Ambulance Services",
            "range_km": 600,
            "speed_kmh": 250,
            "max_payload_kg": 1200,
            "cabin_configuration": "Medical - 1 patient, 2 medical staff",
            "base_location": "City General Hospital",
            "medical_equipment": [
                {"name": "Ventilator", "quantity": 1, "operational": True},
                {"name": "ECG Monitor", "quantity": 1, "operational": True},
                {"name": "Defibrillator", "quantity": 1, "operational": True},
                {"name": "Oxygen Supply", "quantity": 2, "operational": True}
            ],
            "status": "available",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "maintenance_records": []
        },
        {
            "aircraft_type": "fixed_wing",
            "registration": "N456CD",
            "airline_operator": "Air Ambulance Services",
            "range_km": 1500,
            "speed_kmh": 500,
            "max_payload_kg": 2000,
            "cabin_configuration": "Medical - 2 patients, 3 medical staff",
            "base_location": "Regional Airport",
            "medical_equipment": [
                {"name": "Ventilator", "quantity": 2, "operational": True},
                {"name": "ECG Monitor", "quantity": 2, "operational": True},
                {"name": "Defibrillator", "quantity": 1, "operational": True},
                {"name": "Oxygen Supply", "quantity": 4, "operational": True},
                {"name": "Infusion Pump", "quantity": 2, "operational": True}
            ],
            "status": "available",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "maintenance_records": []
        }
    ]
    
    for aircraft_data in sample_aircraft:
        if not aircraft_collection.find_one({"registration": aircraft_data["registration"]}):
            aircraft_collection.insert_one(aircraft_data)
            print(f"✅ Aircraft created: {aircraft_data['registration']}")
    
    # Initialize sample patients
    initialize_sample_patients()
    
    # Initialize sample bookings
    initialize_sample_bookings()
    
    # Initialize user settings for all users
    initialize_settings_collection()
    
    print("🎉 Database initialization completed!")

def reset_user_settings(user_email: str = None):
    """Reset settings for a specific user or all users"""
    settings_collection = get_collection("user_settings")
    users_collection = get_collection("users")
    
    if user_email:
        # Reset settings for specific user
        user = users_collection.find_one({"email": user_email})
        if user:
            user_id = str(user["_id"])
            settings_collection.delete_one({"user_id": user_id})
            print(f"✅ Settings reset for user: {user_email}")
        else:
            print(f"❌ User not found: {user_email}")
    else:
        # Reset all settings
        result = settings_collection.delete_many({})
        print(f"✅ Reset all user settings: {result.deleted_count} settings deleted")
        
        # Reinitialize settings
        initialize_settings_collection()

if __name__ == "__main__":
    from database.connection import connect_to_mongo
    if connect_to_mongo():
        initialize_database()
    else:
        print("❌ Failed to connect to database")
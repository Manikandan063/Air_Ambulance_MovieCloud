from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import connect_to_mongo, close_mongo_connection
from routes import (
    auth, users, patients, hospitals, aircraft, 
    bookings, reports, dashboard, settings, notifications  # Add settings and notifications here
)
import uvicorn
from init_db import initialize_database
from datetime import datetime
from routes import hospital_staff


app = FastAPI(
    title="Air Ambulance Management System",
    description="Comprehensive backend for air ambulance operations management",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
def startup_event():
    print("🚀 Starting Air Ambulance Management System...")
    if connect_to_mongo():
        initialize_database()
        print_routes()  # Print all registered routes
    else:
        print("❌ Failed to initialize database connection")

# Shutdown event
@app.on_event("shutdown")
def shutdown_event():
    close_mongo_connection()
    print("👋 Shutting down Air Ambulance Management System...")

# Include routers - use consistent import style
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(patients.router)
app.include_router(hospitals.router)
app.include_router(aircraft.router)
app.include_router(bookings.router)
app.include_router(reports.router)
app.include_router(hospital_staff.router)
app.include_router(dashboard.router)
app.include_router(settings.router)  # Now using the same import style
app.include_router(notifications.router)  # Now using the same import style

def print_routes():
    """Print all registered routes for debugging"""
    print("\n📋 REGISTERED ROUTES:")
    print("=" * 50)
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            methods = ', '.join(route.methods)
            print(f"{methods:15} {route.path}")
    print("=" * 50)
    print("✅ All routes registered successfully!\n")

@app.get("/")
async def root():
    return {
        "message": "Air Ambulance Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
        "endpoints": {
            "authentication": "/api/auth",
            "users": "/api/users",
            "patients": "/api/patients", 
            "hospitals": "/api/hospitals",
            "aircraft": "/api/aircraft",
            "bookings": "/api/bookings",
            "reports": "/api/reports",
            "settings": "/api/settings",
            "notifications": "/api/notifications",
            "hospital_staff": "/api/hospital-staff",
            "dashboard": "/api/dashboard"
        }
    }

@app.get("/health")
async def health_check():
    from database.connection import db
    try:
        if db.client:
            db.client.admin.command('ping')
            db_status = "connected"
        else:
            db_status = "disconnected"
    except:
        db_status = "error"
    
    return {
        "status": "healthy", 
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints_available": True
    }

# Debug endpoint to check all routes
@app.get("/debug/routes")
async def debug_routes():
    routes_info = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            route_info = {
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, "name", "Unknown")
            }
            routes_info.append(route_info)
    
    return {
        "total_routes": len(routes_info),
        "routes": routes_info
    }

if __name__ == "__main__":
    print("🔄 Starting Air Ambulance Management System...")
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
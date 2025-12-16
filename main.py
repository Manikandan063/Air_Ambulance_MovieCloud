from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import connect_to_mongo, close_mongo_connection
from routes import (
    auth,
    users,
    patients,
    hospitals,
    aircraft,
    bookings,
    reports,
    dashboard,
    settings,
    notifications,
    hospital_staff,
)
import uvicorn
from init_db import initialize_database
from datetime import datetime


# ---------------------------------------------------
# App Initialization
# ---------------------------------------------------
app = FastAPI(
    title="Air Ambulance Management System",
    description="Comprehensive backend for air ambulance operations management",
    version="1.0.0",
)

# ---------------------------------------------------
# ✅ CORS Middleware (CORRECT)
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://10.214.79.226:8080",
        "https://moviecloud-airambulanc.onrender.com",  # ✅ FRONTEND URL
    ],
    allow_credentials=True,
    allow_methods=["*"],   # allows GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],   # allows Authorization, Content-Type
)

# ---------------------------------------------------
# Startup Event
# ---------------------------------------------------
@app.on_event("startup")
def startup_event():
    print("🚀 Starting Air Ambulance Management System...")
    if connect_to_mongo():
        initialize_database()
        print_routes()
    else:
        print("❌ Failed to connect to MongoDB")

# ---------------------------------------------------
# Shutdown Event
# ---------------------------------------------------
@app.on_event("shutdown")
def shutdown_event():
    close_mongo_connection()
    print("👋 Shutting down Air Ambulance Management System...")

# ---------------------------------------------------
# Routers
# ---------------------------------------------------
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(patients.router)
app.include_router(hospitals.router)
app.include_router(aircraft.router)
app.include_router(bookings.router)
app.include_router(reports.router)
app.include_router(hospital_staff.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(notifications.router)

# ---------------------------------------------------
# Utility: Print Routes
# ---------------------------------------------------
def print_routes():
    print("\n📋 REGISTERED ROUTES")
    print("=" * 50)
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            print(f"{', '.join(route.methods):15} {route.path}")
    print("=" * 50)
    print("✅ All routes registered successfully\n")

# ---------------------------------------------------
# Root Endpoint
# ---------------------------------------------------
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
            "dashboard": "/api/dashboard",
        },
    }

# ---------------------------------------------------
# Health Check
# ---------------------------------------------------
@app.get("/health")
async def health_check():
    from database.connection import db

    try:
        if db.client:
            db.client.admin.command("ping")
            db_status = "connected"
        else:
            db_status = "disconnected"
    except Exception:
        db_status = "error"

    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
    }

# ---------------------------------------------------
# Debug Routes
# ---------------------------------------------------
@app.get("/debug/routes")
async def debug_routes():
    routes_info = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes_info.append(
                {
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, "name", "Unknown"),
                }
            )

    return {
        "total_routes": len(routes_info),
        "routes": routes_info,
    }

# ---------------------------------------------------
# Run Server
# ---------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

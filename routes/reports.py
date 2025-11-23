# routes/reports.py
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timedelta, date
import logging
import io

from database.connection import get_collection
from models.user import User, UserRole
from models.report import (
    BookingReport,
    BookingReportRequest,
    BookingReportItem,
    DashboardStats,
    AircraftUtilizationReport,
    BillingReport
)
from routes.auth import get_current_active_user, get_current_user
from utils.report_generator import ReportGenerator

router = APIRouter(prefix="/api/reports", tags=["Reports"])
logger = logging.getLogger(__name__)


# ----------------- PERMISSION CHECK -----------------
def has_report_permission(user: User):
    return user.role in [
        UserRole.SUPERADMIN,
        UserRole.DISPATCHER,
        UserRole.AIRLINE_COORDINATOR
    ]


# ----------------- OPTIONAL USER -----------------
async def get_current_user_optional(authorization: Optional[str] = Header(None)):
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    try:
        return await get_current_user(token)
    except Exception:
        return None


# ----------------- DATE RANGE UTILITY -----------------
def build_date_query(start, end):
    """
    Accepts date or string and returns created_at query between start_dt and end_dt.
    """
    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start).date()
        if isinstance(end, str):
            end = datetime.fromisoformat(end).date()
    except Exception as e:
        logger.error("Invalid date format in build_date_query: %s", e)
        raise HTTPException(status_code=400, detail="Invalid start_date or end_date format")

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    return {
        "created_at": {
            "$gte": start_dt,
            "$lte": end_dt
        }
    }


# ----------------- DASHBOARD REPORT -----------------
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: User = Depends(get_current_active_user)):
    if not has_report_permission(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    bookings = get_collection("bookings")
    patients = get_collection("patients")
    aircraft = get_collection("aircraft")

    total_bookings = bookings.count_documents({})
    pending = bookings.count_documents({"status": "pending"})
    available_aircraft = aircraft.count_documents({"status": "available"})
    critical_patients = patients.count_documents({"acuity_level": "critical"})

    agg = list(bookings.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "revenue": {"$sum": {"$ifNull": ["$actual_cost", 0]}}
        }}
    ]))

    completed = agg[0]["count"] if agg else 0
    revenue = agg[0]["revenue"] if agg else 0

    return DashboardStats(
        total_bookings=total_bookings,
        pending_approvals=pending,
        available_aircraft=available_aircraft,
        critical_patients=critical_patients,
        total_revenue=revenue,
        completed_bookings=completed
    )


# ----------------- BOOKING REPORT -----------------
@router.post("/bookings", response_model=BookingReport)
async def get_booking_report(
    request: BookingReportRequest,
    current_user: User = Depends(get_current_active_user)
):
    if not has_report_permission(current_user):
        raise HTTPException(403, "Not enough permissions")

    collection = get_collection("bookings")
    patients = get_collection("patients")

    # build date query and combine with optional filters
    query = build_date_query(request.start_date, request.end_date)
    if request.status:
        query["status"] = request.status
    if request.urgency:
        query["urgency"] = request.urgency

    # If patient_id is stored as string in bookings, convert it safely before lookup.
    # $addFields creates a patient_obj_id that is ObjectId if patient_id was string.
    pipeline = [
        {"$match": query},
        {"$addFields": {
            "patient_obj_id": {
                "$cond": [
                    {"$and": [{"$ne": ["$patient_id", None]}, {"$eq": [{"$type": "$patient_id"}, "string"]}]},
                    {"$convert": {"input": "$patient_id", "to": "objectId", "onError": None, "onNull": None}},
                    "$patient_id"
                ]
            }
        }},
        {"$lookup": {
            "from": "patients",
            "localField": "patient_obj_id",
            "foreignField": "_id",
            "as": "patient"
        }},
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}}
    ]

    cursor = list(collection.aggregate(pipeline))
    items = []

    total_revenue_completed = 0.0
    total_estimated_pending = 0.0
    completed_count = 0
    total_flight_time = 0

    for b in cursor:
        # created_at fallback
        created_at = b.get("created_at") or b.get("createdAt") or datetime.utcnow()
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = datetime.utcnow()

        patient_doc = b.get("patient") or {}
        patient_name = patient_doc.get("full_name") or patient_doc.get("fullName") or "Unknown"

        # cost: completed => actual_cost, else estimated_cost
        actual_cost = b.get("actual_cost")
        estimated_cost = b.get("estimated_cost") or 0.0

        if b.get("status") == "completed":
            cost = float(actual_cost or 0.0)
            total_revenue_completed += cost
            completed_count += 1
            total_flight_time += b.get("flight_duration", 0) or 0
        else:
            cost = float(estimated_cost or 0.0)
            total_estimated_pending += cost

        items.append(
            BookingReportItem(
                booking_id=str(b["_id"]),
                date=(created_at.date() if isinstance(created_at, datetime) else datetime.utcnow().date()),
                status=b.get("status", "unknown"),
                urgency=b.get("urgency", "unknown"),
                patient_name=patient_name,
                cost=cost
            )
        )

    avg_flight_time = (total_flight_time / completed_count) if completed_count else 0.0
    total_bookings = len(items)
    total_revenue = total_revenue_completed  # revenue for completed bookings
    total_estimated = total_estimated_pending

    logger.info("Booking Report generated: total=%s completed=%s revenue=%.2f estimated_pending=%.2f",
                total_bookings, completed_count, total_revenue, total_estimated)

    # Return both totals in BookingReport model (total_revenue remains completed revenue as before)
    return BookingReport(
        total_bookings=total_bookings,
        completed_bookings=completed_count,
        total_revenue=total_revenue,
        average_flight_time=avg_flight_time,
        bookings=items,
    )


# ----------------- EXPORT HELPERS -----------------
async def export_booking_data(request: BookingReportRequest, user: User):
    if not has_report_permission(user):
        raise HTTPException(403, "Not enough permissions")

    collection = get_collection("bookings")

    query = build_date_query(request.start_date, request.end_date)
    if request.status:
        query["status"] = request.status
    if request.urgency:
        query["urgency"] = request.urgency

    pipeline = [
        {"$match": query},
        {"$addFields": {
            "patient_obj_id": {
                "$cond": [
                    {"$and": [{"$ne": ["$patient_id", None]}, {"$eq": [{"$type": "$patient_id"}, "string"]}]},
                    {"$convert": {"input": "$patient_id", "to": "objectId", "onError": None, "onNull": None}},
                    "$patient_id"
                ]
            }
        }},
        {"$lookup": {
            "from": "patients",
            "localField": "patient_obj_id",
            "foreignField": "_id",
            "as": "patient"
        }},
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}}
    ]

    data = []
    for b in collection.aggregate(pipeline):
        created_at = b.get("created_at") or datetime.utcnow()
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = datetime.utcnow()

        patient_name = (b.get("patient") or {}).get("full_name") or "Unknown"

        cost = (b.get("actual_cost") if b.get("status") == "completed" else b.get("estimated_cost")) or 0.0

        data.append({
            "booking_id": str(b["_id"]),
            "patient_name": patient_name,
            "date": (created_at.date().isoformat() if isinstance(created_at, datetime) else datetime.utcnow().date().isoformat()),
            "status": b.get("status"),
            "urgency": b.get("urgency"),
            "cost": float(cost),
            "equipment": b.get("required_equipment", []),
            "instructions": b.get("special_instructions", ""),
            "flight_duration": b.get("flight_duration", 0) or 0,
            "pickup_location": b.get("pickup_location", ""),
            "destination": b.get("destination", "")
        })

    return data


# ----------------- DOWNLOAD PDF -----------------
@router.post("/bookings/download/pdf")
async def download_pdf(
    request: BookingReportRequest,
    current_user: User = Depends(get_current_active_user)
):
    if not has_report_permission(current_user):
        raise HTTPException(403, "Not enough permissions")

    data = await export_booking_data(request, current_user)
    date_range = f"{request.start_date} to {request.end_date}"

    pdf_bytes = ReportGenerator.generate_booking_pdf(data, "Booking Report", date_range)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=booking_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )


# ----------------- DOWNLOAD EXCEL -----------------
@router.post("/bookings/download/excel")
async def download_excel(
    request: BookingReportRequest,
    current_user: User = Depends(get_current_active_user)
):
    if not has_report_permission(current_user):
        raise HTTPException(403, "Not enough permissions")

    data = await export_booking_data(request, current_user)
    date_range = f"{request.start_date} to {request.end_date}"

    excel_bytes = ReportGenerator.generate_booking_excel(data, "Booking Report", date_range)

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=booking_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        }
    )


# ----------------- AIRCRAFT UTILIZATION -----------------
@router.get("/aircraft-utilization", response_model=List[AircraftUtilizationReport])
async def aircraft_utilization(
    current_user: User = Depends(get_current_active_user),
    days: int = 30
):
    if not has_report_permission(current_user):
        raise HTTPException(403, "Not enough permissions")

    aircraft_col = get_collection("aircraft")
    bookings = get_collection("bookings")

    threshold = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$lookup": {
            "from": "bookings",
            "let": {"ac_id": {"$toString": "$_id"}},
            "pipeline": [
                {"$match": {
                    "$expr": {"$and": [
                        {"$eq": ["$assigned_aircraft_id", "$$ac_id"]},
                        {"$eq": ["$status", "completed"]},
                        {"$gte": ["$created_at", threshold]}
                    ]}
                }},
                {"$group": {
                    "_id": None,
                    "flights": {"$sum": 1},
                    "hours": {"$sum": {"$ifNull": ["$flight_duration", 0]}}
                }}
            ],
            "as": "utilization"
        }},
        {"$unwind": {"path": "$utilization", "preserveNullAndEmptyArrays": True}}
    ]

    results = []
    for a in aircraft_col.aggregate(pipeline):
        flights = a.get("utilization", {}).get("flights", 0)
        hours = a.get("utilization", {}).get("hours", 0)

        max_hours = days * 8
        util_rate = (hours / max_hours) * 100 if max_hours else 0

        results.append(
            AircraftUtilizationReport(
                aircraft_id=str(a["_id"]),
                registration=a.get("registration", ""),
                model=a.get("model", "Unknown"),
                total_flights=flights,
                total_hours=hours,
                utilization_rate=round(util_rate, 2),
                maintenance_downtime=a.get("maintenance_downtime", 0)
            )
        )

    return results


# ----------------- BILLING REPORT -----------------
@router.get("/billing", response_model=BillingReport)
async def billing_report(
    current_user: User = Depends(get_current_active_user),
    days: int = 30
):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.DISPATCHER]:
        raise HTTPException(403, "Not enough permissions")

    bookings = get_collection("bookings")
    threshold = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": threshold}}},
        {"$facet": {
            "all": [
                {"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "pending_estimated": {"$sum": {"$ifNull": ["$estimated_cost", 0]}}
                }}
            ],
            "completed": [
                {"$match": {"status": "completed"}},
                {"$group": {
                    "_id": None,
                    "count": {"$sum": 1},
                    "revenue": {"$sum": {"$ifNull": ["$actual_cost", 0]}}
                }}
            ]
        }}
    ]

    result_list = list(bookings.aggregate(pipeline))
    result = result_list[0] if result_list else {"all": [], "completed": []}

    all_data = result.get("all", [{}])[0] if result.get("all") else {}
    comp = result.get("completed", [{}])[0] if result.get("completed") else {}

    total = all_data.get("total", 0)
    pending = all_data.get("pending_estimated", 0)
    revenue = comp.get("revenue", 0)
    completed = comp.get("count", 0)
    avg_cost = revenue / completed if completed else 0

    return BillingReport(
        total_bookings=total,
        pending_payments=pending,
        completed_payments=revenue,
        total_revenue=revenue,
        average_cost_per_booking=avg_cost
    )

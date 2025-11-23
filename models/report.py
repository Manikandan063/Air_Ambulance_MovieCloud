from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, date
from enum import Enum

class ReportType(str, Enum):
    BOOKING = "booking"
    AIRCRAFT_UTILIZATION = "aircraft_utilization"
    BILLING = "billing"
    CREW_PERFORMANCE = "crew_performance"

class DateRange(BaseModel):
    start_date: date
    end_date: date

class BookingReportRequest(DateRange):
    status: Optional[str] = None
    urgency: Optional[str] = None

class BookingReportItem(BaseModel):
    booking_id: str
    date: date
    status: str
    urgency: str
    patient_name: str
    cost: float

class BookingReport(BaseModel):
    total_bookings: int
    completed_bookings: int
    total_revenue: float
    average_flight_time: float
    bookings: List[BookingReportItem]

class AircraftUtilizationReport(BaseModel):
    aircraft_id: str
    registration: str
    total_flights: int
    total_hours: float
    utilization_rate: float
    maintenance_downtime: float

class BillingReport(BaseModel):
    total_revenue: float
    pending_payments: float
    completed_payments: float
    average_cost_per_booking: float
    total_bookings: Optional[int] = 0  # Add this field
    bookings: Optional[List[BookingReportItem]] = []  # Add this field

class DashboardStats(BaseModel):
    total_bookings: int
    pending_approvals: int
    available_aircraft: int
    critical_patients: int
    total_revenue: float
    completed_bookings: int
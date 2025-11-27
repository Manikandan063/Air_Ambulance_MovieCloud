from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

import os
from datetime import datetime

# -------------------------------------------
# REGISTER FONT THAT SUPPORTS INDIAN RUPEE ₹
# -------------------------------------------
FONT_PATH = "assets/fonts/DejaVuSans.ttf"

if not os.path.exists(FONT_PATH):
    raise Exception(
        "⚠️ Font DejaVuSans.ttf is missing! "
        "Place it in the project root folder to enable ₹ symbol."
    )

pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))


class ReportGenerator:

    @staticmethod
    def generate_booking_pdf(bookings_data, title, date_range):

        buffer = SimpleDocTemplate(
            "booking_report.pdf",
            pagesize=A4,
            leftMargin=15,
            rightMargin=15,
            topMargin=20,
            bottomMargin=20
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="HeadingCenter",
            parent=styles["Heading1"],
            alignment=1,
            fontName="DejaVu"
        ))

        styles.add(ParagraphStyle(
            name="NormalRupee",
            parent=styles["Normal"],
            fontName="DejaVu"
        ))

        story = []

        # ---------------- TITLE ----------------
        story.append(Paragraph(f"<b>{title}</b>", styles["HeadingCenter"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Date Range: {date_range}", styles["NormalRupee"]))
        story.append(Spacer(1, 12))

        # ---------------- TABLE HEADER ----------------
        table_header = [
            "S.No", "Booking ID", "Patient", "Date",
            "Status", "Urgency", "Cost (₹)", "Pickup", "Destination"
        ]

        table_data = [table_header]

        # ---------------- BUILD ROWS ----------------
        for idx, r in enumerate(bookings_data, start=1):
            table_data.append([
                idx,
                r.get("booking_id", ""),
                r.get("patient_name", "Unknown"),
                r.get("date", ""),
                r.get("status", ""),
                r.get("urgency", ""),
                f"₹{r.get('cost', 0):.2f}",
                r.get("pickup_location", ""),
                r.get("destination", "")
            ])

        # ---------------- SMALL/MEDIUM COLUMN WIDTHS ----------------
        col_widths = [
            10 * mm,   # S.No
            28 * mm,   # Booking ID
            28 * mm,   # Patient
            18 * mm,   # Date
            20 * mm,   # Status
            18 * mm,   # Urgency
            18 * mm,   # Cost
            30 * mm,   # Pickup
            30 * mm    # Destination
        ]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),  # S.No alignment
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ]))

        story.append(table)
        story.append(Spacer(1, 18))

        # ---------------- SUMMARY SECTION ----------------
        completed = [r for r in bookings_data if r.get("status") == "completed"]
        non_completed = [r for r in bookings_data if r.get("status") != "completed"]

        total_bookings = len(bookings_data)
        completed_count = len(completed)

        # Only completed revenue
        total_revenue_completed = sum(r.get("cost", 0) for r in completed)
        total_estimated_pending = sum(r.get("cost", 0) for r in non_completed)
        grand_total = total_revenue_completed + total_estimated_pending

        summary_header = ["Summary Item", "Amount"]

        summary_data = [
            summary_header,
            ["Total Bookings", str(total_bookings)],
            ["Completed Bookings", str(completed_count)],
            ["Revenue (Completed Only)", f"₹{total_revenue_completed:.2f}"],
            ["Estimated (Pending/Other)", f"₹{total_estimated_pending:.2f}"],
            ["Grand Total", f"₹{grand_total:.2f}"]
        ]

        summary_table = Table(
            summary_data,
            colWidths=[60 * mm, 50 * mm]
        )

        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        story.append(Paragraph("<b>SUMMARY</b>", styles["NormalRupee"]))
        story.append(Spacer(1, 6))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # FOOTER
        story.append(Paragraph(
            "Air Ambulance Management System - Confidential Report",
            styles["NormalRupee"]
        ))

        buffer.build(story)

        with open("booking_report.pdf", "rb") as f:
            return f.read()

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from wxbench.trip_brief.render import BriefRow, fmt


def render_pdf(path: str, *, title: str, subtitle: str, rows: list[BriefRow], summary: str) -> None:
    styles = getSampleStyleSheet()
    page_size = landscape(letter)
    doc = SimpleDocTemplate(path, pagesize=page_size, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = [
        Paragraph(title, styles["Title"]),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 12),
    ]

    table_data = [
        [
            "time_local",
            "distance_km",
            "precip_type",
            "precip_probability",
            "precip_amount_mm",
            "snow_rate_mm_hr",
            "temp_c",
            "wind_kph",
            "gust_kph",
            "visibility_km",
        ]
    ]

    for row in rows:
        table_data.append(
            [
                row.time_local,
                f"{row.distance_km:.1f}",
                row.precip_type,
                fmt(row.precip_probability, 0),
                fmt(row.precip_amount),
                fmt(row.snow_rate),
                fmt(row.temperature_c),
                fmt(row.wind_kph),
                fmt(row.gust_kph),
                fmt(row.visibility_km),
            ]
        )

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Summary", styles["Heading2"]))
    for line in summary.splitlines():
        elements.append(Paragraph(line, styles["Normal"]))

    doc.build(elements)

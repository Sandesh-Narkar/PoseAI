"""Report generation for PoseAI workout analysis (PDF + CSV).

Builders are pure functions that render already-aggregated, real stored
data supplied by the Flask layer (see GET /api/report in app.py). No
values are computed or invented here.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1e3a5f")
GREEN = colors.HexColor("#82de9e")
CYAN = colors.HexColor("#06b6d4")
SLATE = colors.HexColor("#64748b")
BORDER = colors.HexColor("#e2e8f0")
BG_LIGHT = colors.HexColor("#f8fafc")

RANGE_LABELS: dict[str, str] = {
    "today": "Current Workout (Today)",
    "7d": "Last 7 Days",
    "30d": "Last 30 Days",
    "all": "All Time",
}


def _duration_label(seconds: Any) -> str:
    seconds = int(seconds or 0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _mv(value: Any, suffix: str = "") -> str:
    if value is None:
        return "--"
    return f"{value}{suffix}"


# ==============================================================================
# CSV
# ==============================================================================

CSV_HEADERS = [
    "Date",
    "Exercise",
    "Reps",
    "Sets",
    "Calories",
    "Duration (seconds)",
    "Duration",
    "Form Score",
    "Feedback",
]


def build_csv_payload(data: dict[str, Any]) -> bytes:
    """Return a UTF-8 CSV byte payload of the workout history rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for s in data.get("recent_sessions", []):
        writer.writerow([
            s.get("date") or "",
            s.get("exercise") or "",
            s.get("reps") or 0,
            s.get("sets") or 0,
            round(float(s.get("calories") or 0.0), 1),
            int(s.get("duration") or 0),
            _duration_label(s.get("duration") or 0),
            round(float(s.get("accuracy") or 0.0), 1),
            s.get("feedback") or "",
        ])
    return buffer.getvalue().encode("utf-8")


# ==============================================================================
# PDF
# ==============================================================================


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "bmv.title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "bmv.subtitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=GREEN,
            textTransform="uppercase",
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "bmv.h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "bmv.meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=SLATE,
        ),
    }


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table([[Paragraph(k, _styles()["meta"]), Paragraph(v, _styles()["meta"])] for k, v in rows],
                  colWidths=[60 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BG_LIGHT]),
    ]))
    return table


def _data_table(headers: list[str], rows: list[list[str]], small: bool = False) -> Table:
    body = [headers] + rows
    fs = 7 if small else 8
    table = Table(body, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), fs),
        ("FONTSIZE", (0, 1), (-1, -1), fs),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_pdf_payload(data: dict[str, Any]) -> bytes:
    """Render a professional PoseAI report PDF from real stored data."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="PoseAI Workout Analysis Report",
        author="PoseAI",
    )
    st = _styles()

    story: list[Any] = [
        Paragraph("POSEAI", st["title"]),
        Paragraph("WORKOUT ANALYSIS REPORT", st["subtitle"]),
    ]

    totals = data.get("totals", {})
    ctx = data.get("streak", {})
    best = data.get("personal_bests", {})
    range_param = data.get("range", "all")

    story.append(Paragraph("SUMMARY", st["h2"]))
    story.append(_kv_table([
        ("User", data.get("user_name") or "PoseAI User"),
        ("Report range", RANGE_LABELS.get(range_param, range_param)),
        ("Generated on", data.get("generated_on") or ""),
        ("Total workouts", str(totals.get("total_workouts", 0))),
        ("Total reps", str(totals.get("total_reps", 0))),
        ("Total sets", str(totals.get("total_sets", 0))),
        ("Total calories", _mv(round(float(totals.get("total_calories") or 0.0), 1), " kcal")),
        ("Total training time", _duration_label(totals.get("total_duration") or 0)),
        ("Average form score", _mv(round(float(totals.get("average_form_score") or 0.0), 1), " / 100")),
        ("Current streak", f"{ctx.get('currentStreak', 0)} day(s)"),
        ("Longest streak", f"{ctx.get('longestStreak', 0)} day(s)"),
        ("Completed today", "Yes" if ctx.get("todayCompleted") else "No"),
    ]))

    story.append(Paragraph("PERSONAL BESTS", st["h2"]))
    story.append(_kv_table([
        ("Highest rep count", str(best.get("best_reps", 0))),
        ("Best form score", _mv(round(float(best.get("best_form_score") or 0.0), 1), " / 100")),
        ("Longest workout", _duration_label(best.get("best_duration") or 0)),
        ("Most calories burned", _mv(round(float(best.get("best_calories") or 0.0), 1), " kcal")),
    ]))

    breakdown = data.get("exercise_breakdown", [])
    if breakdown:
        story.append(Paragraph("EXERCISE PERFORMANCE", st["h2"]))
        story.append(_data_table(
            ["Exercise", "Workouts", "Total Reps", "Best Reps", "Avg Form", "Calories"],
            [
                [
                    str(entry.get("exercise", "")),
                    str(entry.get("total_workouts", 0)),
                    str(entry.get("total_reps", 0)),
                    str(entry.get("best_reps", 0)),
                    _mv(entry.get("average_form_score", 0.0), " / 100"),
                    _mv(entry.get("total_calories", 0.0), ""),
                ]
                for entry in breakdown
            ],
        ))

    days = data.get("daily_activity", [])
    if days:
        story.append(Paragraph("DAILY ACTIVITY", st["h2"]))
        story.append(_data_table(
            ["Date", "Workouts", "Reps", "Calories", "Duration", "Avg Form"],
            [
                [
                    str(day.get("date", "")),
                    str(day.get("workouts", 0)),
                    str(day.get("reps", 0)),
                    _mv(round(float(day.get("calories") or 0.0), 1), ""),
                    _duration_label(day.get("duration") or 0),
                    _mv(day.get("form_score", 0.0), " / 100"),
                ]
                for day in days
            ],
        ))

    sessions = data.get("recent_sessions", [])
    if sessions:
        story.append(Paragraph("WORKOUT HISTORY", st["h2"]))
        story.append(_data_table(
            ["Date", "Exercise", "Reps", "Sets", "Duration", "Calories", "Form", "Feedback"],
            [
                [
                    str(s.get("date", "")),
                    str(s.get("exercise", "")),
                    str(s.get("reps", 0)),
                    str(s.get("sets", 0)),
                    _duration_label(s.get("duration") or 0),
                    _mv(round(float(s.get("calories") or 0.0), 1), ""),
                    _mv(round(float(s.get("accuracy") or 0.0), 1), " / 100"),
                    str((s.get("feedback") or "")[:40]),
                ]
                for s in sessions
            ],
            small=True,
        ))
    else:
        story.append(Spacer(1, 4))
        story.append(Paragraph("No completed workouts in this range yet.", st["meta"]))

    doc.build(story)
    return buffer.getvalue()
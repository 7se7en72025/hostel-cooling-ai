"""Build the plain-language overview from the submitted study results."""

import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "hostel_cooling" / "resources" / "Hostel_Cooling_Overview.pdf"
INK = colors.HexColor("#203C31")
MUTED = colors.HexColor("#4F635A")
GREEN = colors.HexColor("#2A694E")
LIGHT = colors.HexColor("#E7F0E4")
LINE = colors.HexColor("#DAE4DB")
MARGIN = 54
WIDTH = A4[0] - 2 * MARGIN - 12


STYLES = {
    "title": ParagraphStyle(
        "title",
        fontName="Times-Roman",
        fontSize=39,
        leading=43,
        textColor=INK,
        spaceAfter=14,
    ),
    "lead": ParagraphStyle(
        "lead", fontSize=13, leading=19, textColor=MUTED, spaceAfter=21
    ),
    "heading": ParagraphStyle(
        "heading",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=7,
    ),
    "body": ParagraphStyle(
        "body", fontSize=11, leading=17, textColor=INK, spaceAfter=10
    ),
    "example": ParagraphStyle(
        "example",
        fontSize=11,
        leading=17,
        textColor=INK,
        backColor=LIGHT,
        borderPadding=12,
        leftIndent=12,
        rightIndent=12,
        spaceBefore=13,
        spaceAfter=24,
    ),
    "source": ParagraphStyle(
        "source", fontSize=9, leading=13, textColor=MUTED, spaceBefore=7
    ),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def measure(label, fixed, project, maximum, suffix):
    chart = Drawing(WIDTH, 76)
    chart.add(
        String(0, 60, label, fontName="Helvetica-Bold", fontSize=11, fillColor=INK)
    )
    for name, value, color, y in (
        ("Fixed schedule", fixed, colors.HexColor("#77857E"), 32),
        ("Project method", project, GREEN, 8),
    ):
        chart.add(String(0, y + 3, name, fontSize=9.5, fillColor=MUTED))
        chart.add(Rect(91, y, 298, 12, rx=3, ry=3, strokeColor=None, fillColor=LIGHT))
        chart.add(
            Rect(
                91,
                y,
                298 * value / maximum,
                12,
                rx=3,
                ry=3,
                strokeColor=None,
                fillColor=color,
            )
        )
        chart.add(
            String(
                459,
                y + 2,
                f"{value:.1f}{suffix}",
                textAnchor="end",
                fontName="Helvetica-Bold",
                fontSize=10,
                fillColor=INK,
            )
        )
    return chart


def page_frame(canvas, doc):
    width, height = A4
    canvas.setFillColor(LIGHT)
    canvas.rect(0, height - 9, width, 9, fill=1, stroke=0)
    canvas.setFillColor(GREEN)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN + 6, height - 45, "HOSTEL COOLING AI")
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN + 6, 48, width - MARGIN - 6, 48)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        MARGIN + 6, 32, "CE F417 + CE F423   /   Simulated course project"
    )
    canvas.drawRightString(width - MARGIN - 6, 32, str(doc.page))


def build():
    evidence = ROOT / "outputs" / "study"
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    rows = {row["method"]: row for row in summary["rows"]}
    fixed, project = rows["fixed"], rows["ours"]
    fixed_energy, project_energy = fixed["fan_wh_day"], project["fan_wh_day"]
    fixed_discomfort, project_discomfort = (
        fixed["comfort_violation_pct"],
        project["comfort_violation_pct"],
    )
    saving = 100 * (1 - project_energy / fixed_energy)
    discomfort_change = project_discomfort - fixed_discomfort
    language = summary["language_evaluation"]
    correct = round(language["n"] * language["exact_match_accuracy"])

    story = [
        p("Cooling a hostel room", "title"),
        p(
            "Should you turn up the fan, open the window or pull the curtains? This dashboard lets you try those choices in a simulated hostel room.",
            "lead",
        ),
        p("Using the dashboard", "heading"),
        p(
            "<b>1. Set the scene.</b> Choose studying, sleeping or away. Enter the indoor and outdoor conditions and tell the app if it’s raining or the window is unavailable."
        ),
        p(
            "<b>2. Get suggested settings.</b> See what to do with the fan, window and curtains. Compare estimated room temperature and fan electricity after an hour with the suggestion or a fixed schedule."
        ),
        p(
            "<b>3. Try the suggestion.</b> Run the simulation for 15 minutes. You can adjust the conditions and try again. The dashboard works with a virtual room."
        ),
        p(
            "<b>Try the rain example.</b> Open it from My room. Both cases use the same example room (31°C inside, 29°C outside). The window is open in the dry case and closed when it rains.",
            "example",
        ),
        p("How it chooses settings", "heading"),
        p(
            "The room model estimates how settings affect heat and airflow. The controller checks allowed combinations and balances modeled comfort, fan electricity and noise."
        ),
        p("Tell it what feels comfortable", "heading"),
        p(
            "With your permission, the language model can interpret a note like “I prefer 27°C when I study.” Review the interpretation before saving. You can export or erase this profile’s saved data."
        ),
        p(
            '<link href="http://127.0.0.1:8765/" color="#2A694E"><u>Open the dashboard</u></link> after starting the app on your computer.'
        ),
        PageBreak(),
        p("What the study found", "title"),
        p(
            f"We compared {len(rows)} ways of running the room over {summary['days_per_seed']} days in each of {len(summary['seeds'])} weather scenarios. A simulated student’s comfort was estimated throughout the trial.",
            "lead",
        ),
        measure(
            "Daily fan electricity (Wh/day)", fixed_energy, project_energy, 500, ""
        ),
        Spacer(1, 12),
        measure(
            "Time outside the modeled comfort range",
            fixed_discomfort,
            project_discomfort,
            100,
            "%",
        ),
        Spacer(1, 12),
        p(
            f"The project method used <b>{saving:.1f}% less fan electricity</b> than a fixed schedule. The room was outside the modeled comfort range <b>{discomfort_change:.1f} percentage points more often</b> while occupied."
        ),
        p("Why you review preferences", "heading"),
        p(
            f"The local language model got <b>{correct} out of {language['n']}</b> test phrases exactly right. The confirmation step lets you catch an incorrect temperature or activity before it is saved."
        ),
        p("What a real-room trial could tell us", "heading"),
        p(
            "These numbers come from simulated rooms and comfort estimates. A trial with consenting students could compare measured fan electricity and ask students how comfortable they actually felt."
        ),
        p(
            "Study files in outputs/study: summary.json, language_evaluation.json and hypothesis_assessment.json.",
            "source",
        ),
    ]
    SimpleDocTemplate(
        str(TARGET),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=72,
        bottomMargin=64,
        title="Hostel Cooling AI | Project Overview",
    ).build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    print(TARGET)


if __name__ == "__main__":
    build()

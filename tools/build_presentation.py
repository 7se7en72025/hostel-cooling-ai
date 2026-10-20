"""Build native editable PowerPoint charts and tables from recorded study results."""

import argparse
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hostel_cooling.presentation_content import write_presentation_content

INK = "193D31"
GREEN = "286B50"
MUTED = "66786D"
PAPER = "F7F8F3"
PALE = "E6EDE0"
WHITE = "FFFFFF"
FONT = "Arial"
LABELS = {
    "fixed": "Fixed schedule",
    "expert": "Expert rules",
    "adaptive": "Adaptive",
    "ann": "ANN",
    "physics": "Physics only",
    "generic_llm": "Generic LLM",
    "ours": "Proposed",
    "survey": "Initial survey",
    "no_physics": "No physics",
}


def color(value):
    return RGBColor.from_string(value)


def text(slide, value, x, y, w, h, size=21, ink=INK, bold=False, align=PP_ALIGN.LEFT):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = 0
    frame.margin_top = frame.margin_bottom = 0
    for i, line in enumerate(value.split("\n")):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.text = line
        p.alignment = align
        p.space_after = Pt(10)
        p.font.name = FONT
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = color(ink)
    return shape


def footer(slide, number, total, dark=False):
    ink = "C8D5C6" if dark else MUTED
    text(slide, "CE F417 + CE F423 / Simulated pilot", 0.72, 7.04, 10.2, 0.24, 10, ink)
    text(
        slide,
        f"{number:02d} / {total:02d}",
        11.6,
        7.04,
        1,
        0.24,
        10,
        ink,
        align=PP_ALIGN.RIGHT,
    )


def bullets(slide, lines, y=1.72, width=11.7, size=21, height=4.75):
    spacing = min(0.9, height / max(1, len(lines)))
    for i, line in enumerate(lines):
        text(slide, line, 0.77, y + i * spacing, width, spacing - 0.1, size)


def native_table(slide, rows, widths, y=1.72, height=4.6, font_size=18):
    rows = [[LABELS.get(str(c), str(c)) for c in row] for row in rows]
    table = slide.shapes.add_table(
        len(rows),
        len(rows[0]),
        Inches(0.72),
        Inches(y),
        Inches(sum(widths)),
        Inches(height),
    ).table
    for i, width in enumerate(widths):
        table.columns[i].width = Inches(width)
    for ri, row in enumerate(rows):
        table.rows[ri].height = Inches(
            0.48 if ri == 0 else (height - 0.48) / (len(rows) - 1)
        )
        for ci, value in enumerate(row):
            cell = table.cell(ri, ci)
            cell.text = value
            cell.margin_left = cell.margin_right = Inches(0.12)
            cell.margin_top = cell.margin_bottom = Inches(0.08)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = color(
                PALE if ri == 0 else (WHITE if ri % 2 else PAPER)
            )
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT
                p.font.size = Pt(font_size if ri else 16)
                p.font.bold = ri == 0 or ci == 0
                p.font.color.rgb = color(INK)
                p.space_after = Pt(0)
    return table


def native_chart(slide, spec):
    data = CategoryChartData()
    data.categories = [LABELS.get(c, c) for c in spec["categories"]]
    data.add_series(spec["unit"], spec["values"])
    line = spec["kind"] == "line"
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.LINE_MARKERS if line else XL_CHART_TYPE.BAR_CLUSTERED,
        Inches(0.72),
        Inches(1.82),
        Inches(11.7),
        Inches(4.15),
        data,
    ).chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.name = FONT
    chart.font.size = Pt(17)
    chart.font.color.rgb = color(INK)
    chart.chart_style = 10
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.position = (
        XL_LABEL_POSITION.ABOVE if line else XL_LABEL_POSITION.OUTSIDE_END
    )
    plot.data_labels.font.name = FONT
    plot.data_labels.font.size = Pt(17)
    plot.data_labels.font.color.rgb = color(INK)
    plot.data_labels.number_format = "0.000" if "RMSE" in spec["unit"] else "0.0"
    series = chart.series[0]
    series.format.line.color.rgb = color(GREEN)
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = color(GREEN)
    if not line:
        plot.gap_width = 75
        for point, category in zip(series.points, spec["categories"]):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = color(
                GREEN
                if category == "ours" or len(spec["categories"]) == 2
                else "9CAA9B"
            )
            point.format.line.fill.background()
        chart.category_axis.reverse_order = True
    for axis in (chart.category_axis, chart.value_axis):
        axis.tick_labels.font.name = FONT
        axis.tick_labels.font.size = Pt(17)
        axis.tick_labels.font.color.rgb = color(INK)
        axis.format.line.fill.background()
    chart.value_axis.has_major_gridlines = False
    chart.value_axis.minimum_scale = 0
    chart.value_axis.maximum_scale = max(spec["values"]) * 1.23
    text(slide, spec["unit"], 0.77, 1.36, 11.5, 0.3, 16, MUTED)
    if line:
        text(
            slide,
            "Objective energy weight",
            0.77,
            5.92,
            11.5,
            0.3,
            16,
            MUTED,
            align=PP_ALIGN.CENTER,
        )
    return chart


def build(out):
    out = Path(out)
    slides = write_presentation_content(out)
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333333), Inches(7.5)
    deck.core_properties.title = "Preference-aware cooling for student hostels"
    deck.core_properties.subject = (
        "Combined CE F417 and CE F423 final simulated research project"
    )
    deck.core_properties.author = "Hostel Cooling Project"
    deck.core_properties.keywords = (
        "CE F417, CE F423, passive cooling, Qwen3, fuzzy comfort, genetic algorithm"
    )
    for n, content in enumerate(slides, 1):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = color(INK if n == 1 else PAPER)
        if n == 1:
            text(slide, "CE F417 + CE F423", 0.78, 1.1, 11.5, 0.35, 17, "C8D5C6")
            text(
                slide, "Cooling for\nstudent hostels", 0.75, 2, 11.6, 2, 44, WHITE, True
            )
            text(
                slide,
                "Preference memory, building physics and room control",
                0.8,
                4.55,
                10.9,
                0.9,
                24,
                "DEE6D8",
            )
            text(
                slide,
                "Final simulated research project / October 2026",
                0.8,
                6.05,
                11,
                0.4,
                17,
                "C8D5C6",
            )
        else:
            text(slide, content["title"], 0.72, 0.55, 11.88, 0.9, 32, INK, True)
            if "table" in content:
                cols = len(content["table"][0])
                if "hypothesis" in content["title"]:
                    widths = [1.12, 4.1, 6.55]
                    table_rows = [["Test", "Finding", "Evidence"]] + [
                        [r[0].split()[-1], r[1], r[2]] for r in content["table"][1:]
                    ]
                    native_table(slide, table_rows, widths, height=4.85, font_size=17)
                else:
                    widths = [4.2, 3.8, 3.77] if cols == 3 else [4.5, 2.35, 2.45, 2.47]
                    table_height = 3.8 if len(content["table"]) <= 5 else 4.2
                    native_table(
                        slide,
                        content["table"],
                        widths,
                        height=table_height,
                        font_size=18,
                    )
                    for i, line in enumerate(content.get("lines", [])):
                        text(
                            slide,
                            line,
                            0.78,
                            1.82 + table_height + i * 0.34,
                            11.65,
                            0.42,
                            16,
                            MUTED,
                        )
            elif "chart" in content:
                native_chart(slide, content["chart"])
                lines = content.get("lines", [])
                text(slide, "\n".join(lines), 0.78, 6.25, 11.7, 0.7, 15, MUTED)
            else:
                lines = content.get("lines", [])
                bullets(slide, lines, size=21 if len(lines) <= 5 else 19, height=4.8)
        footer(slide, n, len(slides), n == 1)
        slide.notes_slide.notes_text_frame.text = (
            content.get("notes", "")
            + "\n\n"
            + "Evidence: outputs/study/summary.json and associated raw study files. "
            + "All room and occupant outcomes are synthetic. Actual local transformer inference and saved model training were executed."
        )
    target = out / "Hostel_Cooling_Final_Presentation.pptx"
    deck.save(target)
    print(
        json.dumps(
            {
                "path": str(target.resolve()),
                "slides": len(slides),
                "native_charts": sum("chart" in s for s in slides),
                "native_tables": sum("table" in s for s in slides),
            },
            indent=2,
        )
    )
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/study")
    build(parser.parse_args().output)

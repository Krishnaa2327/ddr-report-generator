import os
import base64
import json
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────
# HTML Report Template
# ─────────────────────────────────────────────
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Detailed Diagnostic Report (DDR)</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #2c2c2c;
            background: #f5f5f5;
            line-height: 1.6;
        }}

        .page-wrapper {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}

        /* ── Header ── */
        .report-header {{
            background: linear-gradient(135deg, #1a3c5e 0%, #2d6a9f 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .report-header h1 {{
            font-size: 28px;
            letter-spacing: 2px;
            margin-bottom: 8px;
        }}
        .report-header .subtitle {{
            font-size: 14px;
            opacity: 0.85;
            margin-bottom: 20px;
        }}
        .report-header .meta-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 20px;
            text-align: left;
        }}
        .report-header .meta-item {{
            background: rgba(255,255,255,0.15);
            padding: 10px 14px;
            border-radius: 6px;
        }}
        .report-header .meta-item .label {{
            font-size: 10px;
            opacity: 0.75;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .report-header .meta-item .value {{
            font-size: 13px;
            font-weight: 600;
            margin-top: 2px;
        }}

        /* ── Severity Banner ── */
        .severity-banner {{
            display: flex;
            justify-content: center;
            gap: 30px;
            padding: 20px 40px;
            background: #f8f9fa;
            border-bottom: 2px solid #e0e0e0;
        }}
        .sev-box {{
            text-align: center;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
        }}
        .sev-box.high {{ background: #fde8e8; color: #c0392b; border: 2px solid #e74c3c; }}
        .sev-box.medium {{ background: #fef3cd; color: #d35400; border: 2px solid #f39c12; }}
        .sev-box.low {{ background: #d4edda; color: #1e8449; border: 2px solid #27ae60; }}
        .sev-box .count {{ font-size: 28px; display: block; }}
        .sev-box .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}

        /* ── Section Styles ── */
        .section {{
            padding: 35px 40px;
            border-bottom: 1px solid #e8e8e8;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #1a3c5e;
            margin-bottom: 18px;
            padding-bottom: 10px;
            border-bottom: 3px solid #2d6a9f;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-title .number {{
            background: #2d6a9f;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            flex-shrink: 0;
        }}

        /* ── Summary ── */
        .summary-text {{
            background: #eef4fb;
            border-left: 4px solid #2d6a9f;
            padding: 18px 20px;
            border-radius: 0 8px 8px 0;
            font-size: 14px;
            line-height: 1.8;
            color: #333;
        }}

        /* ── Area Cards ── */
        .area-card {{
            border: 1px solid #dde4ed;
            border-radius: 10px;
            margin-bottom: 28px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .area-card-header {{
            padding: 14px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .area-card-header.high {{ background: #fde8e8; border-left: 5px solid #e74c3c; }}
        .area-card-header.medium {{ background: #fef3cd; border-left: 5px solid #f39c12; }}
        .area-card-header.low {{ background: #d4edda; border-left: 5px solid #27ae60; }}
        .area-card-header.na {{ background: #f0f0f0; border-left: 5px solid #999; }}
        .area-name {{ font-size: 16px; font-weight: 700; color: #1a3c5e; }}
        .severity-badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .badge-high {{ background: #e74c3c; color: white; }}
        .badge-medium {{ background: #f39c12; color: white; }}
        .badge-low {{ background: #27ae60; color: white; }}
        .badge-na {{ background: #999; color: white; }}

        .area-card-body {{ padding: 20px; }}

        .obs-text {{
            font-size: 13px;
            line-height: 1.8;
            color: #333;
            white-space: pre-wrap;
            margin-bottom: 16px;
        }}

        /* ── Conflict Box ── */
        .conflict-box {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 14px;
            font-size: 12px;
        }}
        .conflict-box strong {{ color: #856404; }}

        /* ── Images Grid ── */
        .images-section {{ margin-top: 16px; }}
        .images-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .images-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }}
        .image-item {{
            border: 1px solid #ddd;
            border-radius: 6px;
            overflow: hidden;
        }}
        .image-item img {{
            width: 100%;
            height: 140px;
            object-fit: cover;
            display: block;
        }}
        .image-caption {{
            padding: 6px 8px;
            font-size: 10px;
            color: #555;
            background: #f9f9f9;
            border-top: 1px solid #eee;
            text-align: center;
        }}
        .image-missing {{
            width: 100%;
            height: 140px;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
            font-size: 11px;
            text-align: center;
        }}

        /* ── Actions List ── */
        .actions-list {{
            list-style: none;
            margin-top: 12px;
        }}
        .actions-list li {{
            padding: 8px 12px 8px 36px;
            position: relative;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }}
        .actions-list li::before {{
            content: counter(action-counter);
            counter-increment: action-counter;
            position: absolute;
            left: 8px;
            top: 8px;
            background: #2d6a9f;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            font-size: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
        }}
        .actions-container {{ counter-reset: action-counter; }}

        .urgency-tag {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-top: 8px;
        }}
        .urgency-immediate {{ background: #fde8e8; color: #c0392b; }}
        .urgency-month {{ background: #fef3cd; color: #d35400; }}
        .urgency-quarter {{ background: #d4edda; color: #1e8449; }}
        .urgency-routine {{ background: #e8f4fd; color: #1a5276; }}

        /* ── Notes & Missing Info ── */
        .notes-box {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 18px 20px;
            font-size: 13px;
            line-height: 1.8;
            white-space: pre-wrap;
        }}
        .missing-box {{
            background: #fff8e1;
            border: 1px solid #ffcc02;
            border-radius: 8px;
            padding: 18px 20px;
            font-size: 13px;
            line-height: 1.8;
            white-space: pre-wrap;
        }}

        /* ── Footer ── */
        .report-footer {{
            background: #1a3c5e;
            color: rgba(255,255,255,0.7);
            text-align: center;
            padding: 20px 40px;
            font-size: 11px;
        }}
        .report-footer strong {{ color: white; }}

        /* ── Print ── */
        @media print {{
            body {{ background: white; }}
            .page-wrapper {{ box-shadow: none; }}
            .area-card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
<div class="page-wrapper">

    <!-- Header -->
    <div class="report-header">
        <h1>DETAILED DIAGNOSTIC REPORT</h1>
        <div class="subtitle">Property Inspection & Thermal Analysis</div>
        <div class="meta-grid">
            <div class="meta-item">
                <div class="label">Inspection Date</div>
                <div class="value">{inspection_date}</div>
            </div>
            <div class="meta-item">
                <div class="label">Inspected By</div>
                <div class="value">{inspected_by}</div>
            </div>
            <div class="meta-item">
                <div class="label">Property Type</div>
                <div class="value">{property_type}</div>
            </div>
            <div class="meta-item">
                <div class="label">Total Floors</div>
                <div class="value">{floors}</div>
            </div>
            <div class="meta-item">
                <div class="label">Inspection Score</div>
                <div class="value">{score}</div>
            </div>
            <div class="meta-item">
                <div class="label">Report Generated</div>
                <div class="value">{generated_date}</div>
            </div>
        </div>
    </div>

    <!-- Severity Banner -->
    <div class="severity-banner">
        <div class="sev-box high">
            <span class="count">{high_count}</span>
            <span class="label">High Severity</span>
        </div>
        <div class="sev-box medium">
            <span class="count">{medium_count}</span>
            <span class="label">Medium Severity</span>
        </div>
        <div class="sev-box low">
            <span class="count">{low_count}</span>
            <span class="label">Low Severity</span>
        </div>
    </div>

    <!-- Section 1: Property Issue Summary -->
    <div class="section">
        <div class="section-title">
            <span class="number">1</span>
            Property Issue Summary
        </div>
        <div class="summary-text">{property_summary}</div>
    </div>

    <!-- Section 2: Area-wise Observations -->
    <div class="section">
        <div class="section-title">
            <span class="number">2</span>
            Area-wise Observations
        </div>
        {area_cards_html}
    </div>

    <!-- Section 3-5 are embedded in area cards above -->

    <!-- Section 6: Additional Notes -->
    <div class="section">
        <div class="section-title">
            <span class="number">6</span>
            Additional Notes
        </div>
        <div class="notes-box">{additional_notes}</div>
    </div>

    <!-- Section 7: Missing or Unclear Information -->
    <div class="section">
        <div class="section-title">
            <span class="number">7</span>
            Missing or Unclear Information
        </div>
        <div class="missing-box">{missing_information}</div>
    </div>

    <!-- Footer -->
    <div class="report-footer">
        <strong>Detailed Diagnostic Report (DDR)</strong> &nbsp;|&nbsp;
        Generated on {generated_date} &nbsp;|&nbsp;
        Powered by AI-assisted analysis &nbsp;|&nbsp;
        This report is based solely on provided inspection and thermal data.
    </div>

</div>
</body>
</html>
"""


def build_html_report(
    ddr_data: dict,
    image_map: dict,
    output_path: str = "outputs/final_ddr_report.html"
) -> str:
    """
    Builds a complete HTML DDR report from the structured DDR data.

    Args:
        ddr_data: Output from report_generator.generate_ddr_report()
        image_map: Output from image_mapper.map_images_to_areas()
        output_path: Where to save the HTML file

    Returns:
        Path to saved HTML file
    """
    print("[PDFBuilder] Injecting images into report...")

    # Inject images from image_map into area_observations
    for obs in ddr_data.get("area_observations", []):
        area = obs.get("area", "")
        obs["images"] = image_map.get(area, [])

    print("[PDFBuilder] Building HTML report...")

    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

    metadata = ddr_data.get("metadata", {})
    severity_counts = ddr_data.get("severity_counts", {})

    # ── Build area cards HTML ──
    area_cards_html = _build_area_cards(ddr_data.get("area_observations", []))

    # ── Fill template ──
    html = HTML_TEMPLATE.format(
        inspection_date=metadata.get("inspection_date", "Not Available"),
        inspected_by=metadata.get("inspected_by", "Not Available"),
        property_type=metadata.get("property_type", "Not Available"),
        floors=metadata.get("floors", "Not Available"),
        score=metadata.get("score", "Not Available"),
        generated_date=datetime.now().strftime("%d %B %Y, %H:%M"),
        high_count=severity_counts.get("High", 0),
        medium_count=severity_counts.get("Medium", 0),
        low_count=severity_counts.get("Low", 0),
        property_summary=_escape_html(ddr_data.get("property_summary", "Not Available")),
        area_cards_html=area_cards_html,
        additional_notes=_escape_html(ddr_data.get("additional_notes", "Not Available")),
        missing_information=_escape_html(ddr_data.get("missing_information", "Not Available"))
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[PDFBuilder] HTML report saved → {output_path}")
    return output_path


def _build_area_cards(area_observations: list) -> str:
    """Builds HTML for all area observation cards."""
    cards = []

    for obs in area_observations:
        area_name = obs.get("area", "Unknown")
        severity = obs.get("severity", "Not Available")
        urgency = obs.get("urgency", "Not Available")
        obs_text = obs.get("observation_text", "Not Available")
        images = obs.get("images", [])
        actions = obs.get("recommended_actions", [])
        root_cause = obs.get("root_cause", "Not Available")
        conflict = obs.get("conflict", "None")

        sev_lower = severity.lower() if severity else "na"
        sev_class = sev_lower if sev_lower in ["high", "medium", "low"] else "na"
        badge_class = f"badge-{sev_class}"

        # Conflict warning
        conflict_html = ""
        if conflict and conflict.lower() not in ["none", ""]:
            conflict_html = f"""
            <div class="conflict-box">
                <strong>⚠ Data Conflict Noted:</strong> {_escape_html(conflict)}
            </div>"""

        # Images
        images_html = _build_images_html(images)

        # Actions list
        actions_html = ""
        if actions:
            action_items = "".join(
                f"<li>{_escape_html(a)}</li>" for a in actions
            )
            actions_html = f"""
            <div style="margin-top:14px;">
                <strong style="font-size:12px;color:#1a3c5e;text-transform:uppercase;
                letter-spacing:0.5px;">Recommended Actions</strong>
                <div class="actions-container">
                    <ul class="actions-list">{action_items}</ul>
                </div>
            </div>"""

        # Urgency tag
        urgency_html = ""
        if urgency and urgency != "Not Available":
            urgency_css = _get_urgency_class(urgency)
            urgency_html = f'<span class="urgency-tag {urgency_css}">⏱ {_escape_html(urgency)}</span>'

        # Root cause
        root_cause_html = ""
        if root_cause and root_cause != "Not Available":
            root_cause_html = f"""
            <div style="background:#f0f4f8;padding:10px 14px;border-radius:6px;
                margin-bottom:12px;font-size:12px;">
                <strong style="color:#1a3c5e;">Probable Root Cause: </strong>
                {_escape_html(root_cause)}
            </div>"""

        card = f"""
        <div class="area-card">
            <div class="area-card-header {sev_class}">
                <span class="area-name">{_escape_html(area_name)}</span>
                <span class="severity-badge {badge_class}">{severity}</span>
            </div>
            <div class="area-card-body">
                {conflict_html}
                {root_cause_html}
                <div class="obs-text">{_escape_html(obs_text)}</div>
                {urgency_html}
                {actions_html}
                {images_html}
            </div>
        </div>"""

        cards.append(card)

    return "\n".join(cards)


def _build_images_html(images: list) -> str:
    """Builds images grid HTML for an area."""
    if not images:
        return ""

    image_items = []
    for img in images:
        path = img.get("path", "")
        caption = img.get("caption", "")
        img_type = img.get("type", "")

        if path and os.path.exists(path):
            # Embed image as base64
            b64 = _encode_image_base64(path)
            ext = Path(path).suffix.lower().strip(".")
            mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            type_label = "🌡 Thermal" if img_type == "thermal" else ("👁 Visual" if img_type == "visual" else "📷 Inspection")
            image_items.append(f"""
            <div class="image-item">
                <img src="data:{mime};base64,{b64}" alt="{_escape_html(caption)}" />
                <div class="image-caption">{type_label} | {_escape_html(caption[:60])}</div>
            </div>""")
        else:
            image_items.append("""
            <div class="image-item">
                <div class="image-missing">Image Not Available</div>
                <div class="image-caption">Image Not Available</div>
            </div>""")

    return f"""
    <div class="images-section">
        <div class="images-label">📸 Supporting Images</div>
        <div class="images-grid">{"".join(image_items)}</div>
    </div>"""


def _encode_image_base64(image_path: str) -> str:
    """Encodes image file to base64 string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[WARNING] Could not encode image {image_path}: {e}")
        return ""


def _get_urgency_class(urgency: str) -> str:
    """Returns CSS class for urgency tag."""
    urgency_lower = urgency.lower()
    if "immediate" in urgency_lower:
        return "urgency-immediate"
    elif "1 month" in urgency_lower or "month" in urgency_lower:
        return "urgency-month"
    elif "3 month" in urgency_lower or "quarter" in urgency_lower:
        return "urgency-quarter"
    else:
        return "urgency-routine"


def _escape_html(text: str) -> str:
    """Escapes special HTML characters."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def save_ddr_json(ddr_data: dict, output_path: str = "outputs/ddr_data.json") -> str:
    """Saves the raw DDR data as JSON for debugging/reuse."""
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ddr_data, f, indent=2, ensure_ascii=False)
    print(f"[PDFBuilder] DDR JSON saved → {output_path}")
    return output_path
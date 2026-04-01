import re
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AREA_REPORT_PROMPT = """
You are generating a section of a client-ready Detailed Diagnostic Report (DDR).

Area Data:
{area_data}

Write a professional observation entry including:
- What was observed (inspection + thermal combined)
- Temperature data if available
- Conflict note if exists
- Root cause in simple language
- Severity: [HIGH] / [MEDIUM] / [LOW]
- Recommended actions as numbered list
- Urgency note

Rules:
- Simple client-friendly language
- Do NOT add information not in the data
- If field is "Not Available", skip it gracefully

Return only the formatted text. No JSON.
"""

PROPERTY_SUMMARY_PROMPT = """
Based on this diagnostic data, write a concise Property Issue Summary paragraph (3-5 sentences).

Data: {data}

Requirements:
- Summarize overall property condition
- Mention number of affected areas
- Mention most critical issues
- Simple client-friendly language
- Paragraph form, no bullet points

Return only the summary text.
"""

MISSING_INFO_PROMPT = """
Review this data and list missing or unclear information (max 6 bullet points).

Data: {data}

Look for:
- Missing property details (age, address)
- Areas mentioned but not fully inspected
- Missing temperature readings
- Conflicting data points
- Unclear issue sources

Return as bullet list only.
"""

NOTES_PROMPT = """
Based on this inspection metadata and findings, write 2-3 additional notes for the client.

Metadata: {metadata}
Total areas affected: {total_areas}

Cover:
- Whether previous repairs/audits were done
- General building condition
- Recommendations for future inspections

Return as short bullet points only.
"""


def generate_ddr_report(reasoned_data: list) -> dict:
    """
    Called by main.py with reasoned_data list.
    Returns complete DDR dict ready for build_html_report().
    """
    print("  [ReportGenerator] Generating property summary...")
    property_summary = _generate_property_summary(reasoned_data)

    print("  [ReportGenerator] Generating area observation texts...")
    area_observations = []
    for area_data in reasoned_data:
        obs_text = _generate_area_text(area_data)
        area_observations.append({
            "area":                area_data.get("area", "Unknown"),
            "observation_text":   obs_text,
            "severity":           area_data.get("severity", "Not Available"),
            "urgency":            area_data.get("urgency", "Not Available"),
            "recommended_actions": area_data.get("recommended_actions", []),
            "root_cause":         area_data.get("probable_root_cause", "Not Available"),
            "conflict":           area_data.get("conflict", "None"),
            # Images added later by main.py via image_map
            "images": []
        })

    print("  [ReportGenerator] Generating missing info & notes...")
    missing_information = _generate_missing_info(reasoned_data)
    additional_notes    = _generate_notes(reasoned_data)

    ddr = {
        "property_summary":   property_summary,
        "area_observations":  area_observations,
        "additional_notes":   additional_notes,
        "missing_information": missing_information,
        "total_areas":        len(area_observations),
        "severity_counts":    _count_severities(area_observations),
        # metadata injected by build_html_report from image_map step
        "metadata": {}
    }

    print(f"  [ReportGenerator] DDR built — {len(area_observations)} areas")
    return ddr


def _generate_property_summary(reasoned_data: list) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROPERTY_SUMMARY_PROMPT.format(
                data=json.dumps(reasoned_data, indent=2)
            )}],
            temperature=0.3,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [ERROR] Property summary failed: {e}")
        high = [d["area"] for d in reasoned_data if d.get("severity") == "High"]
        return (
            f"A total of {len(reasoned_data)} areas were found to have issues. "
            f"{'High severity issues found in: ' + ', '.join(high) + '.' if high else ''}"
        )


def _generate_area_text(area_data: dict) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional building inspector. Be clear, concise, and factual."
                },
                {
                    "role": "user",
                    "content": AREA_REPORT_PROMPT.format(
                        area_data=json.dumps(area_data, indent=2)
                    )
                }
            ],
            temperature=0.2,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [ERROR] Area text failed for {area_data.get('area','?')}: {e}")
        return _fallback_area_text(area_data)


def _generate_missing_info(reasoned_data: list) -> str:
    try:
        summary = {
            "areas_covered": [d.get("area") for d in reasoned_data],
            "areas_no_thermal": [
                d.get("area") for d in reasoned_data
                if "thermal" not in d.get("data_sources", [])
            ],
            "conflicts": [
                {"area": d.get("area"), "conflict": d.get("conflict")}
                for d in reasoned_data
                if d.get("conflict") not in ["None", None, ""]
            ]
        }
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": MISSING_INFO_PROMPT.format(
                data=json.dumps(summary, indent=2)
            )}],
            temperature=0.2,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [ERROR] Missing info failed: {e}")
        return "- Property address not provided\n- Property age not provided"


def _generate_notes(reasoned_data: list) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": NOTES_PROMPT.format(
                metadata="Not Available",
                total_areas=len(reasoned_data)
            )}],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [ERROR] Notes generation failed: {e}")
        return "- No previous structural audit on record\n- Recommend annual inspection"


def _fallback_area_text(data: dict) -> str:
    lines = [f"Area: {data.get('area', 'Unknown')}"]
    if data.get("combined_observation"):
        lines.append(f"Observation: {data['combined_observation']}")
    if data.get("probable_root_cause"):
        lines.append(f"Root Cause: {data['probable_root_cause']}")
    if data.get("severity"):
        lines.append(f"Severity: [{data['severity'].upper()}]")
    if data.get("recommended_actions"):
        lines.append("Actions:")
        for i, a in enumerate(data["recommended_actions"], 1):
            lines.append(f"  {i}. {a}")
    return "\n".join(lines)


def _count_severities(area_observations: list) -> dict:
    counts = {"High": 0, "Medium": 0, "Low": 0, "Not Available": 0}
    for obs in area_observations:
        sev = obs.get("severity", "Not Available")
        counts[sev] = counts.get(sev, 0) + 1
    return counts
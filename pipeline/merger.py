import re
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MERGER_PROMPT = """
You are an AI system merging building inspection data from two sources:
1. Visual inspection observations
2. Thermal camera readings

Merge these into a unified area-wise dataset.

Inspection Observations:
{inspection_json}

Thermal Observations:
{thermal_json}

Rules:
- Group by area name
- Merge entries for the same area
- Remove duplicate descriptions
- If inspection and thermal CONFLICT on same point, note: "CONFLICT: [X] vs [Y]"
- If area only in one source, include it and note other had no data
- Use "Not Available" for missing fields
- Do NOT invent new information

Return ONLY valid JSON array. No explanation, no markdown.

Format:
[
  {{
    "area": "Hall",
    "combined_observation": "...",
    "inspection_finding": "...",
    "thermal_finding": "...",
    "conflict": "None",
    "data_sources": ["inspection", "thermal"]
  }}
]
"""

AREA_ALIASES = {
    "hall": "Hall",
    "living room": "Hall",
    "bedroom": "Bedroom",
    "common bedroom": "Bedroom",
    "master bedroom": "Master Bedroom",
    "mb": "Master Bedroom",
    "kitchen": "Kitchen",
    "parking": "Parking Area",
    "parking area": "Parking Area",
    "common bathroom": "Common Bathroom",
    "bathroom": "Common Bathroom",
    "wc": "Common Bathroom",
    "external wall": "External Wall",
    "external": "External Wall",
}


def merge_data(inspection_observations: list, thermal_observations: list) -> list:
    """
    Called by main.py.
    Merges inspection + thermal observations into unified area list.
    """
    print("  [Merger] Grouping by area...")
    grouped = _group_by_area(inspection_observations, thermal_observations)

    print("  [Merger] Running LLM merge...")
    merged = _llm_merge(grouped)

    conflicts = [a for a in merged if a.get("conflict", "None") not in ["None", "none", "", None]]
    print(f"  [Merger] {len(merged)} areas merged | {len(conflicts)} conflicts found")
    return merged


def _normalize_area(name: str) -> str:
    name_lower = name.lower().strip()
    for alias, canonical in AREA_ALIASES.items():
        if alias in name_lower:
            return canonical
    return name.strip().title()


def _group_by_area(inspection_obs: list, thermal_obs: list) -> dict:
    grouped = {}

    for obs in inspection_obs:
        area = _normalize_area(obs.get("area", "Unknown"))
        if area not in grouped:
            grouped[area] = {"inspection": [], "thermal": []}
        grouped[area]["inspection"].append(obs)

    for obs in thermal_obs:
        area = _normalize_area(obs.get("area", "Not Available"))
        if area in ["Not Available", "Unknown"]:
            area = "Property - General"
        if area not in grouped:
            grouped[area] = {"inspection": [], "thermal": []}
        grouped[area]["thermal"].append(obs)

    return grouped


def _llm_merge(grouped: dict) -> list:
    all_merged = []
    areas = list(grouped.keys())
    batch_size = 5

    for i in range(0, len(areas), batch_size):
        batch_areas = areas[i:i + batch_size]
        batch_inspection, batch_thermal = [], []

        for area in batch_areas:
            for obs in grouped[area]["inspection"]:
                batch_inspection.append({**obs, "area": area})
            for obs in grouped[area]["thermal"]:
                batch_thermal.append({**obs, "area": area})

        if not batch_inspection and not batch_thermal:
            continue

        print(f"  [Merger] Batch {i//batch_size + 1}: {batch_areas}")
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a building diagnostics expert. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": MERGER_PROMPT.format(
                            inspection_json=json.dumps(batch_inspection, indent=2),
                            thermal_json=json.dumps(batch_thermal, indent=2)
                        )
                    }
                ],
                temperature=0.1,
                max_tokens=2500
            )
            raw = response.choices[0].message.content.strip()
            parsed = _safe_parse_json(raw)
            if isinstance(parsed, list):
                all_merged.extend(parsed)

        except Exception as e:
            print(f"  [ERROR] Merge batch failed: {e}")
            for area in batch_areas:
                all_merged.append(_fallback_merge(area, grouped[area]))

    return all_merged


def _fallback_merge(area: str, area_data: dict) -> dict:
    inspection_descs = [o.get("issue_description", "") for o in area_data.get("inspection", [])]
    thermal_descs = [
        f"Hotspot: {o.get('hotspot','?')}, Coldspot: {o.get('coldspot','?')}"
        for o in area_data.get("thermal", [])
    ]
    combined = ". ".join(filter(None, inspection_descs + thermal_descs))
    return {
        "area": area,
        "combined_observation": combined or "Not Available",
        "inspection_finding": "; ".join(inspection_descs) or "Not Available",
        "thermal_finding": "; ".join(thermal_descs) or "Not Available",
        "conflict": "None",
        "data_sources": (
            (["inspection"] if inspection_descs else []) +
            (["thermal"] if thermal_descs else [])
        )
    }


def _safe_parse_json(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return []
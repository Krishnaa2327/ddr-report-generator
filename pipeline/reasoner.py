import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

REASONING_PROMPT = """
You are an expert building diagnostics engineer writing a professional report.

Given the following merged observations for a property, generate diagnostic reasoning.

Merged Observations:
{merged_data}

For each area, generate:
1. probable_root_cause: What is most likely causing this issue based on the data
2. severity: "Low", "Medium", or "High" 
3. severity_reasoning: Brief explanation of why this severity was assigned
4. recommended_actions: List of 2-4 specific actionable steps to fix the issue
5. urgency: "Immediate", "Within 1 Month", "Within 3 Months", "Routine Maintenance"

Rules:
- Base reasoning ONLY on data provided — do not invent facts
- If data is insufficient for root cause → write "Not Available - insufficient data"
- Keep language simple and client-friendly
- Avoid excessive technical jargon
- Severity guide:
  * High: structural risk, active leakage causing damage, electrical hazard
  * Medium: dampness/moisture present, tile hollowness, external cracks
  * Low: minor stains, cosmetic issues, small isolated dampness

Return ONLY valid JSON array. No explanation, no markdown.

Return format:
[
  {{
    "area": "Hall",
    "probable_root_cause": "Water seepage from bathroom above (Flat 203) through open tile joints and faulty nahani trap",
    "severity": "Medium",
    "severity_reasoning": "Active dampness at skirting level indicates ongoing water ingress but no structural damage observed",
    "recommended_actions": [
      "Re-grout tile joints in Common Bathroom of Flat 203 above",
      "Replace or repair faulty nahani trap in bathroom above",
      "Apply waterproofing coat at skirting level in Hall",
      "Monitor for recurrence after repairs"
    ],
    "urgency": "Within 1 Month"
  }}
]
"""

PROPERTY_SUMMARY_PROMPT = """
You are writing a professional property diagnostic report for a client.

Based on the following area-wise diagnostic data, write a concise Property Issue Summary.

Diagnostic Data:
{diagnostic_data}

Property Metadata:
{metadata}

Write a Property Issue Summary that:
- Is 3-5 sentences long
- Summarizes the overall condition of the property
- Mentions the number of areas affected
- Mentions the most critical issues
- Uses simple, client-friendly language
- Does NOT use bullet points — write in paragraph form

Return ONLY the summary text, no JSON, no markdown.
"""


def generate_reasoning(merged_data: list) -> list:
    """
    Generates root cause, severity, and recommended actions for each merged area.
    Returns list of area diagnostics.
    """
    print("[Reasoner] Generating diagnostic reasoning...")

    all_diagnostics = []
    batch_size = 4  # Process 4 areas at a time

    for i in range(0, len(merged_data), batch_size):
        batch = merged_data[i:i + batch_size]
        print(f"[Reasoner] Processing batch {i//batch_size + 1} ({len(batch)} areas)...")

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a certified building diagnostics expert. Provide accurate, evidence-based reasoning. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": REASONING_PROMPT.format(
                            merged_data=json.dumps(batch, indent=2)
                        )
                    }
                ],
                temperature=0.2,
                max_tokens=2500
            )

            raw = response.choices[0].message.content.strip()
            parsed = _safe_parse_json(raw)
            if isinstance(parsed, list):
                all_diagnostics.extend(parsed)

        except Exception as e:
            print(f"[ERROR] Reasoning batch {i//batch_size + 1} failed: {e}")
            # Fallback
            for area_data in batch:
                all_diagnostics.append(_fallback_reasoning(area_data))

    print(f"[Reasoner] Generated reasoning for {len(all_diagnostics)} areas")
    return all_diagnostics


def generate_property_summary(diagnostics: list, metadata: dict) -> str:
    """
    Generates the overall property issue summary paragraph.
    """
    print("[Reasoner] Generating property summary...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional property inspector writing client reports. Be clear, factual, and concise."
                },
                {
                    "role": "user",
                    "content": PROPERTY_SUMMARY_PROMPT.format(
                        diagnostic_data=json.dumps(diagnostics, indent=2),
                        metadata=json.dumps(metadata, indent=2)
                    )
                }
            ],
            temperature=0.3,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[ERROR] Property summary generation failed: {e}")
        high_areas = [d["area"] for d in diagnostics if d.get("severity") == "High"]
        return (
            f"A total of {len(diagnostics)} areas were found to have issues during inspection. "
            f"{'High severity issues were found in: ' + ', '.join(high_areas) + '.' if high_areas else ''} "
            f"Detailed findings are presented below."
        )


def generate_additional_notes(merged_data: list, metadata: dict) -> str:
    """
    Generates additional notes section — general observations, limitations, etc.
    """
    notes_prompt = f"""
Based on this inspection data and metadata, write 2-3 additional notes for the client report.

Metadata: {json.dumps(metadata, indent=2)}
Number of impacted areas: {len(merged_data)}

Notes should cover:
- Whether previous repairs/audits were done
- General building condition observations
- Any limitations of the current inspection
- Recommendations for future inspections

Write as short bullet points (2-3 points max). Use simple language.
Return only the notes text, no JSON.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": notes_prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] Additional notes generation failed: {e}")
        return "Not Available"


def _fallback_reasoning(area_data: dict) -> dict:
    """Simple fallback when LLM fails."""
    return {
        "area": area_data.get("area", "Unknown"),
        "probable_root_cause": "Not Available - LLM processing error",
        "severity": "Medium",
        "severity_reasoning": "Default severity assigned due to processing error",
        "recommended_actions": [
            "Conduct further inspection by qualified engineer",
            "Address observed dampness/moisture issues"
        ],
        "urgency": "Within 1 Month"
    }


def _safe_parse_json(raw: str) -> list:
    """Safely parses JSON."""
    import re
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
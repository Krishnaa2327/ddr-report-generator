import re
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INSPECTION_EXTRACTION_PROMPT = """
You are an AI system that extracts structured inspection data from building inspection reports.
From the following text, extract ALL observations area by area.
Return ONLY valid JSON array. No explanation, no markdown, no code blocks.

Each item must include:
- area (string): e.g. "Hall", "Master Bedroom", "Kitchen", "Parking Area", "Common Bathroom", "External Wall"
- issue_description (string): clear description of the problem
- side (string): "negative" (affected) or "positive" (source/exposed)
- severity_hint (string): if mentioned e.g. "Moderate", "Mild", else "Not Available"
- point_no (string): reference number if available, else "Not Available"

Rules:
- Do NOT invent information
- If area unclear, write "Not Available"
- Extract EVERY observation

Text:
{text}
"""

THERMAL_EXTRACTION_PROMPT = """
You are an AI system extracting thermal inspection data.
From the text below, extract ALL thermal readings.
Return ONLY valid JSON array. No explanation, no markdown, no code blocks.

Each item must include:
- area (string): location if identifiable, else "Not Available"
- image_id (string): thermal image filename e.g. "RB02380X.JPG", else "Not Available"
- hotspot (string): e.g. "28.8 °C", else "Not Available"
- coldspot (string): e.g. "23.4 °C", else "Not Available"
- emissivity (string): e.g. "0.94", else "Not Available"
- reflected_temp (string): e.g. "23 °C", else "Not Available"
- thermal_issue (string): inferred issue e.g. "moisture/dampness detected", else "Not Available"
- date (string): inspection date if available, else "Not Available"

Rules:
- Do NOT guess missing values
- Coldspot significantly below ambient = moisture/dampness

Text:
{text}
"""


def extract_inspection_data(full_text: str) -> list:
    """
    Called by main.py with inspection full_text string.
    Returns list of structured observation dicts.
    """
    print("  [Extractor] Processing inspection text...")
    all_observations = []
    chunks = _chunk_text(full_text, max_chars=8000)

    for i, chunk in enumerate(chunks):
        print(f"  [Extractor] Inspection chunk {i+1}/{len(chunks)}...")
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise building inspection data extraction system. Always return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": INSPECTION_EXTRACTION_PROMPT.format(text=chunk)
                    }
                ],
                temperature=0.1,
                max_tokens=2000
            )
            raw = response.choices[0].message.content.strip()
            parsed = _safe_parse_json(raw)
            if isinstance(parsed, list):
                all_observations.extend(parsed)
        except Exception as e:
            print(f"  [ERROR] Inspection chunk {i+1} failed: {e}")

    all_observations = _deduplicate(all_observations)
    print(f"  [Extractor] {len(all_observations)} inspection observations extracted")
    return all_observations


def extract_thermal_data(full_text: str) -> list:
    """
    Called by main.py with thermal full_text string.
    Returns list of structured thermal reading dicts.
    """
    print("  [Extractor] Processing thermal text...")
    all_thermal = []
    chunks = _chunk_text(full_text, max_chars=8000)

    for i, chunk in enumerate(chunks):
        print(f"  [Extractor] Thermal chunk {i+1}/{len(chunks)}...")
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise thermal inspection data extraction system. Always return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": THERMAL_EXTRACTION_PROMPT.format(text=chunk)
                    }
                ],
                temperature=0.1,
                max_tokens=2000
            )
            raw = response.choices[0].message.content.strip()
            parsed = _safe_parse_json(raw)
            if isinstance(parsed, list):
                all_thermal.extend(parsed)
        except Exception as e:
            print(f"  [ERROR] Thermal chunk {i+1} failed: {e}")

    print(f"  [Extractor] {len(all_thermal)} thermal readings extracted")
    return all_thermal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk_text(text: str, max_chars: int = 8000) -> list:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current += "\n" + line
    if current:
        chunks.append(current)
    return chunks


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


def _deduplicate(observations: list) -> list:
    seen = set()
    unique = []
    for obs in observations:
        key = (
            obs.get("area", "").lower().strip(),
            obs.get("issue_description", "").lower().strip()[:80]
        )
        if key not in seen:
            seen.add(key)
            unique.append(obs)
    return unique
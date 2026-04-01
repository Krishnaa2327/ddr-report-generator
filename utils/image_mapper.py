import os
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AREA_KEYWORDS = {
    "Hall":             ["hall", "living", "skirting level dampness"],
    "Bedroom":          ["bedroom", "common bed"],
    "Master Bedroom":   ["master bedroom", "master bed", "mb bathroom"],
    "Kitchen":          ["kitchen"],
    "Parking Area":     ["parking", "parking area", "parking ceiling"],
    "Common Bathroom":  ["common bathroom", "wc", "nahani", "toilet", "flat 203"],
    "External Wall":    ["external wall", "duct", "crack", "facade"],
    "Property - General": ["general", "overall"]
}


def map_images_to_areas(
    inspection_images: list,
    thermal_images: list,
    merged_data: list
) -> dict:
    """
    Called by main.py.
    Maps inspection + thermal images to their correct report areas.

    Returns:
        {
            "Hall": [{"path":..., "type":..., "caption":...}, ...],
            "Master Bedroom": [...],
            ...
        }
    """
    print("  [ImageMapper] Mapping images to areas...")

    area_names  = [m.get("area", "") for m in merged_data]
    image_map   = {area: [] for area in area_names}

    # ── Map inspection images ──────────────────────────────────
    for img in inspection_images:
        page_num  = img.get("page_num", 0)
        page_text = _get_page_context(img, inspection_images)

        area = (
            _match_by_keywords(page_text, area_names) or
            _match_by_embedding(page_text, area_names) or
            _match_by_sequence(page_num, len(inspection_images), area_names)
        )

        if area and area in image_map:
            image_map[area].append({
                "path":    img["path"],
                "type":    "inspection",
                "caption": f"Inspection photo — Page {page_num}"
            })

    # ── Map thermal images ─────────────────────────────────────
    total_thermal = len(thermal_images)
    for img in thermal_images:
        page_num  = img.get("page_num", 0)
        img_type  = img.get("type", "thermal")

        # Thermal report has no area labels — distribute by sequence
        area = _match_by_sequence(page_num, total_thermal, area_names)

        if area and area in image_map:
            hotspot  = ""
            coldspot = ""
            caption  = (
                f"Thermal image — Hotspot: {hotspot} Coldspot: {coldspot} Page {page_num}"
                if img_type == "thermal"
                else f"Visual reference — Page {page_num}"
            )
            image_map[area].append({
                "path":    img["path"],
                "type":    img_type,
                "caption": caption
            })

    # ── Cap per area ───────────────────────────────────────────
    image_map = _cap_images(image_map, max_inspection=3, max_thermal=2, max_visual=1)

    for area, imgs in image_map.items():
        print(f"  [ImageMapper] {area}: {len(imgs)} images")

    return image_map


def _get_page_context(img: dict, all_images: list) -> str:
    """Returns a context string based on image metadata."""
    return img.get("filename", "") + " " + str(img.get("page_num", ""))


def _match_by_keywords(text: str, area_names: list) -> str | None:
    text_lower = text.lower()
    for area in area_names:
        if area.lower() in text_lower:
            return area
    for canonical, keywords in AREA_KEYWORDS.items():
        if canonical in area_names:
            for kw in keywords:
                if kw in text_lower:
                    return canonical
    return None


def _match_by_embedding(text: str, area_names: list) -> str | None:
    if not text.strip() or not area_names:
        return None
    try:
        text_resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:500]
        )
        text_emb = text_resp.data[0].embedding

        area_resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=area_names
        )
        area_embs = [e.embedding for e in area_resp.data]

        sims = [_cosine_sim(text_emb, ae) for ae in area_embs]
        best_idx = int(np.argmax(sims))

        if sims[best_idx] > 0.35:
            return area_names[best_idx]
    except Exception as e:
        print(f"  [WARNING] Embedding match failed: {e}")
    return None


def _match_by_sequence(page_num: int, total: int, area_names: list) -> str | None:
    if not area_names or total == 0:
        return None
    pages_per_area = max(1, total // len(area_names))
    idx = min((page_num - 1) // pages_per_area, len(area_names) - 1)
    return area_names[idx]


def _cosine_sim(a: list, b: list) -> float:
    va, vb = np.array(a), np.array(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _cap_images(image_map: dict, max_inspection: int, max_thermal: int, max_visual: int) -> dict:
    capped = {}
    for area, images in image_map.items():
        inspection = [i for i in images if i["type"] == "inspection"][:max_inspection]
        thermal    = [i for i in images if i["type"] == "thermal"][:max_thermal]
        visual     = [i for i in images if i["type"] == "visual"][:max_visual]
        capped[area] = inspection + thermal + visual
    return capped
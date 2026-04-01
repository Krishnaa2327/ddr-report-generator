import fitz
import os
import re
import json
from pathlib import Path


def parse_thermal_pdf(pdf_path: str, image_out: str = "outputs/extracted_images/thermal") -> dict:
    """
    Main entry point called by main.py.
    Returns dict with keys: full_text, page_count, images, pages, readings
    """
    Path(image_out).mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    result = {
        "full_text":  "",      # main.py uses full_text
        "page_count": 0,       # main.py uses page_count
        "pages":      [],
        "images":     [],
        "readings":   []       # main.py uses readings
    }

    full_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()
        full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}"

        result["pages"].append({
            "page_num": page_num + 1,
            "text":     page_text
        })

        # Extract images — page has 2 images: thermal + visual
        image_list = page.get_images(full=True)
        page_image_paths = []

        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image  = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext   = base_image["ext"]
                img_type    = "thermal" if img_index == 0 else "visual"
                image_filename = f"thermal_p{page_num + 1}_{img_type}.{image_ext}"
                image_path  = os.path.join(image_out, image_filename)

                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                result["images"].append({
                    "page_num":    page_num + 1,
                    "image_index": img_index + 1,
                    "type":        img_type,
                    "path":        image_path,
                    "filename":    image_filename
                })
                page_image_paths.append((img_type, image_path))

            except Exception as e:
                print(f"[WARNING] Could not extract image p{page_num+1} img{img_index}: {e}")

        # Parse thermal reading for this page
        reading = _parse_thermal_reading(page_text, page_num + 1)
        if reading:
            for img_type, img_path in page_image_paths:
                if img_type == "thermal":
                    reading["thermal_image_path"] = img_path
                elif img_type == "visual":
                    reading["visual_image_path"] = img_path

            reading.setdefault("thermal_image_path", "Image Not Available")
            reading.setdefault("visual_image_path",  "Image Not Available")
            result["readings"].append(reading)   # key is "readings"

    result["full_text"]  = full_text
    result["page_count"] = len(doc)
    doc.close()

    return result


def _parse_thermal_reading(page_text: str, page_num: int) -> dict | None:
    """Extracts thermal measurement data from a single page."""
    if "hotspot" not in page_text.lower():
        return None

    reading = {
        "page_num":       page_num,
        "image_id":       "Not Available",
        "hotspot":        "Not Available",
        "coldspot":       "Not Available",
        "emissivity":     "Not Available",
        "reflected_temp": "Not Available",
        "date":           "Not Available",
        "device":         "Not Available",
        "serial_number":  "Not Available",
        "thermal_image_path": "Image Not Available",
        "visual_image_path":  "Image Not Available"
    }

    patterns = {
        "image_id":       r'Thermal image\s*:\s*([A-Z0-9]+\.JPG)',
        "hotspot":        r'Hotspot\s*:\s*([\d.]+\s*°C)',
        "coldspot":       r'Coldspot\s*:\s*([\d.]+\s*°C)',
        "emissivity":     r'Emissivity\s*:\s*([\d.]+)',
        "reflected_temp": r'Reflected temperature\s*:\s*([\d.]+\s*°C)',
        "date":           r'(\d{2}/\d{2}/\d{2,4})',
        "device":         r'Device\s*:\s*([^\n]+?)(?:Serial|$)',
        "serial_number":  r'Serial Number\s*:\s*([^\n]+)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            reading[key] = match.group(1).strip()

    return reading
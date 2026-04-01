import fitz
import os
import re
import json
from pathlib import Path
from PIL import Image
import numpy as np
import io


def parse_inspection_pdf(pdf_path: str, image_out: str = "outputs/extracted_images/inspection") -> dict:
    """
    Main entry point called by main.py.
    Returns dict with keys: full_text, page_count, images, pages,
                            impacted_areas, summary_table, metadata
    """
    Path(image_out).mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    result = {
        "full_text": "",        # main.py uses full_text
        "page_count": 0,        # main.py uses page_count
        "pages": [],
        "images": [],
        "impacted_areas": [],
        "summary_table": [],
        "metadata": {}
    }

    full_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()
        full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}"

        result["pages"].append({
            "page_num": page_num + 1,
            "text": page_text
        })

        # Extract images — FIX 1 & 3: Filter by size, keep top 2 largest
        image_list = page.get_images(full=True)
        page_images_filtered = []
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Skip PNG images — these are logos/UI elements in the inspection PDF
                # Actual inspection photos are always JPEG
                if image_ext.lower() in ("png", "gif", "bmp", "tiff"):
                    print(f"  [SKIP] Non-JPEG ({image_ext}) on p{page_num+1} (likely logo)")
                    continue

                # FIX 1: Filter out small images (icons, UI elements)
                # Get image dimensions
                try:
                    img_pil = Image.open(io.BytesIO(image_bytes))
                    width, height = img_pil.size
                except Exception:
                    width, height = 0, 0

                # Skip images smaller than 350x350 — real inspection photos are ≥370px
                # The JPEG logo on p9 is only 285×214, so this filters it cleanly
                if width < 350 or height < 350:
                    print(f"  [SKIP] Small image {width}x{height} on p{page_num+1} (too small — logo/icon)")
                    continue
                
                size = width * height
                page_images_filtered.append({
                    "xref": xref,
                    "bytes": image_bytes,
                    "ext": image_ext,
                    "width": width,
                    "height": height,
                    "size": size,
                    "index": img_index
                })
            except Exception as e:
                print(f"[WARNING] Could not process image p{page_num+1} img{img_index}: {e}")
        
        # FIX 3: Keep only top 2 largest images per page
        page_images_filtered = sorted(page_images_filtered, key=lambda x: x["size"], reverse=True)[:2]
        
        for img_data in page_images_filtered:
            try:
                image_bytes = img_data["bytes"]
                image_ext = img_data["ext"]
                image_filename = f"inspection_p{page_num + 1}_img{img_data['index'] + 1}.{image_ext}"
                image_path = os.path.join(image_out, image_filename)

                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                result["images"].append({
                    "page_num": page_num + 1,
                    "image_index": img_data['index'] + 1,
                    "path": image_path,
                    "filename": image_filename,
                    "type": "inspection",
                    "width": img_data["width"],
                    "height": img_data["height"]
                })
            except Exception as e:
                print(f"[ERROR] Failed to save image p{page_num+1}: {e}")

    result["full_text"] = full_text
    result["page_count"] = len(doc)
    doc.close()

    result["impacted_areas"] = _parse_impacted_areas(full_text)
    result["summary_table"]  = _parse_summary_table(full_text)
    result["metadata"]       = _parse_metadata(full_text)

    return result


def _parse_metadata(text: str) -> dict:
    """Extracts property metadata from inspection text."""
    metadata = {
        "inspection_date": "Not Available",
        "inspected_by": "Not Available",
        "property_type": "Not Available",
        "floors": "Not Available",
        "previous_structural_audit": "Not Available",
        "previous_repair_work": "Not Available",
        "score": "Not Available",
        "flagged_items": "Not Available"
    }

    patterns = {
        "inspection_date": r'Inspection Date and Time[:\s]+([^\n]+)',
        "inspected_by":    r'Inspected By[:\s]+([^\n]+)',
        "property_type":   r'Property Type[:\s]+([^\n]+)',
        "floors":          r'Floors[:\s]+([^\n]+)',
        "previous_structural_audit": r'Previous Structural audit done\s+(Yes|No)',
        "previous_repair_work":      r'Previous Repair work done\s+(Yes|No)',
        "score":           r'Score\s+([\d.]+%)',
        "flagged_items":   r'Flagged items\s+(\d+)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    return metadata


def _parse_impacted_areas(text: str) -> list:
    """Extracts impacted area blocks from raw text."""
    areas = []
    area_blocks = re.split(r'Impacted Area\s+\d+', text, flags=re.IGNORECASE)

    for i, block in enumerate(area_blocks[1:], start=1):
        negative_match = re.search(
            r'Negative side Description\s+(.*?)(?:Negative side photographs|Positive side Description|$)',
            block, re.IGNORECASE | re.DOTALL
        )
        positive_match = re.search(
            r'Positive side Description\s+(.*?)(?:Positive side photographs|Impacted Area|$)',
            block, re.IGNORECASE | re.DOTALL
        )

        negative_desc = negative_match.group(1).strip() if negative_match else "Not Available"
        positive_desc = positive_match.group(1).strip() if positive_match else "Not Available"

        negative_desc = re.sub(r'\s+', ' ', negative_desc).strip()
        positive_desc = re.sub(r'\s+', ' ', positive_desc).strip()

        areas.append({
            "area_number":   i,
            "negative_side": negative_desc,
            "positive_side": positive_desc
        })

    return areas


def _parse_summary_table(text: str) -> list:
    """Extracts SUMMARY TABLE entries."""
    summary = []
    summary_match = re.search(
        r'SUMMARY TABLE(.*?)(?:Appendix|Inspection Checklists|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if not summary_match:
        return summary

    table_text = summary_match.group(1)
    rows = re.findall(
        r'(\d+(?:\.\d+)?)\s+(Observed[^0-9]+?)(?=\d+(?:\.\d+)?\s+Observed|\Z)',
        table_text, re.DOTALL
    )

    for point_no, description in rows:
        desc_clean = re.sub(r'\s+', ' ', description).strip()
        summary.append({
            "point_no":    point_no,
            "type":        "exposed_positive" if '.' in point_no else "impacted_negative",
            "description": desc_clean
        })

    return summary
import fitz
import os
import re
import json
from pathlib import Path
from PIL import Image
import numpy as np
import io


def parse_thermal_pdf(pdf_path: str, image_out: str = "outputs/extracted_images/thermal") -> dict:
    """
    Main entry point called by main.py.
    Returns dict with keys: full_text, page_count, images, pages, readings
    
    FIX 1: Filter out small images (UI elements, icons)
    FIX 2: Detect thermal vs visual images by color analysis, not index
    FIX 3: Keep only top 2 images per page
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

        # Extract images — FIX 1 & 3: Filter by size, keep top 2 largest
        image_list = page.get_images(full=True)
        page_images_filtered = []
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image  = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext   = base_image["ext"]
                
                # FIX 1: Filter out small images (icons, UI elements)
                try:
                    img_pil = Image.open(io.BytesIO(image_bytes))
                    width, height = img_pil.size
                except Exception:
                    width, height = 0, 0
                
                # Skip images smaller than 200x200
                if width < 200 or height < 200:
                    print(f"  [SKIP] Small image {width}x{height} on p{page_num+1} (likely UI element)")
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
        
        page_image_paths = []
        for img_data in page_images_filtered:
            try:
                image_bytes = img_data["bytes"]
                image_ext = img_data["ext"]
                
                # FIX 2: Detect thermal vs visual by color analysis, not index
                img_type = _detect_image_type(image_bytes)
                
                image_filename = f"thermal_p{page_num + 1}_{img_type}.{image_ext}"
                image_path  = os.path.join(image_out, image_filename)

                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                result["images"].append({
                    "page_num":    page_num + 1,
                    "image_index": img_data["index"] + 1,
                    "type":        img_type,
                    "path":        image_path,
                    "filename":    image_filename,
                    "width":       img_data["width"],
                    "height":      img_data["height"]
                })
                page_image_paths.append((img_type, image_path))

            except Exception as e:
                print(f"[ERROR] Failed to save image p{page_num+1}: {e}")

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
            result["readings"].append(reading)

    result["full_text"]  = full_text
    result["page_count"] = len(doc)
    doc.close()

    return result


def _detect_image_type(image_bytes: bytes) -> str:
    """
    FIX 2: Detect if image is thermal or visual based on color characteristics.
    Thermal images typically have strong red/warm tones (high red, low blue).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        
        red_mean  = arr[:, :, 0].mean()
        green_mean = arr[:, :, 1].mean()
        blue_mean = arr[:, :, 2].mean()
        
        # Thermal images have higher red channel, lower blue channel
        # Typical pattern: red > 120, blue < 100
        if red_mean > 120 or (red_mean > blue_mean + 20 and red_mean > green_mean):
            return "thermal"
        else:
            return "visual"
    except Exception as e:
        print(f"[WARNING] Could not analyze image colors: {e}")
        return "visual"  # Default to visual if detection fails


def _parse_thermal_reading(page_text: str, page_num: int) -> dict | None:
    """
    Extracts thermal measurement data from a single page.
    
    FIX 4: Handle broken/garbled text extraction gracefully.
    If numerical data is not extractable, we still mark page as having thermal data
    so images can still be used as evidence (even without exact temperatures).
    """
    # FIX 4: More lenient check - allow pages with minimal indicators
    has_thermal_content = (
        "hotspot" in page_text.lower() or
        "thermal" in page_text.lower() or
        "temperature" in page_text.lower() or
        "°c" in page_text.lower() or
        "°C" in page_text.lower()
    )
    
    if not has_thermal_content:
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
        "visual_image_path":  "Image Not Available",
        "data_quality":   "partial"  # FIX 4: Track data quality
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

    extraction_count = 0
    for key, pattern in patterns.items():
        try:
            # FIX 4: Use non-greedy matching and better error handling
            match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean up garbled characters
                value = ''.join(c for c in value if ord(c) > 31 or c in '\n\t')
                if value:
                    reading[key] = value
                    extraction_count += 1
        except Exception as e:
            print(f"[WARNING] Could not extract {key} from p{page_num}: {e}")
    
    # FIX 4: Mark quality based on extraction success
    if extraction_count == 0:
        reading["data_quality"] = "images_only"  # Images available but no numeric data
    elif extraction_count < 4:
        reading["data_quality"] = "partial"
    else:
        reading["data_quality"] = "complete"

    return reading
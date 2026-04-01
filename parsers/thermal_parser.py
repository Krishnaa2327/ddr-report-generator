import fitz
import os
from pathlib import Path
from PIL import Image
import io


def parse_thermal_pdf(pdf_path: str, image_out: str = "outputs/extracted_images/thermal") -> dict:
    """
    Parse the thermal PDF by scanning all xrefs globally.
    
    The thermal PDF uses shared image resources — every page's get_images()
    returns ALL images from the entire document. Instead, we scan xrefs
    globally to find unique thermal/visual JPEG pairs, then save them in order.
    
    Pattern in this PDF:
      - 1080×810 JPEG = thermal image (colorized heat map)
      - 1080×812 JPEG = visual/normal image (regular photo)
    They appear as consecutive xref pairs (N, N+1).
    """
    Path(image_out).mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)

    result = {
        "full_text": "",
        "page_count": 0,
        "pages": [],
        "images": [],
        "readings": []
    }

    full_text = ""

    # ── Step 1: Collect full text from every page ──────────────────────────────
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()
        full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}"
        result["pages"].append({
            "page_num": page_num + 1,
            "text": page_text
        })

    result["full_text"] = full_text
    result["page_count"] = len(doc)

    # ── Step 2: Scan ALL xrefs globally to find unique large JPEG pairs ────────
    # (Per-page get_images() returns ALL images on every page for this PDF type)
    thermal_xrefs = []   # 1080×810 — thermal heat-map images
    visual_xrefs  = []   # 1080×812 — regular visual photos

    for xref in range(1, doc.xref_length()):
        try:
            base = doc.extract_image(xref)
            if not base:
                continue
            ext = base["ext"]
            if ext not in ("jpeg", "jpg"):
                continue
            pil = Image.open(io.BytesIO(base["image"]))
            w, h = pil.size
            if w < 1000 or h < 800:
                continue  # skip small icons / UI elements

            # Classify by height: 810 = thermal, 812 = visual
            if h == 810:
                thermal_xrefs.append((xref, base["image"], ext))
            elif h == 812:
                visual_xrefs.append((xref, base["image"], ext))
            else:
                # Fallback: collect any other large JPEG in order
                thermal_xrefs.append((xref, base["image"], ext))
        except Exception:
            continue

    # Sort both lists by xref so they remain in document order
    thermal_xrefs.sort(key=lambda x: x[0])
    visual_xrefs.sort(key=lambda x: x[0])

    print(f"  [ThermalParser] Found {len(thermal_xrefs)} thermal + {len(visual_xrefs)} visual images globally")

    # ── Step 3: Save pairs in order ────────────────────────────────────────────
    n_pairs = max(len(thermal_xrefs), len(visual_xrefs))

    for idx in range(n_pairs):
        pair_num = idx + 1  # 1-based

        # Save thermal image
        if idx < len(thermal_xrefs):
            xref, img_bytes, ext = thermal_xrefs[idx]
            filename = f"thermal_pair{pair_num:02d}_thermal.{ext}"
            path = os.path.join(image_out, filename)
            with open(path, "wb") as f:
                f.write(img_bytes)
            result["images"].append({
                "pair_num":    pair_num,
                "image_index": 1,
                "type":        "thermal",
                "path":        path,
                "filename":    filename,
                "xref":        xref
            })
            print(f"  [ThermalParser] Pair {pair_num} thermal  -> {filename} (xref={xref})")

        # Save visual image
        if idx < len(visual_xrefs):
            xref, img_bytes, ext = visual_xrefs[idx]
            filename = f"thermal_pair{pair_num:02d}_visual.{ext}"
            path = os.path.join(image_out, filename)
            with open(path, "wb") as f:
                f.write(img_bytes)
            result["images"].append({
                "pair_num":    pair_num,
                "image_index": 2,
                "type":        "visual",
                "path":        path,
                "filename":    filename,
                "xref":        xref
            })
            print(f"  [ThermalParser] Pair {pair_num} visual   -> {filename} (xref={xref})")

    doc.close()
    print(f"  [ThermalParser] Total images saved: {len(result['images'])} ({n_pairs} pairs)")
    return result

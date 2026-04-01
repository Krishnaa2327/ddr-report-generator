"""
main.py
-------
Entry point for the DDR Report Generation Pipeline.

Flow:
  1. Parse Inspection PDF  -> raw text + images
  2. Parse Thermal PDF     -> raw text + images
  3. Extract structured JSON from both (LLM)
  4. Merge both JSONs      -> combined area data (handle conflicts/duplicates)
  5. Reasoning layer       -> root cause, severity, actions (LLM)
  6. Final DDR generation  -> client-ready report (LLM)
  7. Build HTML/PDF output with embedded images
"""

import os
import json
import sys
from dotenv import load_dotenv

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("[ERROR] OPENAI_API_KEY not found in .env file. Please set it and retry.")
    sys.exit(1)

# ── Path configuration ────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR       = os.path.join(BASE_DIR, "input_docs")
OUTPUT_DIR      = os.path.join(BASE_DIR, "outputs")
IMAGE_DIR       = os.path.join(OUTPUT_DIR, "extracted_images")

INSPECTION_PDF  = os.path.join(INPUT_DIR, "Sample_Report.pdf")
THERMAL_PDF     = os.path.join(INPUT_DIR, "Thermal_Images.pdf")

# Create necessary directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR,  exist_ok=True)
os.makedirs(os.path.join(IMAGE_DIR, "inspection"), exist_ok=True)
os.makedirs(os.path.join(IMAGE_DIR, "thermal"),    exist_ok=True)

# ── Pipeline imports ──────────────────────────────────────────────────────────
from parsers.inspection_parser import parse_inspection_pdf
from parsers.thermal_parser    import parse_thermal_pdf
from pipeline.extractor        import extract_inspection_data, extract_thermal_data
from pipeline.merger           import merge_data
from pipeline.reasoner         import generate_reasoning
from pipeline.report_generator import generate_ddr_report
from utils.image_mapper        import map_images_to_areas
from utils.pdf_builder         import build_html_report


# ── Helpers ───────────────────────────────────────────────────────────────────

def save_json(data: dict | list, filename: str) -> None:
    """Save intermediate JSON to outputs/ for debugging."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [saved] {path}")


def load_json(filename: str) -> dict | list:
    """Load intermediate JSON from outputs/."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_input_files() -> bool:
    """Verify both PDFs exist before starting."""
    missing = []
    if not os.path.exists(INSPECTION_PDF):
        missing.append(INSPECTION_PDF)
    if not os.path.exists(THERMAL_PDF):
        missing.append(THERMAL_PDF)
    if missing:
        print("[ERROR] Missing input files:")
        for f in missing:
            print(f"  - {f}")
        print("\nPlease place both PDFs inside the input_docs/ folder and retry.")
        return False
    return True


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline():
    print("=" * 60)
    print("   DDR REPORT GENERATION PIPELINE")
    print("=" * 60)

    # ── Validate inputs ───────────────────────────────────────────
    if not check_input_files():
        sys.exit(1)

    # ────────────────────────────────────────────────────────────
    # STEP 1 : Parse Inspection PDF
    # ────────────────────────────────────────────────────────────
    print("\n[Step 1/7] Parsing Inspection PDF...")
    inspection_raw = parse_inspection_pdf(
        pdf_path  = INSPECTION_PDF,
        image_out = os.path.join(IMAGE_DIR, "inspection")
    )
    save_json(inspection_raw, "step1_inspection_raw.json")
    print(f"  Pages parsed : {inspection_raw['page_count']}")
    print(f"  Images saved : {len(inspection_raw['images'])}")

    # ────────────────────────────────────────────────────────────
    # STEP 2 : Parse Thermal PDF
    # ────────────────────────────────────────────────────────────
    print("\n[Step 2/7] Parsing Thermal PDF...")
    thermal_raw = parse_thermal_pdf(
        pdf_path  = THERMAL_PDF,
        image_out = os.path.join(IMAGE_DIR, "thermal")
    )
    save_json(thermal_raw, "step2_thermal_raw.json")
    print(f"  Pages parsed : {thermal_raw['page_count']}")
    print(f"  Thermal readings found : {len(thermal_raw['readings'])}")

    # ────────────────────────────────────────────────────────────
    # STEP 3 : Extract structured data via LLM
    # ────────────────────────────────────────────────────────────
    print("\n[Step 3/7] Extracting structured observations via LLM...")

    print("  -> Extracting from inspection report...")
    inspection_structured = extract_inspection_data(inspection_raw["full_text"])
    save_json(inspection_structured, "step3a_inspection_structured.json")

    print("  -> Extracting from thermal report...")
    thermal_structured = extract_thermal_data(thermal_raw["full_text"])
    save_json(thermal_structured, "step3b_thermal_structured.json")

    print(f"  Inspection areas found : {len(inspection_structured)}")
    print(f"  Thermal entries found  : {len(thermal_structured)}")

    # ────────────────────────────────────────────────────────────
    # STEP 4 : Merge inspection + thermal data
    # ────────────────────────────────────────────────────────────
    print("\n[Step 4/7] Merging inspection + thermal data...")
    merged_data = merge_data(inspection_structured, thermal_structured)
    save_json(merged_data, "step4_merged_data.json")
    print(f"  Merged areas : {len(merged_data)}")
    conflicts = [a for a in merged_data if a.get("conflict") != "None"]
    print(f"  Conflicts detected : {len(conflicts)}")

    # ────────────────────────────────────────────────────────────
    # STEP 5 : Reasoning — root cause, severity, actions
    # ────────────────────────────────────────────────────────────
    print("\n[Step 5/7] Generating root cause, severity & actions via LLM...")
    reasoned_data = generate_reasoning(merged_data)
    save_json(reasoned_data, "step5_reasoned_data.json")

    # ────────────────────────────────────────────────────────────
    # STEP 6 : Map images to areas
    # ────────────────────────────────────────────────────────────
    print("\n[Step 6/7] Mapping images to report sections...")
    image_map = map_images_to_areas(
        inspection_images = inspection_raw["images"],
        thermal_images    = thermal_raw["images"],
        merged_data       = reasoned_data
    )
    save_json(image_map, "step6_image_map.json")

    # ────────────────────────────────────────────────────────────
    # STEP 7 : Generate final DDR report
    # ────────────────────────────────────────────────────────────
    print("\n[Step 7/7] Generating final DDR report...")

    # Get property-level summary from LLM
    ddr_text = generate_ddr_report(reasoned_data)
    save_json(ddr_text, "step7_ddr_text.json")

    # Build HTML output with images
    output_html = os.path.join(OUTPUT_DIR, "final_ddr_report.html")
    build_html_report(
        ddr_data   = ddr_text,
        image_map  = image_map,
        output_path= output_html
    )

    print("\n" + "=" * 60)
    print("   PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\n  Final report : {output_html}")
    print("\n  Intermediate files saved in outputs/:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith(".json"):
            print(f"    - {f}")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline()
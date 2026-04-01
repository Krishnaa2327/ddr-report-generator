# DDR Report Generator

An automated AI-powered pipeline that ingests building inspection and thermal inspection PDF reports, extracts structured observation data, uses reasoning to determine root causes and severity, and generates a comprehensive, client-ready Due Diligence Report (DDR) in HTML format.

## Table of Contents
- [Overview](#overview)
- [Pipeline Architecture](#pipeline-architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation setup](#installation-setup)
- [Usage](#usage)
- [Output](#output)

## Overview

The DDR Report Generator is designed to automate the process of creating detailed building inspection reports. It intelligently combines visual inspection data with thermal imaging data, maps extracted images to the corresponding areas, and leverages OpenAI's LLMs to infer the severity, root cause, and necessary actions for any flagged issues.

## Pipeline Architecture

The system executes the following 7-step process:

1. **Parse Inspection PDF**: Extracts raw text and high-resolution JPEG inspection photos (filtering out logos and UI elements).
2. **Parse Thermal PDF**: Extracts raw text and pairs of thermal (heat-map) and visual images based on global PDF xref scanning.
3. **Information Extraction (LLM)**: Uses `gpt-4o-mini` to extract structured JSON data (Observation areas, issues, temperatures, etc.) from the raw text.
4. **Merge Data**: Combines inspection and thermal observations into unified area dictionaries, resolving conflicts if any.
5. **Reasoning Engine (LLM)**: Analyzes the merged data to determine the root cause, severity classification, and recommended corrective actions.
6. **Image Mapping**: Correlates the extracted visual and thermal images back to the specific areas mentioned in the report.
7. **Report Generation**: Synthesizes all data and generates a final HTML report (`final_ddr_report.html`) with embedded images and structured summaries.

## Project Structure

```text
ddr-report-generator/
│
├── main.py                     # Entry point for the pipeline execution
├── .env                        # Environment variables (API Keys)
├── requirements.txt            # Python dependencies
│
├── input_docs/                 # Place input PDFs here
│   ├── Sample_Report.pdf
│   └── Thermal_Images.pdf
│
├── parsers/                    # PDF parsing logic
│   ├── inspection_parser.py    # Extracts text and visual photos (JPEG only)
│   └── thermal_parser.py       # Extracts text and thermal/visual image pairs
│
├── pipeline/                   # Core LLM processing logic
│   ├── extractor.py            # Converts raw text to structured JSON via OpenAI
│   ├── merger.py               # Merges thermal and inspection JSONs
│   ├── reasoner.py             # Generates root cause/severity analysis
│   └── report_generator.py     # Drafts the final report text
│
├── utils/                      # Helper modules
│   ├── image_mapper.py         # Maps extracted images to report sections
│   └── pdf_builder.py          # Assembles the final HTML report
│
└── outputs/                    # Output directory (auto-generated)
    ├── extracted_images/       # Contains extracted inspection & thermal images
    ├── final_ddr_report.html   # The final generated DDR Report
    └── step*.json              # Intermediate pipeline data outputs
```

## Prerequisites

- Python 3.8+
- An active OpenAI API account with access to the `gpt-4o-mini` model.

## Installation setup

1. **Clone the repository** (if applicable) and navigate to the project directory:
   ```bash
   cd ddr-report-generator
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure Environment Variables**:
   Create a `.env` file in the root directory and add your OpenAI API key:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

1. **Prepare Input Files**:
   Ensure your input PDF files are placed in the `input_docs/` folder. The pipeline expects the following default filenames:
   - `Sample_Report.pdf` (Visual inspection report)
   - `Thermal_Images.pdf` (Thermal inspection report)

2. **Run the Pipeline**:
   Execute the main script from the root directory:
   ```bash
   python main.py
   ```
   *Note: If you run into issues with old data, you can safely delete the `outputs/` folder before running the script; it will be recreated automatically.*

## Output

Upon successful execution, check the `outputs/` directory. 
- The final report will be available at `outputs/final_ddr_report.html`.
- Extracted images will be neatly organized inside `outputs/extracted_images/`.
- Intermediate processing steps are saved as `stepX_...json` files for easy debugging and auditing.

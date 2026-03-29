# The Redactor

The Redactor is an offline desktop app for finding and redacting sensitive information in PDF and DOCX files.

It is built for a human-in-the-loop workflow:
1. Load a document.
2. Let the local AI detect possible sensitive entities.
3. Review and approve/reject each detected item.
4. Export a redacted copy.
5. Keep an audit trail of what was approved or rejected.

## What This Code Does

The project combines document parsing, local NLP-based entity detection, a review UI, and format-specific redaction:

- GUI app (PyQt6): drag and drop PDF or DOCX, review detections, export redacted file.
- Detection engine (Presidio + spaCy): identifies entities such as person names, locations, organizations, emails, phone numbers, US SSNs, IBANs, and credit cards.
- PDF redaction (PyMuPDF): searches approved strings and applies permanent redaction annotations.
- DOCX redaction (python-docx): replaces approved strings with [REDACTED] in paragraphs and table cells.
- Audit logging: writes review actions to a local JSON audit file.

Main modules:

- main.py: App entry point, UI orchestration, export flow.
- ui_components.py: Drag/drop zone and review list item widgets.
- worker.py: Background thread for parsing + analysis so UI stays responsive.
- document_parsers.py: Text extraction from PDF and DOCX.
- ml_engine.py: Local PII analysis with Presidio and spaCy model.
- redactor.py: Applies approved redactions to PDF or DOCX.
- audit.py: Appends compliance-style audit records.

## Requirements

- Windows (project includes Windows batch scripts and packaging setup).
- Python 3.10+ recommended.
- Internet only needed during setup to install packages and download spaCy model.
- After setup, analysis/redaction runs offline.

Python dependencies are listed in requirements.txt:

- PyQt6
- pyqtdarktheme
- PyMuPDF
- python-docx
- presidio-analyzer
- presidio-anonymizer
- spacy

## Quick Start

There are two ways to run the application on your device. The recommended approach is to download the finalized installation executable, which instantly provides the full experience without requiring any Python coding or environmental setup.

### Option 1: The Fast Way (Installing the `.exe`)
*Recommended for software testers and end users.*

Since the underlying AI models (`spaCy`) are massive, the final application binaries are not stored directly in this repository's source code. Instead, we have bundled the entire Python environment and AI Engine into a single, clean `.exe` installer via PyInstaller and Inno Setup.

1. Navigate to the **Releases** tab on the right side of this GitHub repository page.
2. Download the attached `Redactor_Setup.exe` file.
3. Run the installer. It will neatly extract the offline application and its models to your Program Files (or a folder of your choosing) and place a shortcut on your Desktop.
4. Double-click **The Redactor** on your Desktop to open the application instantly!

### Option 2: The Developer Way (Running from Source Code)
*Recommended for developers who want to modify or review the Python scripts.*

If you want to run the raw `.py` scripts locally using your own Python installation, use the provided batch scripts:

1. Clone or download this repository to your local machine:
   ```cmd
   git clone https://github.com/m-umer-mustafa/redactor.git
   ```
2. Open a terminal in the project folder and choose one setup method below.

#### Method A: One-time setup script (recommended)

1. Open PowerShell or Command Prompt in the project folder.
2. Run:

	setup.bat

This script will:
- Create a virtual environment in venv
- Install requirements
- Download spaCy model en_core_web_lg
- Generate a demo document in demo_data

3. Start the app:

	start.bat

#### Method B: Manual setup

1. Create and activate a virtual environment.
2. Install dependencies:

	pip install -r requirements.txt

3. Download NLP model:

	python -m spacy download en_core_web_lg

4. Run app:

	python main.py

## How To Use The App

1. Launch the app (start.bat or python main.py).
2. Drag and drop a .pdf or .docx file into the drop zone.
3. Wait for extraction and PII analysis to finish.
4. Review detected entities in the right panel:
	- Default state is approved for redaction.
	- Click Reject to exclude an entity from redaction.
	- Click Restore to include it again.
5. Click Apply Redactions & Export Document.
6. Choose output path and save.

Results:
- Redacted output file at your chosen location.
- Audit log updated at audit_data/redaction_audit_log.json.

## Demo Data

To generate a sample legal-style DOCX for testing:

python generate_demo_data.py

Output file:
- demo_data/Confidential_Agreement_Sterling.docx

## Running Tests

There is a basic core test script:

python test_core.py

It creates temporary DOCX test files and checks:
- zero-PII case
- long-document detection case

## Building A Desktop Executable

Build with PyInstaller:

python build.py

Output folder:
- dist/Redactor

Inno Setup script is included for installer packaging:
- installer.iss

## Notes And Limitations

- Text-only processing: scanned/image-only PDFs are not OCR-processed.
- Language/model: configured for English spaCy model en_core_web_lg.
- DOCX replacement is text-based and may affect complex formatting in some documents.
- Detection is probabilistic; always review entities before export.
- Redaction is done by exact matched strings from approved entities.

## Troubleshooting

- If model load fails, run:
  python -m spacy download en_core_web_lg

- If start.bat says virtual environment not found, run setup.bat first.

- If no text is extracted from a file, verify:
  - file is valid PDF/DOCX
  - PDF is not image-only/scanned

## Project Structure

- main.py
- ui_components.py
- worker.py
- document_parsers.py
- ml_engine.py
- redactor.py
- audit.py
- generate_demo_data.py
- test_core.py
- build.py
- setup.bat
- start.bat
- installer.iss

## Features Included in the MVP
* **100% Offline AI**: Uses `spaCy`'s massive transformer architectures and Microsoft's `presidio` framework to scan contextually for Emails, SSNs, IBANs, Locations, Names, and Phone Numbers with no internet connection required.
* **Modern Desktop GUI**: Built using `PyQt6` and customized with modern, dark-glassmorphic `qdarktheme` elements.
* **Interactive Approvals**: Visualizes exactly what the AI found with a review sidebar. Auto-highlights the document text and allows human-in-the-loop overrides before permanently obliterating the sensitive data. 
* **Audit Logging**: Automatically generates an enterprise-grade `audit_data/` ledger keeping track of exactly which entities were approved or rejected by the user.


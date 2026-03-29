# The Redactor

The Redactor is an offline desktop app for finding and redacting sensitive information in PDF and DOCX files.

It is built for a human-in-the-loop workflow:
1. Load one or more documents.
2. Let the local AI detect possible sensitive entities.
3. Review detections with checkbox-based approval and optional manual redaction.
4. Export a redacted copy.
5. Keep an audit trail of what was approved or rejected.

## What This Code Does

The project combines document parsing, local NLP-based entity detection, a review UI, and format-specific redaction:

- GUI app (PyQt6): drag and drop PDF or DOCX, review detections, export redacted file.
- Detection engine (Presidio + spaCy + custom regex recognizers): identifies base entities and stricter business/legal formats.
- Review workflow: checkbox-based entity approval plus manual redaction from selected text in the preview context menu.
- PDF redaction (PyMuPDF): searches approved strings and applies permanent redaction annotations.
- DOCX redaction (python-docx): replaces approved strings with configurable output styles.
- Audit logging: writes review actions to a local JSON audit file.

Main modules:

- main.py: App entry point, UI orchestration, export flow.
- ui_components.py: Drag/drop zone and other reusable UI widgets.
- worker.py: Background workers for parsing + analysis so UI stays responsive.
- document_parsers.py: Text extraction from PDF and DOCX.
- ml_engine.py: Local PII analysis with Presidio, spaCy, and custom recognizers.
- redactor.py: Applies approved redactions to PDF or DOCX.
- audit.py: Appends and manages compliance-style audit records.

## Recent Behavior Updates

- Review page:
  - Entity list is checkbox-driven (checked = redact, unchecked = keep).
  - You can manually add redactions by selecting text in the preview, right-clicking, and choosing "Mark Selected Text for Redaction".
  - Manual additions appear in a dedicated review-list section.

- History page:
  - Uses a dedicated Select checkbox column per row.
  - "Delete Selected" removes only checked entries from `audit_data/redaction_audit_log.json`.
  - "Clear All History" clears only the audit log file.

- Settings page Data Management:
  - "Reset Dashboard Stats" resets only dashboard counters in `config.json`.
  - "Clear All App Data" resets counters in `config.json` and clears `audit_data/redaction_audit_log.json`.
  - Destructive actions use inline confirmation (second click within timeout).

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

There are two ways to run the application on your device. The recommended approach is to download the finalized installation executable, which instantly provides the full experience without requiring any Python coding or environment setup.

### Option 1: The Fast Way (Installing the .exe)
Recommended for software testers and end users.

Since the underlying AI models (spaCy) are large, the final application binaries are not stored directly in this repository's source code. Instead, the app can be bundled into an installer via PyInstaller and Inno Setup.

1. Navigate to the Releases tab on the right side of the GitHub repository page.
2. Download the attached Redactor_Setup.exe file.
3. Run the installer.
4. Launch The Redactor from your desktop shortcut.

### Option 2: The Developer Way (Running from Source Code)
Recommended for developers who want to modify or review the Python scripts.

1. Clone or download this repository to your local machine:

```cmd
git clone https://github.com/m-umer-mustafa/redactor.git
```

2. Open a terminal in the project folder and choose one setup method below.

#### Method A: One-time setup script (recommended)

1. Open PowerShell or Command Prompt in the project folder.
2. Run:

```cmd
setup.bat
```

This script will:
- Create a virtual environment in venv
- Install requirements
- Download spaCy model en_core_web_lg
- Generate a demo document in demo_data

3. Start the app:

```cmd
start.bat
```

#### Method B: Manual setup

1. Create and activate a virtual environment.
2. Install dependencies:

```cmd
pip install -r requirements.txt
```

3. Download NLP model:

```cmd
python -m spacy download en_core_web_lg
```

4. Run app:

```cmd
python main.py
```

## How To Use The App

1. Launch the app (`start.bat` or `python main.py`).
2. Drag and drop one or more `.pdf` or `.docx` files into the drop zone.
3. Wait for extraction and PII analysis to finish.
4. Review detected entities in the right panel:
   - Checked items are approved for redaction.
   - Unchecked items are kept as-is.
   - Optional: select arbitrary text in the preview, right-click, and choose "Mark Selected Text for Redaction".
5. Click `Apply & Save Current` or `Apply All Approved in Batch`.
6. Open exports from your configured output folder.

Results:
- Redacted output files in your configured export directory.
- Audit log updated at `audit_data/redaction_audit_log.json`.

## Demo Data

To generate a sample legal-style DOCX for testing:

```cmd
python generate_demo_data.py
```

Output file:
- demo_data/Confidential_Agreement_Sterling.docx

## Running Tests

There is a basic core test script:

```cmd
python test_core.py
```

It creates temporary DOCX test files and checks:
- zero-PII case
- long-document detection case

## Building A Desktop Executable

Build with PyInstaller:

```cmd
python build.py
```

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
- Manual redaction entries are added as custom entities and flow through the same export pipeline.

## Troubleshooting

- If model load fails, run:

```cmd
python -m spacy download en_core_web_lg
```

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

- 100% offline AI: uses local spaCy + Presidio with custom recognizers for practical legal and enterprise formats.
- Dark-mode desktop GUI: built using PyQt6 and styled with qdarktheme.
- Interactive approvals: checkbox-based review with live highlight updates and manual redaction support.
- History and data controls: checkbox-based history deletion, full history clear, dashboard stat reset, and full app data reset.
- Audit logging: `audit_data/` ledger tracks approved and rejected entities per file.
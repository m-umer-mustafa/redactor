# The Redactor — Sensitive Data Shield

An MVP application designed to securely identify, review, and permanently redact Personally Identifiable Information (PII) from PDFs and Word documents. Powered entirely by localized, offline AI models (`spaCy` and `presidio-analyzer`) to guarantee 100% data privacy. No cloud APIs are used.

---

## 🚀 How to Test the Application

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
2. Run `setup.bat` by double-clicking it. This will automatically:
   - Create an isolated `venv` (Virtual Environment).
   - Install the underlying machine learning dependencies (`PyQt6`, `presidio-analyzer`, `spacy`, etc).
   - Download the massive `en_core_web_lg` offline AI model.
3. Once the setup has successfully finished, run `start.bat` to boot up the application GUI natively!

---

## 🛠 Features Included in the MVP
* **100% Offline AI**: Uses `spaCy`'s massive transformer architectures and Microsoft's `presidio` framework to scan contextually for Emails, SSNs, IBANs, Locations, Names, and Phone Numbers with no internet connection required.
* **Modern Desktop GUI**: Built using `PyQt6` and customized with modern, dark-glassmorphic `qdarktheme` elements.
* **Interactive Approvals**: Visualizes exactly what the AI found with a review sidebar. Auto-highlights the document text and allows human-in-the-loop overrides before permanently obliterating the sensitive data. 
* **Audit Logging**: Automatically generates an enterprise-grade `audit_data/` ledger keeping track of exactly which entities were approved or rejected by the user.

## 🏗 Notice For Compilation (PyInstaller)
This application utilizes highly advanced Windows OS-specific multiprocessing and subprocess patching techniques to seamlessly package `spaCy` NLP pipelines inside frozen executables. If you edit the `main.py` code, ensure you respect the `-m` and `-c` early-exit blocks to prevent recursive threadpool lockups! To rebuild the `.exe` yourself, run `python build.py` followed by the `installer.iss` script in Inno Setup.

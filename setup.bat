@echo off
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
python -m spacy download en_core_web_lg
echo Generating Demo Data...
python generate_demo_data.py
echo Setup complete. Run start.bat to launch the app.

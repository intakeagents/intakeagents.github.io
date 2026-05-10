@echo off
echo Starting Coastal DME Intake Agent Demo...
echo.

REM Install dependencies if needed
pip install -r requirements.txt --quiet

REM Start the server
python demo_server.py

pause

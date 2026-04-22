# Activates venv and starts the API server
# Usage: .\start_api.ps1
# To find your local IP for the mobile app config, run `ipconfig` and look for "IPv4 Address"
& ".\venv\Scripts\Activate.ps1"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

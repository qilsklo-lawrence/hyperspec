#!/bin/bash
set -e

echo "=== Hyperspec Setup & Run Script ==="

# 1. Build frontend if it doesn't exist
if [ ! -d "frontend/dist" ]; then
    echo "[1/3] Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
else
    echo "[1/3] Frontend already built. Skipping..."
fi

# 2. Setup Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "[2/3] Creating Python virtual environment..."
    # Try python3 first, fallback to python
    if command -v python3 &>/dev/null; then
        python3 -m venv venv
    else
        python -m venv venv
    fi
fi

echo "[3/3] Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "==========================================================="
echo "   All set! Starting Hyperspec server on port 8080...      "
echo "   Open http://localhost:8080 in your browser.             "
echo "   Press Ctrl+C to stop the server.                        "
echo "==========================================================="
echo ""

python app.py

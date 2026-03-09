#!/bin/bash
set -e

echo "Upgrading pip..." >&2
pip install --upgrade pip

echo "Installing dependencies from requirements.txt..." >&2
pip install -r /home/site/wwwroot/requirements.txt

echo "Dependencies installed. Launching Streamlit..." >&2
cd /home/site/wwwroot/src/dashboard
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
echo "Streamlit launched successfully." >&2
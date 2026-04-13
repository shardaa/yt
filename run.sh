#!/usr/bin/env bash
set -e

# Detect Python command
if [ -x "/opt/homebrew/bin/python3.12" ]; then
  PY="/opt/homebrew/bin/python3.12"
elif command -v python3 &>/dev/null; then
  PY=python3
elif command -v py &>/dev/null; then
  PY=py
elif command -v python &>/dev/null; then
  PY=python
else
  echo "Error: Python not found. Install Python 3.11+ first."
  exit 1
fi

echo "Using: $PY ($($PY --version 2>&1))"

# Check if venv exists
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  $PY -m venv venv
fi

# Install dependencies
echo "Installing dependencies..."
./venv/bin/pip install --quiet yt-dlp click flask

# Start the web server
echo "Starting YouTube Downloader at http://localhost:9090"
./venv/bin/python -m youtube_downloader.cli web --port 9090

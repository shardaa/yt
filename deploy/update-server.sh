#!/usr/bin/env bash
# ============================================================
# Pull latest code and restart the service
# Run this whenever you push new changes:
#   bash update-server.sh
# ============================================================
set -e

cd ~/youtube-downloader
git pull
source venv/bin/activate
pip install --quiet --upgrade yt-dlp click flask gunicorn

sudo systemctl restart ytdownloader
echo "Updated and restarted. Check: sudo systemctl status ytdownloader"

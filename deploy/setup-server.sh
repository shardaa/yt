#!/usr/bin/env bash
# ============================================================
# Oracle Cloud / Ubuntu VM — one-time server setup
# Run this ONCE after SSH-ing into your new VM:
#   bash setup-server.sh
# ============================================================
set -e

echo "=== Updating system ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing Python 3, pip, ffmpeg, git ==="
sudo apt install -y python3 python3-pip python3-venv ffmpeg git

echo "=== Cloning project ==="
cd ~
if [ -d "youtube-downloader" ]; then
  echo "Project directory already exists, pulling latest..."
  cd youtube-downloader && git pull
else
  echo "Enter your git repo URL (e.g. https://github.com/you/youtube-downloader.git):"
  read -r REPO_URL
  git clone "$REPO_URL" youtube-downloader
  cd youtube-downloader
fi

echo "=== Creating virtual environment ==="
python3 -m venv venv
source venv/bin/activate

echo "=== Installing dependencies ==="
pip install --upgrade pip
pip install yt-dlp click flask gunicorn

echo "=== Creating downloads directory ==="
mkdir -p ~/downloads

echo "=== Setting up systemd service ==="
sudo tee /etc/systemd/system/ytdownloader.service > /dev/null <<EOF
[Unit]
Description=YouTube Downloader Web App
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/youtube-downloader
ExecStart=$HOME/youtube-downloader/venv/bin/gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --timeout 600 \
  --access-logfile - \
  "youtube_downloader.web_app:create_app('$HOME/downloads')"
Restart=always
RestartSec=5
Environment=PATH=$HOME/youtube-downloader/venv/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ytdownloader
sudo systemctl start ytdownloader

echo "=== Opening firewall port 5000 ==="
# iptables rule for Oracle Cloud (their firewall blocks by default)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  App running at: http://$(curl -s ifconfig.me):5000"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status ytdownloader"
echo "    sudo systemctl restart ytdownloader"
echo "    sudo journalctl -u ytdownloader -f"
echo "============================================"

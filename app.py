"""Entry point for production deployment (Railway, Render, etc.)."""
import os
from youtube_downloader.web_app import create_app

app = create_app(output_dir=os.environ.get("DOWNLOAD_DIR", "./downloads"))

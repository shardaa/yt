"""Entry point for production deployment (Railway, Render, etc.)."""
import os
from youtube_downloader.web_app import create_app

app = create_app(output_dir=os.environ.get("DOWNLOAD_DIR", "./downloads"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

from __future__ import annotations

import os

from app_logging.logger import logger
from config.config import MediaSettings


def get_latest_audio_file(topic: str, media_settings: MediaSettings) -> str | None:
    """
    Find the latest audio file for a given topic in the news output directory.
    - Scans the directory for files matching `f"{topic}_*.mp3"`.
    - Sorts them by modification time and returns the newest one.
    """
    if topic == "AMA":
        news_dir = media_settings.voice_output_dir
    else:
        news_dir = media_settings.voice_output_dir

    try:
        files = [
            f
            for f in os.listdir(news_dir)
            if f.startswith(f"{topic}_") and f.endswith(".mp3")
        ]
        if not files:
            return None

        latest_file = max(
            files, key=lambda f: os.path.getmtime(os.path.join(news_dir, f))
        )
        return os.path.join(news_dir, latest_file)
    except FileNotFoundError:
        logger.warning(f"News directory not found: {news_dir}")
        return None

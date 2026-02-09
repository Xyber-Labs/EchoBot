"""
This service is used for loading songs from soundcloud and loading videos from the googledrive
"""

from app_logging.logger import logger
from config.config import Settings, to_system_path
import os
import schedule
from services.music_service.media.load_songs_soundcloud import Soundcloud
from video.video_load import main as load_videos_from_google_drive
import time
import sys
from pathlib import Path


class MediaInitializationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def check_if_media_repo_is_empty(self):
        return

    def create_media_repo(self):
        """Create all necessary media directories if they don't exist."""
        logger.info("Ensuring all media directories exist...")
        dirs_to_create = [
            self.settings.media.voice_output_dir,
            self.settings.media.news_output_dir,
            self.settings.media.state_output_dir,
            self.settings.media.memory_output_dir,
            self.settings.media.videos_output_dir,
            self.settings.media.google_drive_music_dir,
            self.settings.media.suno_output_dir,
            self.settings.media.soundcloud_output_dir,
            self.settings.media.config_dir,
        ]
        for dir_path in dirs_to_create:
            try:
                # When creating directories for the application, we should always use the container path.
                # The volume mount will map this to the host directory.
                # to_system_path should be used for external tools on the host (e.g., OBS).
                system_path = to_system_path(self.settings, str(dir_path))
                Path(system_path).mkdir(parents=True, exist_ok=True)
                logger.debug(f"Directory ensured: {system_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")
        logger.info("Media directories check complete.")

    def check_if_music_repo_is_empty(self):
        logger.info("Checking if music repo is empty")
        music_dir = to_system_path(
            self.settings, str(self.settings.media.soundcloud_output_dir)
        )
        if not os.path.exists(music_dir) or not os.listdir(music_dir):
            logger.info("Soundcloud repo is empty or does not exist.")
            return True
        logger.info("Soundcloud repo is not empty.")
        return False

    def check_if_videos_repo_is_empty(self):
        logger.info("Checking if videos repo is empty")
        video_dir = to_system_path(
            self.settings, str(self.settings.media.videos_output_dir)
        )
        if not os.path.exists(video_dir) or not os.listdir(video_dir):
            logger.info("Videos repo is empty or does not exist.")
            return True
        logger.info("Videos repo is not empty.")
        return False

    def load_songs_from_soundcloud(self):
        logger.info("Loading songs from soundcloud")
        try:
            soundcloud_downloader = Soundcloud(self.settings)
            soundcloud_downloader.download_songs()
        except Exception as e:
            logger.warning(f"Error loading songs from soundcloud: {e}")
            logger.warning("Skipping SoundCloud initialization - not configured. You can add local music files to app/media/music/ instead.")

    def load_videos_from_googledrive(self):
        logger.info("Loading videos from googledrive")
        try:
            load_videos_from_google_drive()
        except Exception as e:
            logger.warning(f"Error loading videos from googledrive: {e}")
            logger.warning("Skipping Google Drive initialization - not configured. You can add local video files to app/media/videos/ instead.")

    def set_schedule_for_soundcloud_downloader(self):
        logger.info("Setting schedule for soundcloud downloader")
        schedule.every(self.settings.schedule.SOUNDCLOUD_DOWNLOADER_INTERVAL).hours.do(
            self.load_songs_from_soundcloud
        )

    def initialize_media(self):
        """Initialize media files (videos and music). Checks for missing files and downloads them."""
        # Ensure all directories are created before proceeding
        self.create_media_repo()

        # Always check for missing videos (video_load.py handles comparison internally)
        logger.info("Checking for missing videos from Google Drive...")
        self.load_videos_from_googledrive()

        # Check for music (only download if repo is empty)
        if self.check_if_music_repo_is_empty():
            logger.info("Music repo is empty, loading songs from SoundCloud.")
            self.load_songs_from_soundcloud()
        else:
            logger.info("Music repo is not empty, skipping initial song download.")

    def setup_scheduling(self):
        """Set up scheduling for periodic music downloads."""
        self.set_schedule_for_soundcloud_downloader()
        logger.info("Media initialization service scheduling configured.")

    def run(self):
        """Run the service to load songs from soundcloud and set up scheduling"""
        self.initialize_media()
        self.setup_scheduling()

        # Keep the script running to execute scheduled tasks
        logger.info("Starting scheduled task runner...")
        while True:
            schedule.run_pending()
            time.sleep(1)


def run_media_initialization_service():
    """Run as standalone service with continuous scheduling."""
    media_initialization_service = MediaInitializationService(Settings())
    media_initialization_service.run()


def initialize_media_once():
    """Initialize media once and set up scheduling (for integration with main app)."""
    media_initialization_service = MediaInitializationService(Settings())
    media_initialization_service.initialize_media()
    media_initialization_service.setup_scheduling()
    return media_initialization_service


if __name__ == "__main__":
    run_media_initialization_service()

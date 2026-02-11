"""
Media Directory Manager for EchoBot

Handles startup validation and auto-creation of media directories
based on configuration settings.
"""

import os
from typing import Dict, List, Tuple

from app_logging.logger import logger
from config.config import settings


class MediaDirectoryManager:
    """
    Manages media directories, ensuring they exist and are writable.
    Automatically creates missing directories based on configuration.
    """

    def __init__(self) -> None:
        self.media_dirs: Dict[str, str] = {}
        self.is_docker = self._detect_docker_environment()
        self._load_media_directories()

    def _detect_docker_environment(self) -> bool:
        """Detect if we're running in a Docker container."""
        return os.path.exists("/.dockerenv")

    def _load_media_directories(self) -> None:
        """Load media directory paths from configuration, adapting to environment."""
        if self.is_docker:
            # In Docker: use container paths
            logger.info("Running in Docker container - using container paths")
            self.media_dirs = {
                "news": str(settings.media.news_output_dir),
                "voice": str(settings.media.voice_output_dir),
                "music_soundcloud": str(settings.media.soundcloud_output_dir),
                "music_google_drive": str(settings.media.google_drive_music_dir),
                "state": str(settings.media.state_output_dir),
                "memory": str(settings.media.memory_output_dir),
                "videos": str(settings.media.videos_output_dir),
            }
        else:
            # Local development: use host paths
            logger.info("Running locally - using host paths")
            if not settings.MEDIA_HOST_DIR:
                logger.warning(
                    "MEDIA_HOST_DIR not configured, falling back to container paths"
                )
                self.media_dirs = {
                    "news": str(settings.media.news_output_dir),
                    "voice": str(settings.media.voice_output_dir),
                    "music_soundcloud": str(settings.media.soundcloud_output_dir),
                    "music_google_drive": str(settings.media.google_drive_music_dir),
                    "state": str(settings.media.state_output_dir),
                    "memory": str(settings.media.memory_output_dir),
                    "videos": str(settings.media.videos_output_dir),
                }
            else:
                # Convert container paths to host paths
                self.media_dirs = {
                    "news": os.path.join(settings.MEDIA_HOST_DIR, "news"),
                    "voice": os.path.join(
                        settings.MEDIA_HOST_DIR, "voice", "generated_audio"
                    ),
                    "music_soundcloud": os.path.join(
                        settings.MEDIA_HOST_DIR, "music", "soundcloud_songs"
                    ),
                    "music_google_drive": os.path.join(
                        settings.MEDIA_HOST_DIR, "music", "google_drive_songs"
                    ),
                    "state": os.path.join(settings.MEDIA_HOST_DIR, "state"),
                    "memory": os.path.join(settings.MEDIA_HOST_DIR, "memory"),
                    "videos": os.path.join(settings.MEDIA_HOST_DIR, "videos"),
                }

        logger.info("Loaded media directory configuration:")
        for name, path in self.media_dirs.items():
            logger.info(f"  {name}: {path}")

    def validate_and_create_directories(self) -> Tuple[bool, List[str]]:
        """
        Validate that all media directories exist and are writable.
        Creates missing directories automatically.

        Returns:
            Tuple of (success, list of created directories)
        """
        created_dirs = []
        errors = []

        logger.info("Validating media directory structure...")

        for dir_name, dir_path in self.media_dirs.items():
            try:
                # Ensure directory exists
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    created_dirs.append(dir_path)
                    logger.info(f"Created missing directory: {dir_path}")

                # Check if directory is writable
                if not os.access(dir_path, os.W_OK):
                    error_msg = f"Directory not writable: {dir_path}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue

                # Check if it's actually a directory
                if not os.path.isdir(dir_path):
                    error_msg = f"Path exists but is not a directory: {dir_path}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue

                logger.info(f"✓ {dir_name}: {dir_path}")

            except Exception as e:
                error_msg = f"Failed to validate/create directory {dir_path}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        # Validate mount status if we're in Docker
        if self.is_docker:
            mount_status = self._validate_mount_status()
            if not mount_status:
                errors.append("Media volume mount may not be working correctly")

        success = len(errors) == 0

        if success:
            logger.info("All media directories validated successfully")
        else:
            logger.error(
                f"❌ Media directory validation failed with {len(errors)} errors"
            )
            for error in errors:
                logger.error(f"  - {error}")

        return success, created_dirs

    def _validate_mount_status(self) -> bool:
        """
        Validate that the Docker volume mount is working correctly.
        Checks if we can see files from the host side.
        """
        try:
            # Check if the media directory exists and has expected structure
            media_root = settings.media.MEDIA_CONTAINER_DIR
            if not os.path.exists(media_root):
                logger.warning(f"Media root directory not found: {media_root}")
                return False

            # Try to create a test file to verify write access
            test_file = os.path.join(media_root, ".mount_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                logger.info("Media volume mount is working (write test passed)")
                return True
            except Exception as e:
                logger.warning(f"Media volume mount may have issues: {e}")
                return False

        except Exception as e:
            logger.warning(f"Could not validate mount status: {e}")
            return True  # Assume it's working if we can't check

    def get_directory_info(self) -> Dict[str, Dict[str, object]]:
        """
        Get detailed information about all media directories.

        Returns:
            Dictionary with directory information
        """
        info: Dict[str, Dict[str, object]] = {}

        for dir_name, dir_path in self.media_dirs.items():
            exists = os.path.exists(dir_path)
            writable = os.access(dir_path, os.W_OK) if exists else False
            is_dir = os.path.isdir(dir_path) if exists else False

            info[dir_name] = {
                "path": dir_path,
                "exists": exists,
                "writable": writable,
                "is_directory": is_dir,
                "status": "✓" if (exists and writable and is_dir) else "❌",
            }

        return info

    def print_directory_status(self) -> None:
        """Print a formatted status report of all media directories."""
        info = self.get_directory_info()

        env_info = "Docker Container" if self.is_docker else "Local Development"
        logger.info(f"Media Directory Status Report ({env_info}):")
        logger.info("=" * 60)

        for dir_name, details in info.items():
            status = details["status"]
            path = details["path"]
            exists = "EXISTS" if details["exists"] else "MISSING"
            writable = "WRITABLE" if details["writable"] else "NOT_WRITABLE"
            is_dir = "DIR" if details["is_directory"] else "NOT_DIR"

            logger.info(f"{status} {dir_name:20} | {path}")
            logger.info(f"     {'':20} | {exists} | {writable} | {is_dir}")

        logger.info("=" * 60)


def ensure_media_directories() -> bool:
    """
    Convenience function to ensure all media directories exist.

    Returns:
        True if all directories are valid, False otherwise
    """
    manager = MediaDirectoryManager()
    success, created = manager.validate_and_create_directories()

    if created:
        logger.info(f"Created {len(created)} missing directories")

    return success


def print_media_status() -> None:
    """Print a formatted status report of all media directories."""
    manager = MediaDirectoryManager()
    manager.print_directory_status()

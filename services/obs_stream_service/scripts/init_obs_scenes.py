import logging
import os

# Explicitly load .env from the project root before any other imports
try:
    from dotenv import load_dotenv

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        # Using print here for immediate feedback before logging is configured
        print(f"INFO: Successfully loaded .env file from {dotenv_path}")
    else:
        print(f"WARNING: .env file not found at {dotenv_path}")
except ImportError:
    print("WARNING: python-dotenv not installed, .env file will not be loaded.")


from services.obs_stream_service.obs import (
    create_or_update_audio_source,
    create_or_update_video_source_centered,
    create_scene,
    scene_exists,
    init_background_music,
)
from services.obs_stream_service.services.schedule_service import ScheduleService
from config.config import settings


def setup_obs_environment():
    """
    Automatically creates all scenes and default sources in OBS so that the
    live setup exactly matches the schedule.json file.
    """
    logging.info("=== OBS auto‑setup started ===")

    # Get MEDIA_HOST_DIR from settings
    media_root = settings.media.media_root_dir
    logging.info(f"Using media root directory: {media_root}")

    schedule_service = ScheduleService()
    schedule = schedule_service.load()
    if not schedule:
        logging.error("Could not load schedule.json. Aborting setup.")
        return

    available_scenes = schedule.get("_available_scenes", {})
    bg_music_config = schedule.get("background_music", {})

    all_scene_names = [
        scene["scene_name"]
        for scene in available_scenes.values()
        if isinstance(scene, dict)
    ]
    if bg_music_config.get("enabled"):
        all_scene_names.append("Background-Music")

    for scene_name in set(all_scene_names):
        if not scene_exists(scene_name):
            create_scene(scene_name)

    for scene_name, scene_data in available_scenes.items():
        if scene_name.startswith("_"):
            continue

        # Resolve video path relative to media_root
        video_path = scene_data.get("video_path")
        if video_path:
            full_video_path = os.path.join(media_root, video_path)
            if os.path.exists(full_video_path):
                create_or_update_video_source_centered(
                    scene_name=scene_data["scene_name"],
                    source_name=scene_data["video_source_name"],
                    file_path=full_video_path,
                    loop_video=scene_data["loop_video"],
                )
            else:
                logging.warning(f"Video file not found: {full_video_path}")

        # Resolve audio path relative to media_root
        audio_path = scene_data.get("audio_path")
        if audio_path:
            full_audio_path = os.path.join(media_root, audio_path)
            if os.path.exists(full_audio_path):
                create_or_update_audio_source(
                    scene_name=scene_data["scene_name"],
                    source_name=scene_data["audio_source_name"],
                    file_path=full_audio_path,
                )
            else:
                logging.warning(f"Audio file not found: {full_audio_path}")

    # Resolve background music path relative to media_root
    if bg_music_config.get("enabled"):
        bg_music_path = bg_music_config.get("file_path")
        if bg_music_path:
            full_bg_music_path = os.path.join(media_root, bg_music_path)
            if os.path.exists(full_bg_music_path):
                logging.info(f"Setting up background music with: {full_bg_music_path}")
                init_background_music(music_file_path=full_bg_music_path)
            else:
                logging.warning(
                    f"Background music is enabled, but file not found: {full_bg_music_path}"
                )

    logging.info("✓ OBS auto‑setup finished")


if __name__ == "__main__":
    setup_obs_environment()

import logging
import os
import sys
import time

# Load environment variables from .env file
from dotenv import load_dotenv
from pydub import AudioSegment

from app_logging.logger import logger
from config.config import (BACKGROUND_MUSIC_VOLUME_DUCKED,
                           BACKGROUND_MUSIC_VOLUME_NORMAL, settings)
from services.obs_stream_service.obs.ClientManager import OBSClientManager

load_dotenv()

# --- Configuration ---
# Correctly add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

# Names of scenes and sources in OBS
SCENE_MUSIC = "Scene-Music"
SCENE_VOICE = "util-background-voice"
SCENE_NEWS = "Scene-News"
SCENE_READING = "Scene-Reading"
SCENE_TALKING = "Scene-Talking"
SCENE_GREETING = "Scene-Greeting"
# Dedicated scene for background music
SCENE_BACKGROUND_MUSIC = "Background-Music"
AUDIO_SOURCE_FOR_NEWS = "Generated_Audio_Source"
VIDEO_SOURCE_FOR_NEWS = "Generated_Video_Source"
VIDEO_SOURCE_FOR_MUSIC = "Music_Video_Source"

# Background music source (always playing in its own scene)
BACKGROUND_MUSIC_SOURCE = "Media Playlist Source"
VOICE_MUSIC_SOURCE = "Voice_Music_Source"

# Video size and scaling configuration
VIDEO_SCALE_X = 1.0  # Horizontal scale (1.0 = 100%, 0.5 = 50%, 1.5 = 150%)
VIDEO_SCALE_Y = 1.0  # Vertical scale (1.0 = 100%, 0.5 = 50%, 1.5 = 150%)
# Alternative: Use specific dimensions (set to None to use scaling instead)
VIDEO_WIDTH = None  # Width in pixels (e.g., 1280 for 720p width)
VIDEO_HEIGHT = None  # Height in pixels (e.g., 720 for 720p height)

# Scene transition duration
TRANSITION_DURATION_MS = 500  # Duration for scene fades in milliseconds

# File paths
GENERATED_AUDIO_PATH = os.path.join(os.getcwd(), "generated_news.mp3")
GENERATED_VIDEO_PATH = os.path.join(os.getcwd(), "generated_news.mp4")
MUSIC_VIDEO_PATH = os.path.join(os.getcwd(), "music_visuals.mp4")

# Audio monitoring constants
MONITOR_OFF = "OBS_MONITORING_TYPE_NONE"
MONITOR_ONLY = "OBS_MONITORING_TYPE_MONITOR_ONLY"
MONITOR_AND_OUTPUT = "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT"

# --- Logging Setup ---
logger.info("OBS client manager initialized")


# Singleton instance of the OBS client manager
# TODO: this should be done at the orchestrator level I guess here -> radio/core/flow.py
obs_client_manager = OBSClientManager(
    settings.obs
)  # TODO: this should not be initialised here


def source_exists(scene_name: str, source_name: str) -> bool:
    try:
        cl = obs_client_manager.get_client()
        inputs = cl.get_input_list().inputs  # type:ignore
        for input in inputs:
            if input["inputName"] == source_name:
                # To ensure it's in the specific scene, we might need additional checks
                # For simplicity, assume sources are unique or scene-specific
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to check if source exists: {e}")
        return False


def scene_exists(scene_name: str) -> bool:
    """
    Checks if a scene exists in OBS.

    Args:
        scene_name (str): Name of the scene to check

    Returns:
        bool: True if scene exists, False otherwise

    """
    try:
        cl = obs_client_manager.get_client()
        scenes = cl.get_scene_list().scenes  # type:ignore
        for scene in scenes:
            if scene["sceneName"] == scene_name:
                return True
        return False
    except Exception as e:
        logging.error(f"Failed to check if scene exists: {e}")
        return False


def get_canvas_size() -> tuple[int, int]:
    """
    Gets the canvas size from OBS video settings.

    Returns:
        tuple: (width, height) of the canvas

    """
    try:
        cl = obs_client_manager.get_client()
        response = cl.get_video_settings()
        if hasattr(response, "base_width") and hasattr(response, "base_height"):
            width = response.base_width  # type:ignore
            height = response.base_height  # type:ignore
            return width, height
        logging.error("Could not retrieve canvas size from OBS.")
        return 1920, 1080  # Default fallback
    except Exception as e:
        logging.error(f"Failed to get canvas size: {e}")
        return 1920, 1080  # Default fallback


def create_scene(scene_name: str) -> bool:
    """
    Creates a new scene in OBS.

    Args:
        scene_name (str): Name of the scene to create

    Returns:
        bool: True if successful, False otherwise

    """
    try:
        cl = obs_client_manager.get_client()
        cl.create_scene(scene_name)
        logging.info(f"✓ Created scene: {scene_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to create scene '{scene_name}': {e}")
        return False


def create_or_update_video_source(
    scene_name: str,
    source_name: str,
    file_path: str,
    loop_video: bool = True,
    close_when_inactive: bool = False,
    width: int | None = None,
    height: int | None = None,
    x_pos: int = 0,
    y_pos: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    center: bool = False,
    mute_audio: bool = False,
) -> None:
    """
    Creates or updates a video source with specified file and transform properties.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the video source
        file_path (str): Path to the video file
        loop_video (bool): Whether to loop the video
        close_when_inactive (bool): Whether to close file when inactive
        width (int): Width in pixels (None to use original)
        height (int): Height in pixels (None to use original)
        x_pos (int): X position in pixels (ignored if center=True)
        y_pos (int): Y position in pixels (ignored if center=True)
        scale_x (float): Horizontal scale factor (1.0 = 100%)
        scale_y (float): Vertical scale factor (1.0 = 100%)
        center (bool): Whether to center the source on the canvas
        mute_audio (bool): Whether to mute the audio of the video source

    """
    try:
        cl = obs_client_manager.get_client()
        if not source_exists(scene_name, source_name):
            logging.info(
                f"Creating new video source '{source_name}' in scene '{scene_name}'"
            )
            cl.create_input(
                scene_name,
                source_name,
                "ffmpeg_source",  # Media Source kind
                {},  # Initial settings can be empty
                True,  # Enabled
            )

        # Now update the settings
        logging.info(f"Updating video source '{source_name}' with file: {file_path}")
        settings = {
            "local_file": os.path.abspath(file_path),
            "looping": loop_video,
            "close_when_inactive": close_when_inactive,
        }
        cl.set_input_settings(source_name, settings, True)

        # Mute audio if requested, otherwise ensure it's unmuted
        cl.set_input_mute(source_name, mute_audio)
        if mute_audio:
            logging.info(f"Muting audio for video source '{source_name}'")
        else:
            logging.info(
                f"Ensuring audio is not muted for video source '{source_name}'"
            )

        # Set transform properties (size, position, scale) with centering option
        set_source_transform(
            scene_name,
            source_name,
            width,
            height,
            x_pos,
            y_pos,
            scale_x,
            scale_y,
            center,
        )

    except Exception as e:
        logging.error(f"Failed to create or update video source: {e}")


def create_or_update_audio_source_v2(
    scene_name: str,
    source_name: str,
    file_path: str,
    *,
    loop_audio: bool = True,
    close_when_inactive: bool = False,
    monitor_type: int = MONITOR_AND_OUTPUT,  # TODO: replace with enum
    volume: float = 1.0,
    should_restart: bool = True,
) -> bool:
    """
    Creates or updates an audio source in the specified OBS scene.

    Args:
      scene_name: name of the scene to which the source will be attached.
      source_name: unique name for the source.
      file_path: path to the audio file.
      loop_audio: whether the audio should loop.
      close_when_inactive: whether to close the file when the source is inactive.
      monitor_type: monitoring mode (None, output only, or input+output).
      volume: volume of the source (0.0–1.0).
      should_restart: True — restarts the sound immediately.

    Returns:
      True on success, False otherwise.

    """
    try:
        cl = obs_client_manager.get_client()

        if not source_exists(scene_name, source_name):
            logging.info(f"Creating audio source {source_name} in scene {scene_name}")
            cl.create_input(scene_name, source_name, "ffmpeg_source", {}, True)

        settings = {
            "local_file": os.path.abspath(file_path),
            "looping": loop_audio,
            "close_when_inactive": close_when_inactive,
        }
        cl.set_input_settings(source_name, settings, True)

        cl.set_input_audio_monitor_type(source_name, monitor_type)
        cl.set_input_volume(source_name, volume)
        logging.info(
            f"Audio source {source_name} updated in scene {scene_name}: "
            f"loop={loop_audio}, monitor_type={monitor_type}, volume={volume:.0%}"
        )

        if should_restart:
            restart_media_source(source_name)

        return True
    except Exception as e:
        logging.error(f"Failed to create or update audio source {source_name}: {e}")
        return False


def create_or_update_audio_source(
    scene_name: str,
    source_name: str,
    file_path: str,
    monitor_type: int = MONITOR_AND_OUTPUT,
    looping: bool = False,
    close_when_inactive: bool = True,
    volume: float = 1.0,
) -> None:
    """
    Creates or updates an audio source with a specified file or folder (for playlists).
    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the audio source
        file_path (str): Path to the audio file OR a folder for playlist playback
        monitor_type (int): OBS monitoring type (0=off, 1=monitor, 2=monitor&output)
        looping (bool): Whether the audio should loop
        close_when_inactive (bool): Whether to close file when inactive
        volume (float): The volume for the source (0.0 to 1.0)
    """
    try:
        cl = obs_client_manager.get_client()
        is_playlist = os.path.isdir(file_path)
        input_kind = "media_playlist_source" if is_playlist else "ffmpeg_source"
        if not source_exists(scene_name, source_name):
            logging.info(
                f"Creating new audio source '{source_name}' ({input_kind}) in scene '{scene_name}'"
            )
            cl.create_input(
                scene_name,
                source_name,
                input_kind,
                {},
                True,
            )

        logging.info(f"Updating audio source '{source_name}' with path: {file_path}")

        if is_playlist:
            settings = {
                "is_local_file": False,
                "playlist": [
                    {"value": os.path.abspath(os.path.join(file_path, f))}
                    for f in sorted(os.listdir(file_path))
                    if f.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"))
                ],
                "shuffle": True,
                "loop": looping,
                "close_when_inactive": close_when_inactive,
            }
            logging.info(f"Configured as playlist source from directory: {file_path}")
        else:
            settings = {
                "local_file": os.path.abspath(file_path),
                "is_local_file": True,
                "looping": looping,
                "close_when_inactive": close_when_inactive,
            }
            logging.info(f"Configured as single file source: {file_path}")

        cl.set_input_settings(source_name, settings, True)

        # Set audio monitoring and volume
        cl.set_input_audio_monitor_type(source_name, monitor_type)
        cl.set_input_volume(source_name, volume)
        logging.info(f"Set volume for '{source_name}' to {volume:.0%}")

    except Exception as e:
        logging.error(f"Failed to create or update audio source: {e}")


def set_source_transform(
    scene_name: str,
    source_name: str,
    width: int | None = None,
    height: int | None = None,
    x_pos: int = 0,
    y_pos: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    center: bool = False,
) -> None:
    """
    Sets the transform properties (position, size, scale) of a source in a scene.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the source
        width (int): Width in pixels (None to keep current)
        height (int): Height in pixels (None to keep current)
        x_pos (int): X position in pixels (ignored if center=True)
        y_pos (int): Y position in pixels (ignored if center=True)
        scale_x (float): Horizontal scale factor
        scale_y (float): Vertical scale factor
        center (bool): Whether to center the source on the canvas

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Setting transform for '{source_name}' in scene '{scene_name}'")

        # Get the scene item ID for this source
        scene_item_id = cl.get_scene_item_id(scene_name, source_name)
        if not scene_item_id or not hasattr(scene_item_id, "scene_item_id"):
            logging.error(
                f"Could not find scene item ID for '{source_name}' in '{scene_name}'"
            )
            return

        item_id = scene_item_id.scene_item_id  # type:ignore

        if center:
            # Use OBS's built-in centering with bounds
            canvas_width, canvas_height = get_canvas_size()
            logging.info(
                f"Centering '{source_name}' on {canvas_width}x{canvas_height} canvas"
            )

            transform = {
                "positionX": float(canvas_width / 2),  # Center X
                "positionY": float(canvas_height / 2),  # Center Y
                "scaleX": float(scale_x),
                "scaleY": float(scale_y),
                "rotation": 0.0,
                "boundsType": "OBS_BOUNDS_NONE",
                "alignment": 0,  # OBS_ALIGN_CENTER (0 = perfect center)
            }
        else:
            # Build transform settings with manual positioning
            transform = {
                "positionX": float(x_pos),
                "positionY": float(y_pos),
                "scaleX": float(scale_x),
                "scaleY": float(scale_y),
                "rotation": 0.0,
                "boundsType": "OBS_BOUNDS_NONE",
                "alignment": 5,  # OBS_ALIGN_TOP | OBS_ALIGN_LEFT
            }

        # If specific width/height are provided, we need to get source dimensions first
        if width is not None or height is not None:
            try:
                # Get current transform to get source dimensions
                current_transform = cl.get_scene_item_transform(scene_name, item_id)
                if hasattr(current_transform, "scene_item_transform"):
                    source_width = current_transform.scene_item_transform.get(
                        "sourceWidth", 1920
                    )  # type:ignore
                    source_height = current_transform.scene_item_transform.get(
                        "sourceHeight", 1080
                    )  # type:ignore

                    if width is not None and source_width > 0:
                        transform["scaleX"] = float(width) / float(source_width)
                    if height is not None and source_height > 0:
                        transform["scaleY"] = float(height) / float(source_height)
            except Exception as e:
                logging.warning(
                    f"Could not get source dimensions, using provided scale values: {e}"
                )

        # Apply the transform using the scene item ID
        cl.set_scene_item_transform(scene_name, item_id, transform)

        if center:
            logging.info(
                f"Successfully centered '{source_name}' - Position: (Center), Scale: ({scale_x}, {scale_y})"
            )
        else:
            logging.info(
                f"Successfully set transform for '{source_name}' - Position: ({x_pos}, {y_pos}), Scale: ({scale_x}, {scale_y})"
            )

    except Exception as e:
        logging.error(f"Failed to set source transform: {e}")


# --- Core Control Functions ---


def set_scene_transition(
    transition_type: str = "fade_transition", duration_ms: int = 1000
) -> None:
    """
    Sets the scene transition type and duration in OBS.

    Args:
        transition_type (str): Type of transition (fade_transition, cut_transition, slide_transition, etc.)
        duration_ms (int): Duration of transition in milliseconds

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Setting scene transition: {transition_type} ({duration_ms}ms)")
        cl.set_current_scene_transition(transition_type)
        cl.set_current_scene_transition_duration(duration_ms)
    except Exception as e:
        logging.error(f"Failed to set scene transition: {e}")


def switch_to_scene(scene_name: str) -> None:
    """Tells OBS to switch to a specific scene."""
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Switching to scene: {scene_name}")
        cl.set_current_program_scene(scene_name)
    except Exception as e:
        logging.error(f"Failed to switch scene: {e}")


def switch_to_scene_smooth(
    scene_name: str, transition_type: str = "Fade", duration_ms: int = 1000
) -> None:
    """
    Switches to a scene with a smooth transition.

    Args:
        scene_name (str): Name of the scene to switch to
        transition_type (str): Type of transition (Fade, Cut, etc.)
        duration_ms (int): Duration of transition in milliseconds

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(
            f"Smooth transition to scene: {scene_name} using {transition_type} ({duration_ms}ms)"
        )

        # Try common OBS transition names
        common_names = ["Fade", "Cut", "fade_transition", "cut_transition", "Slide"]
        actual_transition = transition_type

        # If the requested transition doesn't work, try alternatives
        for name in [transition_type] + common_names:
            try:
                cl.set_current_scene_transition(name)
                actual_transition = name
                logging.info(f"Using transition: {actual_transition}")
                break
            except BaseException:
                continue

        # Set duration if transition was set successfully
        try:
            cl.set_current_scene_transition_duration(duration_ms)
        except BaseException:
            logging.warning(f"Could not set transition duration to {duration_ms}ms")

        # Perform the scene switch
        cl.set_current_program_scene(scene_name)

        # Wait for transition to complete
        time.sleep(duration_ms / 1000.0)

    except Exception as e:
        logging.error(f"Failed to switch scene with transition: {e}")
        # Fallback to regular scene switch
        try:
            cl = obs_client_manager.get_client()
            logging.info(f"Falling back to direct scene switch: {scene_name}")
            cl.set_current_program_scene(scene_name)
        except Exception as fallback_error:
            logging.error(f"Fallback scene switch also failed: {fallback_error}")


def update_audio_source_file(source_name: str, file_path: str) -> None:
    """
    Dynamically changes the file used by a Media Source in OBS.
    This is how you inject generated news/comment audio.
    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Updating source '{source_name}' with file: {file_path}")
        settings = {"local_file": os.path.abspath(file_path)}
        cl.set_input_settings(source_name, settings, True)
    except Exception as e:
        logging.error(f"Failed to update audio source: {e}")


def update_video_source_file(
    source_name: str,
    file_path: str,
    loop_video: bool = True,
    close_when_inactive: bool = False,
) -> None:
    """
    Dynamically changes the file used by a Video/Media Source in OBS.

    Args:
        source_name (str): Name of the video source in OBS
        file_path (str): Path to the video file
        loop_video (bool): Whether to loop the video (default: True)
        close_when_inactive (bool): Whether to close file when inactive (default: False)

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Updating video source '{source_name}' with file: {file_path}")
        settings = {
            "local_file": os.path.abspath(file_path),
            "looping": loop_video,
            "close_when_inactive": close_when_inactive,
        }
        cl.set_input_settings(source_name, settings, True)
    except Exception as e:
        logging.error(f"Failed to update video source: {e}")


def set_video_repeat_count(source_name: str, repeat_count: int | None = None) -> None:
    """
    Sets the number of times a video should repeat.

    Args:
        source_name (str): Name of the video source in OBS
        repeat_count (int): Number of times to repeat (None for infinite loop)

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(
            f"Setting video repeat count for '{source_name}' to: {repeat_count or 'infinite'}"
        )

        if repeat_count is None:
            # Infinite loop
            settings = {"looping": True}
        else:
            # Specific number of repeats - this might need custom handling
            # depending on your OBS setup and requirements
            settings = {"looping": repeat_count > 1}

        cl.set_input_settings(source_name, settings, True)
    except Exception as e:
        logging.error(f"Failed to set video repeat count: {e}")


def restart_media_source(source_name: str) -> None:
    """Restarts a media source, forcing it to play from the beginning."""
    with obs_client_manager.get_client() as cl:
        cl.trigger_media_input_action(
            source_name, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
        )


def refresh_media_source(source_name: str, new_file_path: str) -> None:
    """
    Force-refreshes a media source by updating its file and toggling visibility.

    This is a more reliable way to ensure a new song plays than just updating
    the file path and restarting.
    """
    try:
        logger.info(f"Refreshing media source '{source_name}' with new file.")
        update_audio_source_file(source_name, new_file_path)
        restart_media_source(source_name)  # Always restart to ensure new file loads

        with obs_client_manager.get_client() as cl:
            # Get the scene the source is in (assuming it's in one)
            # This part is tricky as a source can be in multiple scenes.
            # For BGM, it's usually in a dedicated scene. We'll assume a convention.
            # A more robust solution might need to know the scene name contextually.
            scene_items = cl.get_scene_item_list(SCENE_BACKGROUND_MUSIC)
            source_in_scene = any(
                item["sourceName"] == source_name for item in scene_items.scene_items
            )

            if source_in_scene:
                # Toggle visibility to force reload
                hide_source_in_scene(SCENE_BACKGROUND_MUSIC, source_name)
                time.sleep(0.1)  # Small delay to ensure OBS processes the change
                show_source_in_scene(SCENE_BACKGROUND_MUSIC, source_name)
                logger.info(f"Visibility toggled for '{source_name}' to force reload.")
            else:
                # If not in the main BGM scene, just restart as a fallback
                logger.warning(
                    f"Source '{source_name}' not found in scene '{SCENE_BACKGROUND_MUSIC}'. "
                    "Skipping visibility toggle."
                )

    except Exception as e:
        logger.error(f"Failed to refresh media source '{source_name}': {e}")


def stop_media_source(source_name: str) -> None:
    """Stops a media source playback."""
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Stopping media source: {source_name}")
        cl.trigger_media_input_action(
            source_name, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP"
        )
    except Exception as e:
        logging.error(f"Failed to stop media source: {e}")


def fade_video_source(
    source_name: str,
    scene_name: str,
    fade_type: str = "in",
    duration: float = 2.0,
    target_opacity: int = 100,
) -> None:
    """
    Fade a video source in or out by controlling scene item enabled state.

    Args:
        source_name (str): Name of the video source
        scene_name (str): Name of the scene containing the source
        fade_type (str): "in", "out", or "custom"
        duration (float): Fade duration in seconds
        target_opacity (int): Target opacity (0-100) - simplified to enabled/disabled

    """
    try:
        cl = obs_client_manager.get_client()
        # Get the scene item ID
        scene_item_id = cl.get_scene_item_id(scene_name, source_name)
        if not scene_item_id or not hasattr(scene_item_id, "scene_item_id"):
            logging.error(
                f"Could not find scene item for '{source_name}' in '{scene_name}'"
            )
            return

        item_id = scene_item_id.scene_item_id  # type:ignore

        if fade_type == "in":
            logging.info(f"Fading video '{source_name}' IN over {duration:.1f}s")
            # Start invisible, then fade in
            cl.set_scene_item_enabled(scene_name, item_id, False)
            time.sleep(0.1)  # Brief moment of invisibility
            cl.set_scene_item_enabled(scene_name, item_id, True)

        elif fade_type == "out":
            logging.info(f"Fading video '{source_name}' OUT over {duration:.1f}s")
            # Stay visible for duration, then fade out
            time.sleep(duration - 0.1)
            cl.set_scene_item_enabled(scene_name, item_id, False)
        else:  # custom
            logging.info(f"Setting video '{source_name}' visibility")
            enabled = target_opacity > 50
            cl.set_scene_item_enabled(scene_name, item_id, enabled)

        logging.info(f"✓ Video fade completed: {source_name}")

    except Exception as e:
        logging.error(f"Failed to fade video source '{source_name}': {e}")


def fade_audio_source(
    source_name: str,
    fade_type: str = "in",
    duration: float = 2.0,
    target_volume: float = 1.0,
) -> None:
    """
    Fade an audio source in or out by controlling volume multiplier.

    Args:
        source_name (str): Name of the audio source
        fade_type (str): "in", "out", or "custom"
        duration (float): Fade duration in seconds
        target_volume (float): Target volume multiplier (0.0 to 1.0, where 1.0 = 100%)

    """
    try:
        cl = obs_client_manager.get_client()

        # Get the current volume to start the fade from
        start_volume = 0.0
        try:
            current_volume_info = cl.get_input_volume(source_name)
            if hasattr(current_volume_info, "input_volume_mul"):
                start_volume = current_volume_info.input_volume_mul
        except Exception as e:
            logging.warning(
                f"Could not get current volume for '{source_name}', assuming 0: {e}"
            )

        end_volume = target_volume

        # Override start volume for a standard "fade in" from silence
        if fade_type == "in":
            start_volume = 0.0

        if abs(start_volume - end_volume) < 0.01:
            logging.info(
                f"Audio '{source_name}' is already at target volume {end_volume:.0%}."
            )
            return

        logging.info(
            f"Fading audio '{source_name}' from {start_volume:.0%} to {end_volume:.0%} over {duration:.1f}s"
        )

        # Perform the fade with smooth steps
        steps = int(duration * 10)  # 10 steps per second for smooth audio
        if steps < 1:
            steps = 1

        step_duration = duration / steps

        for step in range(steps + 1):
            progress = step / steps
            current_volume = start_volume + (end_volume - start_volume) * progress

            # Ensure volume stays within valid range
            current_volume = max(0.0, min(1.0, current_volume))

            # Set the volume using volume multiplier (0.0 to 1.0)
            cl.set_input_volume(source_name, current_volume)

            if step < steps:
                time.sleep(step_duration)

        logging.info(f"✓ Audio fade completed: {source_name}")

    except Exception as e:
        logging.error(f"Failed to fade audio source '{source_name}': {e}")


def set_bgm_volume(volume: float) -> None:
    """Ducks the background music volume directly."""
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Setting volume to {volume:.0%}")
        cl.set_input_volume("Media Playlist Source", volume)
    except Exception as e:
        logging.error(f"Failed to set background music volume: {e}")


def smooth_duck_background_music(
    duration: float = 1.0, ducked_volume: float = BACKGROUND_MUSIC_VOLUME_DUCKED
) -> None:
    """Ducks the background music volume directly."""
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Ducking background music to {ducked_volume:.0%}")
        cl.set_input_volume("Media Playlist Source", ducked_volume)
    except Exception as e:
        logging.error(f"Failed to duck background music: {e}")


def smooth_restore_background_music(
    duration: float = 1.0, normal_volume: float = BACKGROUND_MUSIC_VOLUME_NORMAL
) -> None:
    """Restores the background music volume directly."""
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Restoring background music to {normal_volume:.0%}")
        cl.set_input_volume("Media Playlist Source", normal_volume)
    except Exception as e:
        logging.error(f"Failed to restore background music: {e}")


def remove_fade_filter(source_name: str) -> None:
    """Remove fade filter from a source (simplified - no filters used)."""
    # No longer using filters for fading, so just log
    logging.info(f"✓ No fade filters to remove from: {source_name}")


def get_audio_duration_seconds(file_path: str) -> float:
    """Get the duration of an audio file in seconds using pydub."""
    import json
    import subprocess

    try:
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return 0.0

        # Method 1: Try pydub (most reliable for various formats)
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000.0  # Convert milliseconds to seconds
            logger.info(f"Audio duration (pydub): {duration:.2f} seconds")
            return duration
        except ImportError:
            logger.warning("pydub not available, trying alternative methods")
        except Exception as e:
            logger.warning(f"pydub failed: {e}")

        # Method 2: Try subprocess with ffprobe (more reliable than ffmpeg-python)
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    file_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            logging.info(f"Audio duration (ffprobe): {duration:.2f} seconds")
            return duration
        except (
            subprocess.CalledProcessError,
            KeyError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logging.warning(f"ffprobe failed: {e}")
        except Exception as e:
            logging.warning(f"ffprobe subprocess failed: {e}")

        # Method 3: Try mutagen (good for metadata)
        try:
            from mutagen import File  # type: ignore

            audio_file = File(file_path)
            if audio_file is not None and audio_file.info is not None:
                duration = audio_file.info.length
                logging.info(f"Audio duration (mutagen): {duration:.2f} seconds")
                return duration
        except ImportError:
            logging.warning("mutagen not available")
        except Exception as e:
            logging.warning(f"mutagen failed: {e}")

        # Method 4: Basic WAV file header parsing (fallback for WAV files)
        if file_path.lower().endswith(".wav"):
            try:
                import struct

                with open(file_path, "rb") as f:
                    # Read WAV header
                    header = f.read(44)
                    if (
                        len(header) >= 44
                        and header[:4] == b"RIFF"  # noqa
                        and header[8:12] == b"WAVE"  # noqa
                    ):
                        # Parse WAV header
                        _sample_rate = struct.unpack("<I", header[24:28])[0]  # noqa
                        byte_rate = struct.unpack("<I", header[28:32])[0]

                        # Get file size and calculate duration
                        file_size = os.path.getsize(file_path)
                        audio_data_size = file_size - 44  # Subtract header size
                        duration = audio_data_size / byte_rate

                        logging.info(
                            f"Audio duration (WAV header): {duration:.2f} seconds"
                        )
                        return duration
            except Exception as e:
                logging.warning(f"WAV header parsing failed: {e}")

        # Method 5: Try ffmpeg-python as last resort
        try:
            import ffmpeg  # type: ignore

            probe = ffmpeg.probe(file_path)  # type: ignore
            duration = float(probe["streams"][0]["duration"])
            logging.info(f"Audio duration (ffmpeg): {duration:.2f} seconds")
            return duration
        except ImportError:
            logging.warning("ffmpeg-python not available")
        except Exception as e:
            logging.warning(f"ffmpeg failed: {e}")

        logging.error(f"Could not determine duration for {file_path}")
        return 0.0

    except Exception as e:
        logging.error(f"Error getting audio duration: {e}")
        return 0.0


def get_video_duration_seconds(file_path: str) -> float:
    """
    Calculates the duration of a video file in seconds.
    Uses accurate detection methods when available.
    """
    try:
        import ffmpeg  # type: ignore

        probe = ffmpeg.probe(file_path)  # type: ignore
        duration = float(probe["streams"][0]["duration"])
        return duration
    except Exception:
        logging.warning(f"Using placeholder duration for video: {file_path}")
        return 120.0  # 2 minutes default


def calculate_video_audio_coefficient(
    video_file_path: str,
    audio_file_path: str | None = None,
    target_duration: float | None = None,
) -> dict[str, object]:
    """
    Calculate the looping coefficient needed to match video duration to audio.

    Args:
        video_file_path (str): Path to the source video file
        audio_file_path (str): Path to audio file (optional if target_duration provided)
        target_duration (float): Target duration in seconds (optional if audio_file_path provided)

    Returns:
        dict: Contains coefficient information and recommendations

    """
    try:
        if not os.path.exists(video_file_path):
            return {"success": False, "error": "Video file not found"}

        # Get video duration
        video_duration = get_video_duration_seconds(video_file_path)

        # Determine target duration
        if target_duration is None:
            if audio_file_path and os.path.exists(audio_file_path):
                target_duration = get_audio_duration_seconds(audio_file_path)
            else:
                return {
                    "success": False,
                    "error": "Either target_duration or valid audio_file_path must be provided",
                }

        if target_duration <= 0 or video_duration <= 0:
            return {"success": False, "error": "Invalid durations"}

        coefficient = target_duration / video_duration
        loops_needed = int(coefficient) + (1 if coefficient % 1 > 0.01 else 0)

        # Determine action needed
        if abs(video_duration - target_duration) < 0.1:
            action = "No change needed (durations match)"
        elif target_duration > video_duration:
            action = f"Loop video {loops_needed} times"
        else:
            action = f"Trim video to {target_duration:.2f}s"

        return {
            "success": True,
            "video_duration": video_duration,
            "target_duration": target_duration,
            "coefficient": coefficient,
            "loops_needed": loops_needed,
            "action": action,
            "perfect_match": abs(coefficient - round(coefficient)) < 0.01,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def match_video_duration_to_audio(
    video_file_path: str,
    audio_file_path: str | None = None,
    target_duration: float | None = None,
    output_video_path: str | None = None,
) -> str | None:
    """
    Modify a video file to match the duration of an audio file.

    Args:
        video_file_path (str): Path to the source video file
        audio_file_path (str): Path to audio file to match duration (optional if target_duration provided)
        target_duration (float): Target duration in seconds (optional if audio_file_path provided)
        output_video_path (str): Output path for the modified video (optional)

    Returns:
        str: Path to the output video file, or None if failed

    """
    try:
        if not os.path.exists(video_file_path):
            logging.error(f"Video file not found: {video_file_path}")
            return None

        # Determine target duration
        if target_duration is None:
            if audio_file_path and os.path.exists(audio_file_path):
                target_duration = get_audio_duration_seconds(audio_file_path)
                logging.info(f"Using audio file duration: {target_duration:.2f}s")
            else:
                logging.error(
                    "Either target_duration or valid audio_file_path must be provided"
                )
                return None

        if target_duration <= 0:
            logging.error("Invalid target duration")
            return None

        # If no output path specified, create one
        if output_video_path is None:
            base_name = os.path.splitext(os.path.basename(video_file_path))[0]
            output_dir = os.path.dirname(video_file_path)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_video_path = os.path.join(
                output_dir, f"{base_name}_matched_{timestamp}.mp4"
            )

        # Method 1: Try moviepy (most user-friendly)
        try:
            from moviepy.editor import (VideoFileClip,  # type: ignore
                                        concatenate_videoclips)

            with VideoFileClip(video_file_path) as video:
                original_duration = video.duration
                logging.info(
                    f"Original video duration: {original_duration:.2f}s, target: {target_duration:.2f}s"
                )

                if abs(original_duration - target_duration) < 0.1:
                    logging.info("Video duration already matches target (within 0.1s)")
                    return video_file_path

                if target_duration > original_duration:
                    # Calculate coefficient for looping
                    coefficient = target_duration / original_duration
                    loops_needed = int(coefficient) + (
                        1 if coefficient % 1 > 0.01 else 0
                    )
                    logging.info(
                        f"Looping video {loops_needed} times (coefficient: {coefficient:.2f})"
                    )

                    # Create seamless loops by ensuring no audio conflicts
                    # Remove audio from video to prevent sync issues during looping
                    video_no_audio = video.without_audio()
                    clips = [video_no_audio] * loops_needed
                    logging.info(f"Creating {len(clips)} video clips for concatenation")

                    # Concatenate clips seamlessly
                    looped_video = concatenate_videoclips(clips, method="compose")
                    logging.info(
                        f"Concatenated video duration: {looped_video.duration:.2f}s"
                    )

                    # Trim to exact target duration
                    final_video = looped_video.subclip(0, target_duration)
                    logging.info(
                        f"Final trimmed video duration: {final_video.duration:.2f}s"
                    )
                else:
                    # Need to trim the video
                    logging.info(
                        f"Trimming video from {original_duration:.2f}s to {target_duration:.2f}s"
                    )
                    final_video = video.subclip(0, target_duration)

                # Write the result with optimized settings
                logging.info(
                    f"Writing matched video to: {os.path.basename(output_video_path)}"
                )
                final_video.write_videofile(
                    output_video_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile="temp-audio.m4a",
                    remove_temp=True,
                    preset="fast",
                    ffmpeg_params=["-movflags", "+faststart"],
                    verbose=False,
                    logger=None,
                )
                logging.info("✓ Video writing completed")

                logging.info(
                    f"Video duration matched and saved to: {output_video_path}"
                )
                return output_video_path

        except ImportError:
            logging.warning("moviepy not available, trying ffmpeg")
        except Exception as e:
            logging.warning(f"moviepy processing failed: {e}")

        # Method 2: Try ffmpeg directly
        try:
            import ffmpeg  # type: ignore

            # Get original video info
            probe = ffmpeg.probe(video_file_path)  # type: ignore
            video_stream = next(
                (
                    stream
                    for stream in probe["streams"]
                    if stream["codec_type"] == "video"
                ),
                None,
            )

            if not video_stream:
                logging.error("No video stream found in file")
                return None

            original_duration = float(video_stream.get("duration", 0))
            logging.info(
                f"Original video duration: {original_duration:.2f}s, target: {target_duration:.2f}s"
            )

            if abs(original_duration - target_duration) < 0.1:
                logging.info("Video duration already matches target (within 0.1s)")
                return video_file_path

            if target_duration > original_duration:
                # Calculate coefficient for looping
                coefficient = target_duration / original_duration
                loops_needed = int(coefficient) + (1 if coefficient % 1 > 0.01 else 0)
                logging.info(
                    f"Looping video {loops_needed} times (coefficient: {coefficient:.2f})"
                )

                # Create input streams for seamless looping
                inputs = [ffmpeg.input(video_file_path) for _ in range(loops_needed)]  # type: ignore
                concatenated = ffmpeg.concat(*inputs, v=1, a=1)  # type: ignore
                output = ffmpeg.output(
                    concatenated, output_video_path, t=target_duration
                )  # type: ignore
            else:
                # Trim the video to target duration
                logging.info(
                    f"Trimming video from {original_duration:.2f}s to {target_duration:.2f}s"
                )
                input_stream = ffmpeg.input(video_file_path)  # type: ignore
                output = ffmpeg.output(
                    input_stream, output_video_path, t=target_duration
                )  # type: ignore

            # Run the ffmpeg command
            ffmpeg.run(output, overwrite_output=True, quiet=True)  # type: ignore

            logging.info(f"Video duration matched and saved to: {output_video_path}")
            return output_video_path

        except ImportError:
            logging.warning("ffmpeg-python not available")
        except Exception as e:
            logging.error(f"ffmpeg processing failed: {e}")

        logging.error(
            "No video processing library available. Install moviepy or ffmpeg-python"
        )
        return None

    except Exception as e:
        logging.error(f"Error matching video duration: {e}")
        return None


def start_streaming() -> None:
    """Starts the OBS stream output."""
    try:
        cl = obs_client_manager.get_client()
        cl.start_stream()
        logging.info("Streaming started.")
    except Exception as e:
        if "streaming is already active" in str(e).lower():
            logging.warning("Stream is already active.")
        else:
            logging.error(f"Failed to start streaming: {e}")


def stop_streaming() -> None:
    """Stops the OBS stream output."""
    try:
        cl = obs_client_manager.get_client()
        cl.stop_stream()
        logging.info("Streaming stopped.")
    except Exception as e:
        # This can fail if streaming wasn't active, which is fine.
        logging.warning(f"Could not stop streaming (it may not have been active): {e}")


def is_streaming() -> bool:
    """Check if OBS is currently streaming."""
    try:
        cl = obs_client_manager.get_client()
        status = cl.get_stream_status()
        return status.output_active
    except Exception as e:
        logging.error(f"Failed to check streaming status: {e}")
        return False


def ensure_streaming() -> bool:
    """
    Ensures that OBS is streaming. If not streaming, attempts to start the stream.

    Returns
    -------
    bool
        True if streaming is active (either was already active or successfully started),
        False if failed to start streaming.
    """
    try:
        # Check if already streaming
        if is_streaming():
            logging.info("Stream is already active.")
            return True

        # Try to start streaming
        logging.info("Stream is not active. Attempting to start streaming...")
        start_streaming()

        # Verify that streaming started successfully
        if is_streaming():
            logging.info("Stream started successfully.")
            return True
        else:
            logging.error("Failed to start streaming.")
            return False

    except Exception as e:
        logging.error(f"Error ensuring streaming status: {e}")
        return False


def run_audio_matched_video_segment(
    video_path: str,
    audio_path: str | None,
    scene_name: str,
    duck_background_music: bool,
    background_music_active: bool,
    normal_bg_volume: float,
    ducked_bg_volume: float,
    forced_duration: float | None = None,
) -> dict[str, object]:
    """
    Runs a video segment with optional audio, using simple OBS looping.
    This is a blocking function that waits for the segment to complete.
    It returns information needed for later cleanup.
    """
    segment_info = {}
    try:
        logging.info(f"--- Preparing VIDEO Segment for scene '{scene_name}' ---")

        has_audio = bool(audio_path and os.path.exists(audio_path))

        audio_duration = get_audio_duration_seconds(audio_path) if has_audio else 0
        video_duration = get_video_duration_seconds(video_path)

        if has_audio:
            segment_duration = audio_duration
        elif forced_duration:
            segment_duration = forced_duration
        else:
            # Fallback for visual-only scenes without a specified duration
            segment_duration = max(video_duration, 10.0)

        logging.info(
            f"Audio duration: {audio_duration:.2f}s"
            if has_audio
            else "No audio for segment."
        )
        logging.info(f"Video duration: {video_duration:.2f}s")
        if forced_duration and not has_audio:
            logging.info(
                f"Using forced duration for visual-only scene: {forced_duration}s"
            )
        logging.info(f"Segment will run for: {segment_duration:.2f}s")

        timestamp = time.strftime("%H%M%S")
        video_source_name = f"Matched_Video_{timestamp}"
        audio_source_name = f"Matched_Audio_{timestamp}" if has_audio else None

        sources_to_cleanup = [s for s in [video_source_name, audio_source_name] if s]

        segment_info = {
            "scene_name": scene_name,
            "video_source_name": video_source_name,
            "audio_source_name": audio_source_name,
            "sources_to_cleanup": sources_to_cleanup,
            "background_music_active": background_music_active,
            "normal_bg_volume": normal_bg_volume,
        }

        create_or_update_video_source_centered(
            scene_name=scene_name,
            source_name=video_source_name,
            file_path=video_path,
            loop_video=True,
            scale_x=VIDEO_SCALE_X,
            scale_y=VIDEO_SCALE_Y,
            # Mute the video's own audio track if we are playing a separate one.
            mute_audio=has_audio,
        )

        if has_audio and audio_source_name:
            create_or_update_audio_source(scene_name, audio_source_name, audio_path)
            # Give OBS a moment to process the new source before we stop it.
            time.sleep(0.1)

        # NOTE: We no longer stop media sources here. We will rely on the default OBS
        # behavior where sources are set to "restart when active". This ensures both
        # audio and video begin playback simultaneously when the scene transition completes.
        # Explicitly stopping/restarting them was causing sync issues.

        switch_to_scene_smooth(scene_name, "Fade", TRANSITION_DURATION_MS)

        # NOTE: Both video and audio sources are now triggered automatically by the scene
        # activation above. Explicit restart commands are no longer needed and would
        # cause sync and "double-start" issues.

        if background_music_active:
            if duck_background_music:
                smooth_duck_background_music(1.0, ducked_bg_volume)
            else:
                smooth_restore_background_music(1.0, normal_bg_volume)

        logging.info(f"Playing segment for {segment_duration:.2f} seconds...")
        time.sleep(segment_duration)

        return {"success": True, "cleanup_info": segment_info}

    except Exception as e:
        logging.error(f"Error in audio-matched video segment: {e}")
        return {"success": False, "error": str(e), "cleanup_info": segment_info}


def cleanup_scene_resources(cleanup_info: dict[str, object]) -> None:
    """Cleans up resources from a previous scene after a transition."""
    if not cleanup_info:
        return

    logging.info(
        f"--- Cleaning up post-transition for scene '{cleanup_info.get('scene_name')}' ---"
    )

    scene = cleanup_info.get("scene_name")
    video_source = cleanup_info.get("video_source_name")
    sources_to_cleanup = cleanup_info.get("sources_to_cleanup", [])

    if video_source:
        stop_media_source(video_source)

    if scene and sources_to_cleanup:
        logging.info(f"Cleaning up OBS sources: {sources_to_cleanup}")
        cleanup_temporary_sources(scene, sources_to_cleanup)


def add_global_source_to_scene(scene_name: str, source_name: str) -> bool:
    """
    Adds an existing global source to a scene as a scene item.
    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Adding global source '{source_name}' to scene '{scene_name}'")
        cl.create_scene_item(scene_name, source_name, True)
        logging.info(f"✓ Global source '{source_name}' added to scene '{scene_name}'")
        return True
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logging.info(
                f"✓ Global source '{source_name}' already exists in scene '{scene_name}'"
            )
            return True
        else:
            logging.warning(
                f"Could not add global source '{source_name}' to scene '{scene_name}': {e}"
            )
            return False


def add_scene_as_source(target_scene: str, source_scene_name: str) -> bool:
    """Adds an existing scene as a source to the target scene (scene nesting)."""
    try:
        cl = obs_client_manager.get_client()

        # Check if the scene item already exists in the target scene
        items = cl.get_scene_item_list(target_scene).scene_items  # type:ignore
        for item in items:
            if item["sourceName"] == source_scene_name:
                logging.info(
                    f"Scene source '{source_scene_name}' already in '{target_scene}'."
                )
                return True

        # Scenes can be added as sources by creating a scene item
        cl.create_scene_item(target_scene, source_scene_name, True)
        logging.info(
            f"Added scene '{source_scene_name}' as a source to '{target_scene}'"
        )
        return True

    except Exception as e:
        # Gracefully handle cases where the source already exists.
        if "does not exist" in str(e).lower():
            logging.error(
                f"Cannot nest scene '{source_scene_name}' because it does not exist."
            )
        elif "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logging.info(
                f"Scene source '{source_scene_name}' is already present in '{target_scene}'."
            )
            return True
        else:
            logging.error(
                f"Failed to add scene '{source_scene_name}' to '{target_scene}': {e}"
            )
        return False


def init_background_music(music_file_path: str, *_: object, **__: object) -> bool:
    """
    Simplified helper that ensures the main music scene exists and attaches a
    looping background‑music audio source to it.

    Parameters
    ----------
    music_file_path : str
        Path to the audio file that should loop in the *Scene‑Music* scene.

    Returns
    -------
    bool
        True if successful, False otherwise.

    """
    try:
        # 1. Ensure the Scene‑Music scene exists
        if not scene_exists(SCENE_MUSIC):
            create_scene(SCENE_MUSIC)

        # 2. Create or update the audio source inside Scene‑Music
        create_or_update_audio_source(
            scene_name=SCENE_MUSIC,
            source_name=BACKGROUND_MUSIC_SOURCE,
            file_path=music_file_path,
            looping=True,
            close_when_inactive=False,
            monitor_type=MONITOR_AND_OUTPUT,
        )

        # 3. Start playback of the source
        restart_media_source(BACKGROUND_MUSIC_SOURCE)

        logging.info("✓ Background music started.")
        return True

    except Exception as e:
        logging.error(f"❌ Failed to start background music: {e}")
        return False


def init_voice_audio(music_file_path: str, *_: object, **__: object) -> None:
    try:
        if not scene_exists(SCENE_VOICE):
            create_scene(SCENE_VOICE)

        create_or_update_audio_source(
            scene_name=SCENE_VOICE,
            source_name=VOICE_MUSIC_SOURCE,
            file_path=music_file_path,
            looping=False,
            close_when_inactive=False,
            monitor_type=MONITOR_AND_OUTPUT,
        )

        # 3. Start playback of the source
        restart_media_source(BACKGROUND_MUSIC_SOURCE)

        logging.info("✓ Background music started.")
        return True

    except Exception as e:
        logging.error(f"❌ Failed to start voice: {e}")
        return False


# --- Radio Show Segments ---


def run_music_segment() -> None:
    """Switches to the music scene and sets up music video."""
    logging.info("--- Starting MUSIC Segment ---")

    # Update music video if it exists
    if os.path.exists(MUSIC_VIDEO_PATH):
        update_video_source_file(
            VIDEO_SOURCE_FOR_MUSIC, MUSIC_VIDEO_PATH, loop_video=True
        )
        restart_media_source(VIDEO_SOURCE_FOR_MUSIC)

    # Switch to music scene with smooth transition
    switch_to_scene_smooth(SCENE_MUSIC, "Fade", TRANSITION_DURATION_MS)

    # Hide any music banners/overlays that might cover the video
    hide_music_banner_sources(SCENE_MUSIC)


def run_news_segment() -> None:
    """
    Generates news audio and video, updates OBS, switches to the news scene,
    and schedules the return to music.
    """
    logging.info("--- Starting NEWS Segment ---")

    # 1. Generate the content (This is where you call your AI APIs)
    logging.info("Generating news script, audio, and video...")
    # news_script = your_llm_function()
    # your_tts_function(news_script, GENERATED_AUDIO_PATH)
    # your_video_generation_function(news_script, GENERATED_VIDEO_PATH)

    # For this example, we'll just create placeholder files.
    # Replace this with your actual generation logic.
    AudioSegment.silent(duration=30000).export(
        GENERATED_AUDIO_PATH, format="mp3"
    )  # Placeholder 30s audio

    # 2. Update the OBS Media Sources to point to our new files
    update_audio_source_file(AUDIO_SOURCE_FOR_NEWS, GENERATED_AUDIO_PATH)

    if os.path.exists(GENERATED_VIDEO_PATH):
        # Set video to play only once for news (no loop)
        update_video_source_file(
            VIDEO_SOURCE_FOR_NEWS, GENERATED_VIDEO_PATH, loop_video=False
        )
        restart_media_source(VIDEO_SOURCE_FOR_NEWS)

    # 3. Switch to the News Scene in OBS
    switch_to_scene(SCENE_NEWS)

    # 4. Wait for the news to finish before the next segment
    duration = get_audio_duration_seconds(GENERATED_AUDIO_PATH)
    logging.info(f"News segment will run for {duration:.2f} seconds.")
    time.sleep(duration + 2)  # Add a small buffer

    # 5. After the news is done, go back to music
    run_music_segment()


def list_scene_sources(scene_name: str) -> list[dict[str, object]]:
    """
    Lists all sources in a specific scene with their visibility status.

    Args:
        scene_name (str): Name of the OBS scene

    Returns:
        list: List of dictionaries containing source info

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Listing sources in scene '{scene_name}'")

        # Get scene items
        scene_items = cl.get_scene_item_list(scene_name)
        if not scene_items:
            logging.warning(f"No scene items found in '{scene_name}'")
            return []

        sources = []
        items = getattr(scene_items, "scene_items", [])
        if not items:
            logging.warning(f"No scene items found in '{scene_name}'")
            return []

        for item in items:
            if (
                hasattr(item, "sourceName")  # noqa
                and hasattr(item, "sceneItemEnabled")  # noqa
                and hasattr(item, "sceneItemId")  # noqa
            ):
                source_info = {
                    "name": item.sourceName,
                    "visible": item.sceneItemEnabled,
                    "id": item.sceneItemId,
                }
                sources.append(source_info)
                logging.info(
                    f"  - {source_info['name']}: {'Visible' if source_info['visible'] else 'Hidden'}"
                )

        return sources

    except Exception as e:
        logging.error(f"Failed to list sources in scene '{scene_name}': {e}")
        return []


def hide_source_in_scene(scene_name: str, source_name: str) -> bool:
    """
    Hides a source in a specific scene without deleting it.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the source to hide

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Hiding source '{source_name}' in scene '{scene_name}'")

        # Get the scene item ID
        scene_item_id = cl.get_scene_item_id(scene_name, source_name)
        if not scene_item_id or not hasattr(scene_item_id, "scene_item_id"):
            logging.debug(
                f"Source '{source_name}' not found in scene '{scene_name}' (this is normal when switching locations)"
            )
            return False

        item_id = scene_item_id.scene_item_id  # type:ignore

        # Hide the source
        cl.set_scene_item_enabled(scene_name, item_id, False)
        logging.info(f"Successfully hid source '{source_name}' in scene '{scene_name}'")
        return True

    except Exception as e:
        # Check if it's a "source not found" error (code 600)
        error_msg = str(e)
        if "code 600" in error_msg or "No scene items were found" in error_msg:
            logging.debug(
                f"Source '{source_name}' not found in scene '{scene_name}' (this is normal when switching locations): {e}"
            )
        else:
            logging.warning(
                f"Failed to hide source '{source_name}' in scene '{scene_name}': {e}"
            )
        return False


def show_source_in_scene(scene_name: str, source_name: str) -> bool:
    """
    Shows a source in a specific scene.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the source to show

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Showing source '{source_name}' in scene '{scene_name}'")

        # Get the scene item ID
        scene_item_id = cl.get_scene_item_id(scene_name, source_name)
        if not scene_item_id or not hasattr(scene_item_id, "scene_item_id"):
            logging.warning(f"Source '{source_name}' not found in scene '{scene_name}'")
            return False

        item_id = scene_item_id.scene_item_id  # type:ignore

        # Show the source
        cl.set_scene_item_enabled(scene_name, item_id, True)
        logging.info(
            f"Successfully showed source '{source_name}' in scene '{scene_name}'"
        )
        return True

    except Exception as e:
        logging.error(
            f"Failed to show source '{source_name}' in scene '{scene_name}': {e}"
        )
        return False


def hide_music_banner_sources(
    scene_name: str = SCENE_MUSIC, banner_keywords: list[str] | None = None
) -> None:
    """
    Hides common music banner/overlay sources in the music scene.

    Args:
        scene_name (str): Name of the music scene
        banner_keywords (list): Keywords to identify banner sources (default: common music overlay names)

    """
    if banner_keywords is None:
        banner_keywords = [
            "banner",
            "song",
            "track",
            "title",
            "artist",
            "now playing",
            "music",
            "overlay",
            "text",
        ]

    try:
        logging.info(f"Hiding music banner sources in scene '{scene_name}'")

        # Get all sources in the scene
        sources = list_scene_sources(scene_name)
        hidden_sources = []

        for source in sources:
            source_name_lower = source["name"].lower()

            # Check if source name contains any banner keywords
            for keyword in banner_keywords:
                if keyword.lower() in source_name_lower and source["visible"]:
                    if hide_source_in_scene(scene_name, source["name"]):
                        hidden_sources.append(source["name"])
                    break

        if hidden_sources:
            logging.info(f"Hidden banner sources: {hidden_sources}")
        else:
            logging.info("No banner sources found to hide")

        return hidden_sources

    except Exception as e:
        logging.error(f"Failed to hide music banner sources: {e}")
        return []


def delete_source_from_scene(scene_name: str, source_name: str) -> None:
    """
    Deletes a source from a specific scene.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the source to delete

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Deleting source '{source_name}' from scene '{scene_name}'")

        # Get the scene item ID first
        scene_item_id = cl.get_scene_item_id(scene_name, source_name)
        if not scene_item_id or not hasattr(scene_item_id, "scene_item_id"):
            logging.warning(
                f"Source '{source_name}' not found in scene '{scene_name}' - may already be deleted"
            )
            return

        item_id = scene_item_id.scene_item_id  # type:ignore

        # Remove the scene item
        cl.remove_scene_item(scene_name, item_id)
        logging.info(
            f"Successfully deleted source '{source_name}' from scene '{scene_name}'"
        )

    except Exception as e:
        logging.error(
            f"Failed to delete source '{source_name}' from scene '{scene_name}': {e}"
        )


def cleanup_temporary_sources(scene_name: str, source_names: list[str]) -> None:
    """
    Deletes multiple temporary sources from a scene.

    Args:
        scene_name (str): Name of the OBS scene
        source_names (list): List of source names to delete

    """
    for source_name in source_names:
        delete_source_from_scene(scene_name, source_name)


def run_custom_video_segment(
    video_path: str,
    audio_path: str | None = None,
    scene_name: str = SCENE_NEWS,
    repeat_count: int = 1,
    video_source_name: str = VIDEO_SOURCE_FOR_NEWS,
    width: int | None = None,
    height: int | None = None,
    x_pos: int = 0,
    y_pos: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    cleanup_after: bool = True,
) -> None:
    """
    Runs a custom video segment with specified repeat count and sizing.

    Args:
        video_path (str): Path to the video file
        audio_path (str): Optional path to audio file (if separate from video)
        scene_name (str): OBS scene to use
        repeat_count (int): Number of times to repeat the video (None for infinite)
        video_source_name (str): Name of the video source to create/update
        width (int): Width in pixels (None to use original)
        height (int): Height in pixels (None to use original)
        x_pos (int): X position in pixels
        y_pos (int): Y position in pixels
        scale_x (float): Horizontal scale factor (1.0 = 100%)
        scale_y (float): Vertical scale factor (1.0 = 100%)
        cleanup_after (bool): Whether to delete the source after video finishes (default: True)

    """
    logging.info(
        f"--- Starting CUSTOM VIDEO Segment (repeats: {repeat_count or 'infinite'}) ---"
    )

    # Keep track of sources we create for cleanup
    sources_to_cleanup = []

    # Update video source
    loop_video = repeat_count is None or repeat_count > 1
    create_or_update_video_source(
        scene_name,
        video_source_name,
        video_path,
        loop_video=loop_video,
        width=width,
        height=height,
        x_pos=x_pos,
        y_pos=y_pos,
        scale_x=scale_x,
        scale_y=scale_y,
    )

    # Add to cleanup list if it's not a default source name
    if cleanup_after and video_source_name not in [
        VIDEO_SOURCE_FOR_NEWS,
        VIDEO_SOURCE_FOR_MUSIC,
    ]:
        sources_to_cleanup.append(video_source_name)

    # Set video repeat count
    set_video_repeat_count(video_source_name, repeat_count)

    # Restart the video source
    restart_media_source(video_source_name)

    # Update audio source if provided
    audio_source_name = None
    if audio_path and os.path.exists(audio_path):
        audio_source_name = f"{video_source_name}_Audio"
        # Create audio source if needed
        create_or_update_audio_source(scene_name, audio_source_name, audio_path)
        if cleanup_after:
            sources_to_cleanup.append(audio_source_name)

    # Switch to scene
    switch_to_scene(scene_name)

    # Calculate how long to stay in this segment
    if repeat_count:
        video_duration = get_video_duration_seconds(video_path)
        total_duration = video_duration * repeat_count
        logging.info(f"Custom video segment will run for {total_duration:.2f} seconds.")
        time.sleep(total_duration + 2)  # Add buffer

        # Clean up sources after video finishes
        if cleanup_after and sources_to_cleanup:
            logging.info(f"Cleaning up temporary sources: {sources_to_cleanup}")
            cleanup_temporary_sources(scene_name, sources_to_cleanup)

        # Return to music after custom segment
        run_music_segment()


def calculate_center_position(
    source_width=None, source_height=None, canvas_width=None, canvas_height=None
):
    """
    Calculates the center position for a source on the canvas.

    Args:
        source_width (int): Width of the source (optional)
        source_height (int): Height of the source (optional)
        canvas_width (int): Width of the canvas (optional, will auto-detect)
        canvas_height (int): Height of the canvas (optional, will auto-detect)

    Returns:
        tuple: (x_pos, y_pos) for centering the source

    """
    # Get canvas size if not provided
    if canvas_width is None or canvas_height is None:
        canvas_width, canvas_height = get_canvas_size()

    # If source dimensions not provided, assume source fills canvas (scale to fit)
    if source_width is None:
        source_width = canvas_width
    if source_height is None:
        source_height = canvas_height

    # Calculate center position
    x_pos = (canvas_width - source_width) // 2
    y_pos = (canvas_height - source_height) // 2

    return (x_pos, y_pos)


def create_or_update_video_source_centered(
    scene_name: str,
    source_name: str,
    file_path: str,
    loop_video: bool = True,
    close_when_inactive: bool = False,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    mute_audio: bool = False,
) -> None:
    """
    Creates or updates a video source and centers it on the canvas.

    Args:
        scene_name (str): Name of the OBS scene
        source_name (str): Name of the video source
        file_path (str): Path to the video file
        loop_video (bool): Whether to loop the video
        close_when_inactive (bool): Whether to close file when inactive
        scale_x (float): Horizontal scale factor (1.0 = 100%)
        scale_y (float): Vertical scale factor (1.0 = 100%)
        mute_audio (bool): Whether to mute the audio of the video source

    """
    # Simply call the main function with center=True
    create_or_update_video_source(
        scene_name=scene_name,
        source_name=source_name,
        file_path=file_path,
        loop_video=loop_video,
        close_when_inactive=close_when_inactive,
        center=True,  # This is the key change!
        scale_x=scale_x,
        scale_y=scale_y,
        mute_audio=mute_audio,
    )


def create_global_audio_source(source_name: str, file_path: str) -> bool:
    """
    Creates a GLOBAL audio source that is independent of any scene.
    This source can then be added to multiple scenes as needed.

    Args:
        source_name (str): Name of the global audio source
        file_path (str): Path to the audio file

    Returns:
        bool: True if successful, False otherwise

    """
    try:
        cl = obs_client_manager.get_client()
        logging.info(f"Creating GLOBAL audio source: {source_name}")

        # Create the source as a global input (not tied to any scene)
        # This is done by creating it in the first scene, making it available globally.
        # We need a "primary" scene to host the source initially.
        primary_scene = SCENE_NEWS  # Or another default scene #type: ignore

        cl.create_input(
            primary_scene,  # Scene to create the source in
            source_name,  # Name of the new source
            "ffmpeg_source",  # Media Source kind
            {
                "local_file": os.path.abspath(file_path),
                "looping": True,  # Background music should loop
                "close_when_inactive": False,
            },
            True,  # Enabled
        )

        logging.info(f"✓ Global audio source '{source_name}' created successfully")
        return True

    except Exception as e:
        # Check if source already exists
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logging.info(f"✓ Global audio source '{source_name}' already exists")
            # Update its settings
            try:
                cl = obs_client_manager.get_client()
                cl.set_input_settings(
                    source_name,
                    {
                        "local_file": os.path.abspath(file_path),
                        "looping": True,
                        "close_when_inactive": False,
                    },
                    True,
                )
                logging.info(
                    f"✓ Updated settings for existing global source '{source_name}'"
                )
                return True
            except Exception as update_error:
                logging.error(
                    f"Failed to update existing global source: {update_error}"
                )
                return False
        else:
            logging.error(f"Failed to create global audio source: {e}")
            return False


def create_background_music_source(
    music_file_path: str, scene_name: str | None = None
) -> bool:
    """
    DEPRECATED: This function is replaced by the new `start_background_music` logic.
    """
    logging.warning(
        "`create_background_music_source` is deprecated and should not be used."
    )
    return False


#
# ------------------------------------------------------------------------
# 🛠️  AUTO‑SETUP HELPER
# ------------------------------------------------------------------------


def setup_obs_environment(
    music_video_path: str = MUSIC_VIDEO_PATH,
    news_video_path: str = GENERATED_VIDEO_PATH,
    news_audio_path: str = GENERATED_AUDIO_PATH,
    background_music_path: str | None = None,
    background_music_duck: bool = False,
) -> None:
    """
    Automatically creates all scenes and default sources in OBS so that the
    live setup exactly matches the constants declared at the top of this
    module.

    Parameters
    ----------
    music_video_path : str
        Path to the looping video that should play in the music scene.
    news_video_path : str
        Path to the placeholder video for the news scene (optional).
    news_audio_path : str
        Path to the placeholder audio for the news scene (optional).
    background_music_path : str | None
        Path to a background music file.  If provided, a global looping
        audio source will be created and shared to every scene.
    background_music_duck : bool
        If ``True`` and ``background_music_path`` is supplied, the background
        music starts at the ducked volume; otherwise it starts at the normal
        volume.

    """
    logging.info("=== OBS auto‑setup started ===")

    # TODO: remove from here
    required_scenes = [
        SCENE_MUSIC,
        SCENE_NEWS,
        SCENE_READING,
        SCENE_TALKING,
        SCENE_GREETING,
        SCENE_BACKGROUND_MUSIC,
    ]
    for scene in required_scenes:
        if not scene_exists(scene):
            create_scene(scene)

    # 2️⃣  MUSIC scene – looping visuals
    if music_video_path and os.path.exists(music_video_path):
        create_or_update_video_source_centered(
            scene_name=SCENE_MUSIC,
            source_name=VIDEO_SOURCE_FOR_MUSIC,
            file_path=music_video_path,
            loop_video=True,
            scale_x=VIDEO_SCALE_X,
            scale_y=VIDEO_SCALE_Y,
        )

    # 3️⃣  NEWS scene – audio + (optional) video placeholders
    if news_audio_path and os.path.exists(news_audio_path):
        create_or_update_audio_source(
            scene_name=SCENE_NEWS,
            source_name=AUDIO_SOURCE_FOR_NEWS,
            file_path=news_audio_path,
        )

    if news_video_path and os.path.exists(news_video_path):
        create_or_update_video_source_centered(
            scene_name=SCENE_NEWS,
            source_name=VIDEO_SOURCE_FOR_NEWS,
            file_path=news_video_path,
            loop_video=False,
            scale_x=VIDEO_SCALE_X,
            scale_y=VIDEO_SCALE_Y,
        )

    logging.info("✓ OBS auto‑setup finished")


# ------------------------------------------------------------------------
# Optional CLI entry point
# ------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialise OBS scenes & sources based on obs_functions.py"
    )
    parser.add_argument(
        "--music-video",
        default=MUSIC_VIDEO_PATH,
        help="Path to the visuals for the music scene",
    )
    parser.add_argument(
        "--news-video",
        default=GENERATED_VIDEO_PATH,
        help="Path to placeholder video for the news scene",
    )
    parser.add_argument(
        "--news-audio",
        default=GENERATED_AUDIO_PATH,
        help="Path to placeholder audio for the news scene",
    )
    parser.add_argument(
        "--bg-music",
        default=None,
        help="Path to background music file (optional)",
    )
    parser.add_argument(
        "--bg-duck",
        action="store_true",
        help="Start background music in ducked mode",
    )

    args = parser.parse_args()
    setup_obs_environment(
        music_video_path=args.music_video,
        news_video_path=args.news_video,
        news_audio_path=args.news_audio,
        background_music_path=args.bg_music,
        background_music_duck=args.bg_duck,
    )

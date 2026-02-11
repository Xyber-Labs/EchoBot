#!/usr/bin/env python3
"""
Video Utilities for OBS Director
Provides accurate video duration detection and other video helpers.
"""

import json
import os

from app_logging.logger import logger


def get_video_duration_accurate(file_path: str) -> float:
    """
    Get accurate video duration using multiple methods.
    Returns duration in seconds.
    """
    if not os.path.exists(file_path):
        logger.error(f"Video file not found: {file_path}")
        return 0.0

    # Method 1: Try ffmpeg-python (most accurate)
    try:
        import ffmpeg  # type: ignore

        probe = ffmpeg.probe(file_path)  # type: ignore
        duration = float(probe["streams"][0]["duration"])
        logger.info(f"Got video duration using ffmpeg: {duration:.2f} seconds")
        return duration
    except ImportError:
        logger.warning(
            "ffmpeg-python not installed. Install with: pip install ffmpeg-python"
        )
    except Exception as e:
        logger.warning(f"ffmpeg probe failed: {e}")

    # Method 2: Try moviepy
    try:
        from moviepy.editor import VideoFileClip  # type: ignore

        with VideoFileClip(file_path) as clip:
            duration = clip.duration
            logger.info(f"Got video duration using moviepy: {duration:.2f} seconds")
            return duration
    except ImportError:
        logger.warning("moviepy not installed. Install with: pip install moviepy")
    except Exception as e:
        logger.warning(f"moviepy failed: {e}")

    # Method 3: Try opencv
    try:
        import cv2

        cap = cv2.VideoCapture(file_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps
        cap.release()
        logger.info(f"Got video duration using opencv: {duration:.2f} seconds")
        return duration
    except ImportError:
        logger.warning("opencv not installed. Install with: pip install opencv-python")
    except Exception as e:
        logger.warning(f"opencv failed: {e}")

    # Fallback: Return default duration
    logger.warning(f"Could not determine duration for {file_path}, using default 120s")
    return 120.0


def install_video_dependencies() -> None:
    """Install required dependencies for video processing."""
    import subprocess
    import sys

    dependencies = ["ffmpeg-python", "moviepy", "opencv-python"]

    logger.info("Installing video processing dependencies...")
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            logger.info(f"{dep} installed successfully")
        except subprocess.CalledProcessError:
            logger.info(f"Failed to install {dep}")


def get_video_info(file_path: str) -> dict[str, object]:
    """Get comprehensive video information."""
    info = {
        "duration": 0.0,
        "fps": 0.0,
        "width": 0,
        "height": 0,
        "format": "",
        "size_mb": 0.0,
    }

    if not os.path.exists(file_path):
        return info

    # File size
    info["size_mb"] = os.path.getsize(file_path) / (1024 * 1024)

    # Video properties
    try:
        import ffmpeg  # type: ignore

        probe = ffmpeg.probe(file_path)  # type: ignore
        video_stream = next(
            (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
            None,
        )

        if video_stream:
            info["duration"] = float(video_stream.get("duration", 0))
            info["fps"] = eval(video_stream.get("r_frame_rate", "0/1"))
            info["width"] = int(video_stream.get("width", 0))
            info["height"] = int(video_stream.get("height", 0))
            info["format"] = video_stream.get("codec_name", "")

    except Exception as e:
        logger.warning(f"Could not get detailed video info: {e}")
        info["duration"] = get_video_duration_accurate(file_path)

    return info


def validate_video_file(file_path):
    """Validate if a video file is suitable for OBS."""
    if not os.path.exists(file_path):
        return False, "File not found"

    info = get_video_info(file_path)

    # Check file size (warn if too large)
    if info["size_mb"] > 500:
        return (
            False,
            f"Video file is very large ({info['size_mb']:.1f}MB). Consider compressing.",
        )

    # Check duration (warn if too long for short segments)
    if info["duration"] > 600:  # 10 minutes
        return (
            False,
            f"Video is very long ({info['duration']:.1f}s). Consider splitting.",
        )

    # Check resolution (warn if too high)
    if info["width"] > 1920 or info["height"] > 1080:
        return (
            False,
            f"High resolution ({info['width']}x{info['height']}). May impact performance.",
        )

    return True, "Video file looks good!"


if __name__ == "__main__":
    import sys

    # ============================================
    # SPECIFY YOUR VIDEO FILE PATH HERE:
    # ============================================
    # <-- Change this to your video file path
    video_path = (
        "C:/Users/Doctor Who/Desktop/agent_actions/action_listening_music_slow.mp4"
    )

    # You can also use command line arguments if you prefer
    if len(sys.argv) > 1:
        if "--install-deps" in sys.argv:
            install_video_dependencies()
            exit()
        video_path = sys.argv[1]

    # Analyze the video
    if video_path != "path/to/your/video.mp4":  # Only run if path has been changed
        logger.info(f"Analyzing video: {video_path}")
        print("-" * 50)

        # Validate
        is_valid, message = validate_video_file(video_path)
        logger.info(f"Validation: {message}")

        if is_valid or os.path.exists(video_path):
            # Get info
            info = get_video_info(video_path)
            logger.info(f"Duration: {info['duration']:.2f} seconds")
            logger.info(f"Resolution: {info['width']}x{info['height']}")
            logger.info(f"FPS: {info['fps']:.2f}")
            logger.info(f"Format: {info['format']}")
            logger.info(f"Size: {info['size_mb']:.1f} MB")
        else:
            logger.info(f"Error: Could not access video file at {video_path}")

    else:
        logger.info("Please specify your video file path in the code!")
        logger.info('Edit line 131: video_path = "path/to/your/video.mp4"')
        logger.info("")
        logger.info("Alternative usage:")
        logger.info("  python video_utils.py <video_file>")
        logger.info("  python video_utils.py --install-deps")


def update_current_scene(
    scene_name: str, schedule_path="schedule.json", audio_path: str = None
):
    """
    Updates the 'current_scene' in the schedule.json file.
    Optionally, it can also override the audio_path for the new scene.

    Args:
        scene_name (str): The key of the scene to set as current,
                          from within the '_available_scenes' in schedule.json.
        schedule_path (str): The path to the schedule.json file.
        audio_path (str, optional): If provided, this will update/add the 'audio_path'
                                     for the 'current_scene'. The scene will be marked
                                     as having audio. Defaults to None.

    Returns:
        bool: True if the update was successful, False otherwise.

    """
    if not os.path.exists(schedule_path):
        logger.info(f"Error: Schedule file not found at '{schedule_path}'")
        return False

    try:
        with open(schedule_path) as f:
            schedule_data = json.load(f)
    except json.JSONDecodeError:
        logger.info(f"Error: Could not decode JSON from '{schedule_path}'")
        return False
    except Exception as e:
        logger.info(f"An error occurred while reading the file: {e}")
        return False

    if "_available_scenes" not in schedule_data:
        logger.info("Error: '_available_scenes' key not found in schedule.json")
        return False

    if scene_name not in schedule_data["_available_scenes"]:
        logger.info(f"Error: Scene '{scene_name}' not found in '_available_scenes'.")
        available = list(schedule_data["_available_scenes"].keys())
        # Filter out keys starting with '_'
        available = [key for key in available if not key.startswith("_")]
        logger.info(f"Available scenes are: {available}")
        return False

    # Get a copy of the scene to avoid modifying the template in _available_scenes
    new_scene = schedule_data["_available_scenes"][scene_name].copy()

    # If a new audio path is provided, update the scene data
    if audio_path:
        if os.path.exists(audio_path):
            # Normalize the path for consistency in the JSON file
            normalized_audio_path = audio_path.replace("\\", "/")
            # Capitalize the drive letter for consistency (e.g., c:/ -> C:/)
            if len(normalized_audio_path) > 1 and normalized_audio_path[1] == ":":
                normalized_audio_path = (
                    normalized_audio_path[0].upper() + normalized_audio_path[1:]
                )
            new_scene["audio_path"] = normalized_audio_path
            new_scene["has_audio"] = True
            logger.info(
                f"  -> Overriding audio with: {os.path.basename(normalized_audio_path)}"
            )
        else:
            # Don't fail the whole operation, just warn the user.
            logger.info(
                f"Warning: New audio file not found at '{audio_path}'. Audio path will not be updated."
            )

    # Update the current_scene with the selected (and possibly modified) scene's data
    schedule_data["current_scene"] = new_scene

    try:
        with open(schedule_path, "w") as f:
            json.dump(schedule_data, f, indent=2)
        logger.info(
            f"Successfully updated current scene to '{scene_name}' in '{schedule_path}'."
        )
        return True
    except Exception as e:
        logger.info(f"An error occurred while writing to the file: {e}")
        return False


if __name__ == "__main__":
    # Example usage:
    # To test, uncomment one of the following lines and run this script directly.
    # Be sure to have a 'schedule.json' in the same directory.

    # update_current_scene('greeting')
    # update_current_scene('talking')
    # update_current_scene('dj_visual_only')
    # update_current_scene('non_existent_scene') # This will fail gracefully
    pass

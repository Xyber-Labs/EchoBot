from __future__ import annotations

import argparse
from time import sleep

from app_logging.logger import logger
from config.config import settings
from services.obs_stream_service.services.obs_service import OBSService
from services.obs_stream_service.services.subscene_cycler import SubsceneCycler

# --- Configuration ---
SCENE_NAME = "Scene-Music"
MEDIA_SOURCES = [
    "dj_01",
    "dj_02",
    "dj_03",
]
DURATION_SECONDS = 3


def run_media_source_cycler_for(seconds: float = 10.0, obs: OBSService = None) -> int:
    """Start the media source cycler and stop it after a duration."""
    obs = OBSService(settings.obs)
    cycler = SubsceneCycler(obs)

    try:
        cycler.start_media_source_cycling(
            scene_name=SCENE_NAME,
            media_sources=MEDIA_SOURCES,
            duration=DURATION_SECONDS,
        )
        logger.info(
            f"Cycling media sources in '{SCENE_NAME}' for {seconds:.1f} seconds..."
        )
        sleep(seconds)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.info("Stopping media source cycler...")
        cycler.stop(timeout=2.0)
        logger.info("Media source cycler stopped.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cycle through media sources in a scene."
    )
    parser.add_argument(
        "--for",
        dest="seconds",
        type=float,
        default=10.0,
        help="Run the cycler for a specific number of seconds.",
    )
    args = parser.parse_args()

    run_media_source_cycler_for(args.seconds)

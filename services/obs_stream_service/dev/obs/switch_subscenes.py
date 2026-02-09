from __future__ import annotations

from radio.services.subscene_cycler import SubsceneCycler

"""
Subscene cycling demo

Concept:
- Treat "subscenes" as variants of one conceptual scene (e.g., Scene-Music, Scene-Music-02, Scene-Music-03).
- Cycle through them in a background thread, so the main thread can stop it anytime.

Usage (run as module or from debugger):
  python -m radio.dev.obs.switch_subscenes
  python -m radio.dev.obs.switch_subscenes --for 15   # run cycler for 15 seconds, then stop
  python -m radio.dev.obs.switch_subscenes --forever  # old behavior, stop with Ctrl+C

Or import and control from your main flow:
  cycler = SubsceneCyclerService(obs)
  cycler.start(["Scene-Music", "Scene-Music-02"], duration=3)
  ... do other work ...
  cycler.stop()
"""

from time import sleep

from app_logging.logger import logger
from config.config import settings
from services.obs_stream_service.services.obs_service import OBSService

DURATION_SECONDS = 3
SUBSCENES: list[str] = [
    "Scene-Music",
    "Scene-Music-02",
]
DEFAULT_TRANSITION = "Fade"
DEFAULT_DURATION_MS = 500


# ---- Demo runner ----
def switch_subscenes_forever() -> int:
    """Run cycler until KeyboardInterrupt (Ctrl+C)."""
    obs = OBSService(settings.obs)
    cycler = SubsceneCycler(obs)

    try:
        cycler.start_scene_cycling(
            SUBSCENES,
            duration=DURATION_SECONDS,
            smooth=True,
            transition=DEFAULT_TRANSITION,
            transition_ms=DEFAULT_DURATION_MS,
        )
        logger.info("Cycling… Press Ctrl+C to stop.")
        while True:
            sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt – stopping…")
    finally:
        cycler.stop(timeout=2.0)
    return 0


def run_subscenes_for(seconds: float = 10.0) -> int:
    """Start the cycler and stop it from the main thread after `seconds`."""
    obs = OBSService(settings.obs)
    cycler = SubsceneCycler(obs)
    cycler.start_scene_cycling(
        SUBSCENES,
        duration=DURATION_SECONDS,
        smooth=True,
        transition=DEFAULT_TRANSITION,
        transition_ms=DEFAULT_DURATION_MS,
    )
    try:
        logger.info("Cycling for %.1f seconds…", seconds)
        slept = 0.0
        while slept < seconds:
            sleep(0.25)
            slept += 0.25
            # You can add your own main-thread logic here
    finally:
        cycler.stop(timeout=2.0)
    return 0


def switch_subscenes(seconds: int, obs: OBSService):
    run_subscenes_for(seconds)

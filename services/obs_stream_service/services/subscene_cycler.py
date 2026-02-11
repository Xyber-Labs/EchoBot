from __future__ import annotations

import random
import time
from collections.abc import Iterable
from enum import Enum, auto
from threading import Event, Thread
from time import sleep
from typing import Any

from app_logging.logger import logger
from config.config import settings
from services.obs_stream_service.services.obs_service import OBSService


class CycleMode(Enum):
    SCENES = auto()
    MEDIA_SOURCES = auto()
    LOCATION_CYCLING = auto()


class SubsceneCycler:
    """
    Service that rotates through a list of subscenes or media sources in the background.

    Usage for scenes:
        cycler = SubsceneCycler()
        cycler.start_scene_cycling(["Scene-A", "Scene-B"], duration=3)
        ...
        cycler.stop()

    Usage for media sources:
        cycler = SubsceneCycler()
        cycler.start_media_source_cycling("YourScene", ["Source1", "Source2"], duration=3)
        ...
        cycler.stop()
    """

    DEFAULT_TRANSITION = "Fade"
    DEFAULT_DURATION_MS = 500
    DEFAULT_POLL_INTERVAL = 0.1

    def __init__(self) -> None:
        self._obs: OBSService | None = None
        self._stop = Event()
        self._thread: Thread | None = None
        self._cfg: dict[str, Any] = {}
        self._current_index = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_scene_cycling(
        self,
        subscenes: Iterable[str],
        *,
        duration: float = 3.0,
        smooth: bool = True,
        transition: str = DEFAULT_TRANSITION,
        transition_ms: int = DEFAULT_DURATION_MS,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        subscene_list = list(subscenes)
        if not subscene_list:
            raise ValueError("Subscene list must not be empty")

        cfg: dict[str, Any] = {
            "mode": CycleMode.SCENES,
            "subscenes": tuple(subscene_list),
            "duration": float(duration),
            "smooth": bool(smooth),
            "transition": str(transition),
            "transition_ms": int(transition_ms),
            "poll_interval": float(poll_interval),
        }
        self._start_cycler(cfg)

    def start_media_source_cycling(
        self,
        scene_name: str,
        media_sources: Iterable[str],
        *,
        duration: float = 3.0,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        media_source_list = list(media_sources)
        if not media_source_list:
            raise ValueError("Media source list must not be empty")

        cfg: dict[str, Any] = {
            "mode": CycleMode.MEDIA_SOURCES,
            "scene_name": scene_name,
            "media_sources": tuple(media_source_list),
            "duration": float(duration),
            "poll_interval": float(poll_interval),
        }
        self._start_cycler(cfg)

    def start_location_cycling(
        self,
        locations: list[dict[str, Any]],
        total_duration: float,
        location_switch_duration: float,
        media_source_cycle_duration: float,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """
        Two-level cycling:
        - Outer: Switch locations every location_switch_duration
        - Inner: Switch videos within location every media_source_cycle_duration

        Args:
            locations: List of location dicts with 'scene' and 'sources' keys
            total_duration: Total time to run (e.g., 1800s = 30 minutes)
            location_switch_duration: Time per location (e.g., 300s = 5 minutes)
            media_source_cycle_duration: Time between video switches (e.g., 10s)
            poll_interval: Polling interval for checking stop signal
        """
        if not locations:
            raise ValueError("Location list must not be empty")

        cfg: dict[str, Any] = {
            "mode": CycleMode.LOCATION_CYCLING,
            "locations": locations,
            "total_duration": float(total_duration),
            "location_switch_duration": float(location_switch_duration),
            "media_source_cycle_duration": float(media_source_cycle_duration),
            "poll_interval": float(poll_interval),
        }
        self._start_cycler(cfg)

    def _start_cycler(self, cfg: dict[str, Any]) -> None:
        if self.is_running and cfg == self._cfg:
            logger.debug("CyclerService: same config, already running")
            return

        self.stop(timeout=0.5)
        self._cfg = cfg
        self._stop.clear()
        self._current_index = 0
        self._thread = Thread(target=self._run, name="CyclerService", daemon=True)
        self._thread.start()
        logger.info(f"CyclerService started in {self._cfg['mode'].name} mode")

    def stop(self, timeout: float | None = None) -> None:
        if not self.is_running:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self._obs:
            if self._cfg.get("mode") == CycleMode.MEDIA_SOURCES:
                # Cleanup: leave only the first source visible
                scene_name = self._cfg["scene_name"]
                media_sources = self._cfg["media_sources"]
                if media_sources:
                    first_source = media_sources[0]
                    self._obs.switch_on_media_source(scene_name, first_source)
                    for source in media_sources[1:]:
                        self._obs.switch_off_media_source(scene_name, source)
            elif self._cfg.get("mode") == CycleMode.LOCATION_CYCLING:
                # Stop any running media source cycler
                self._stop_media_source_cycler()
            self._obs.shutdown()
            self._obs = None
        self._thread = None
        logger.info("CyclerService stopped")

    def _run(self) -> None:
        # Create a new OBSService instance for this thread
        self._obs = OBSService(settings.obs)
        try:
            # Check if client is available before ensuring connection
            if self._obs._client is None:
                logger.error("OBS client is None, cannot ensure connection")
                return
            self._obs.ensure_connected()
        except Exception as e:
            logger.error("OBS connection check failed: %s", e)
            return

        if self._cfg["mode"] == CycleMode.SCENES:
            self._run_scene_cycler()
        elif self._cfg["mode"] == CycleMode.MEDIA_SOURCES:
            self._run_media_source_cycler()
        elif self._cfg["mode"] == CycleMode.LOCATION_CYCLING:
            self._run_location_cycler()

    def _run_scene_cycler(self):
        subscenes = self._cfg["subscenes"]
        n = len(subscenes)
        duration = self._cfg["duration"]
        poll_interval = self._cfg["poll_interval"]

        while not self._stop.is_set():
            scene = subscenes[self._current_index % n]
            logger.info("[scenes] switching to %s", scene)
            self._switch_scene(scene)

            self._sleep_interruptibly(duration, poll_interval)
            self._current_index += 1

    def _run_media_source_cycler(self):
        assert self._obs is not None
        scene_name = self._cfg["scene_name"]
        media_sources = self._cfg["media_sources"]
        n = len(media_sources)
        duration = self._cfg["duration"]
        poll_interval = self._cfg["poll_interval"]

        if n == 0:
            logger.warning("No media sources to cycle in scene '%s'", scene_name)
            return

        last_source = None
        while not self._stop.is_set():
            if n > 1:
                # Exclude the last source from the choices, then pick a random one
                possible_sources = [s for s in media_sources if s != last_source]
                current_source = random.choice(possible_sources)
            else:
                # If there's only one source, just use that one
                current_source = media_sources[0]
            last_source = current_source

            logger.info(
                "[media_sources] switching to %s in %s", current_source, scene_name
            )

            # Turn on the current source
            self._obs.switch_on_media_source(scene_name, current_source)

            # Turn off all other sources
            for source in media_sources:
                if source != current_source:
                    self._obs.switch_off_media_source(scene_name, source)

            self._sleep_interruptibly(duration, poll_interval)

    def _switch_scene(self, scene: str) -> None:
        assert self._obs is not None
        try:
            if self._cfg.get("smooth", True):
                self._obs.switch_scene_smooth(
                    scene_name=scene,
                    transition_type=self._cfg.get(
                        "transition", self.DEFAULT_TRANSITION
                    ),
                    duration_ms=self._cfg.get(
                        "transition_ms", self.DEFAULT_DURATION_MS
                    ),
                )
            else:
                self._obs.switch_scene(scene_name=scene)
        except Exception as e:
            logger.error("Failed to switch to %s: %s", scene, e)

    def _run_location_cycler(self):
        """
        Main loop for location cycling:
        1. Pick random location (exclude last)
        2. Switch to that scene
        3. Start media source cycler for that location's sources
        4. Wait location_switch_duration
        5. Repeat until total_duration elapsed
        """
        assert self._obs is not None

        locations = self._cfg["locations"]
        total_duration = self._cfg["total_duration"]
        location_switch_duration = self._cfg["location_switch_duration"]
        media_source_cycle_duration = self._cfg["media_source_cycle_duration"]
        poll_interval = self._cfg["poll_interval"]

        if not locations:
            logger.warning("No locations configured for location cycling")
            return

        start_time = time.time()
        last_location = None
        _media_source_cycler_thread: Thread | None = None
        _media_source_cycler_stop = Event()

        def _run_media_source_cycler_for_location(
            scene_name: str, sources: list[str]
        ) -> None:
            """Run media source cycler in a separate thread for current location"""
            nonlocal _media_source_cycler_stop

            _media_source_cycler_stop.clear()
            last_source = None

            while not _media_source_cycler_stop.is_set():
                n = len(sources)
                if n == 0:
                    break

                if n > 1:
                    # Exclude the last source from the choices, then pick a random one
                    possible_sources = [s for s in sources if s != last_source]
                    current_source = random.choice(possible_sources)
                else:
                    current_source = sources[0]
                last_source = current_source

                logger.info(
                    "[location_cycling] switching to %s in %s",
                    current_source,
                    scene_name,
                )

                # Turn on the current source (ignore errors if source doesn't exist)
                try:
                    self._obs.switch_on_media_source(scene_name, current_source)
                except Exception as e:
                    logger.warning(
                        f"Failed to show source '{current_source}' in '{scene_name}': {e}"
                    )
                    continue  # Skip to next iteration if source doesn't exist

                # Turn off all other sources (ignore errors if source doesn't exist)
                for source in sources:
                    if source != current_source:
                        try:
                            result = self._obs.switch_off_media_source(
                                scene_name, source
                            )
                            if not result:
                                # Source doesn't exist or failed to hide, that's okay
                                logger.debug(
                                    f"Source '{source}' not found or failed to hide in '{scene_name}', skipping"
                                )
                        except Exception as e:
                            # Source might not exist in this scene, that's okay
                            logger.debug(
                                f"Source '{source}' not found in '{scene_name}', skipping: {e}"
                            )

                # Sleep for media_source_cycle_duration (interruptible)
                slept = 0.0
                while (
                    slept < media_source_cycle_duration
                    and not _media_source_cycler_stop.is_set()
                ):
                    sleep(min(poll_interval, media_source_cycle_duration - slept))
                    slept += poll_interval

        def _stop_media_source_cycler():
            """Stop the media source cycler thread"""
            nonlocal _media_source_cycler_thread
            if _media_source_cycler_thread is not None:
                _media_source_cycler_stop.set()
                # Wait longer for thread to finish to avoid race conditions
                _media_source_cycler_thread.join(timeout=2.0)
                if _media_source_cycler_thread.is_alive():
                    logger.warning("Media source cycler thread did not stop in time")
                _media_source_cycler_thread = None

        try:
            while not self._stop.is_set():
                # Check if total duration elapsed
                elapsed = time.time() - start_time
                if elapsed >= total_duration:
                    logger.info(
                        f"Location cycling completed after {elapsed:.1f}s (target: {total_duration}s)"
                    )
                    break

                # Calculate remaining time for this location
                remaining_total = total_duration - elapsed
                current_location_duration = min(
                    location_switch_duration, remaining_total
                )

                # Pick random location (exclude last)
                available_locations = [loc for loc in locations if loc != last_location]
                if not available_locations:
                    available_locations = locations

                current_location = random.choice(available_locations)
                last_location = current_location

                scene_name = current_location["scene"]
                sources = current_location.get("sources", [])

                logger.info(
                    f"[location_cycling] switching to location '{scene_name}' "
                    f"(remaining: {remaining_total:.1f}s, this location: {current_location_duration:.1f}s)"
                )

                # Stop previous media source cycler
                _stop_media_source_cycler()

                # Switch to location scene
                try:
                    self._obs.switch_scene_smooth(scene_name)
                except Exception as e:
                    logger.error(
                        f"Failed to switch to location scene '{scene_name}': {e}"
                    )
                    # Skip to next location
                    continue

                # Start media source cycler for this location
                if sources:
                    _media_source_cycler_stop.clear()
                    _media_source_cycler_thread = Thread(
                        target=_run_media_source_cycler_for_location,
                        args=(scene_name, sources),
                        name="MediaSourceCycler",
                        daemon=True,
                    )
                    _media_source_cycler_thread.start()
                else:
                    logger.warning(f"No sources configured for location '{scene_name}'")

                # Wait for location switch duration (or until stop)
                # Start timing immediately after scene switch completes
                location_start_time = time.time()

                # Use precise timing with small sleep intervals for responsive checking
                while not self._stop.is_set():
                    elapsed_at_location = time.time() - location_start_time
                    if elapsed_at_location >= current_location_duration:
                        break
                    remaining = current_location_duration - elapsed_at_location
                    # Small sleep for responsive checking (0.05s = 50ms)
                    sleep(min(0.05, remaining))

        finally:
            # Cleanup: stop media source cycler
            _stop_media_source_cycler()

    def _stop_media_source_cycler(self):
        """Helper method to stop media source cycler (used in cleanup)"""
        # This is handled internally in _run_location_cycler
        pass

    def _sleep_interruptibly(self, duration: float, poll_interval: float):
        slept = 0.0
        while slept < duration and not self._stop.is_set():
            sleep(min(poll_interval, duration - slept))
            slept += poll_interval

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from typing import Any

import services.obs_stream_service.services.log_pusher as log_pusher
from app_logging.logger import logger
from config.config import Settings, to_container_path, to_system_path
from services.event_notifier_service.src.event_client import send_event
from services.obs_stream_service.core.ama_section import (
    generate_ama_voice, load_answered_messages)
from services.obs_stream_service.obs import (get_audio_duration_seconds,
                                             smooth_duck_background_music,
                                             smooth_restore_background_music,
                                             update_audio_source_file)
from services.obs_stream_service.services.obs_service import OBSService
from services.obs_stream_service.services.schedule_service import \
    ScheduleService
from services.obs_stream_service.services.subscene_cycler import SubsceneCycler
from services.obs_stream_service.utils.media import get_latest_audio_file

# Global variables for location-based DJ scenes
DJ_TOTAL_DURATION = 1800  # 30 minutes total (global control)
DJ_LOCATION_SWITCH_DURATION = 30  # 30 seconds per location
# DJ_TOTAL_DURATION = 300  # 10 minutes for dev/testing
# DJ_LOCATION_SWITCH_DURATION = 30  # 30 seconds per location for dev/testing


def load_playlist(dj_duration_override: int | None = None):
    playlist_path = os.path.join(os.path.dirname(__file__), "playlist.json")
    with open(playlist_path, "r") as f:
        data = json.load(f)

    variables = data.get("variables", {})
    if dj_duration_override is not None:
        variables["dj_duration"] = dj_duration_override
    playlist = data.get("playlist", [])

    # Substitute variables
    for item in playlist:
        duration = item.get("duration")
        if isinstance(duration, str) and duration.startswith("$"):
            var_name = duration[1:]
            if var_name in variables:
                item["duration"] = variables[var_name]

    return playlist


PLAYLIST = load_playlist(dj_duration_override=DJ_TOTAL_DURATION)


class RadioFlow:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        # --- Core services -------------------------------------------------- #
        self.obs = OBSService(settings.obs)
        self.schedule_service = ScheduleService()
        self.subscene_cycler = SubsceneCycler()
        self.scene_player = None  # legacy attribute for tests
        self.schedule = self.schedule_service.load()["_available_scenes"]
        self.log_pusher = log_pusher

        # --- State ---------------------------------------------------------- #
        self._running = True

    # ---------- Orchestration ---------- #

    async def start(self) -> None:
        _setup_sigint(self)
        logger.info("OBS Stream Service Started:")

        # Ensure OBS streaming is active
        logger.info("Checking OBS streaming status...")
        # if ensure_streaming():
        #     self.log_pusher.push("✅ OBS streaming is active!")
        # else:
        #     self.log_pusher.push(
        #         "⚠️ Failed to start OBS streaming. Continuing anyway..."
        #     )

        # 4. Main loop
        logger.info("Starting endless playlist cycle…")
        self.log_pusher.push(
            "Agent: Systems online. I'm ready—let's begin our journey together…"
        )
        while self._running:
            for item in PLAYLIST:
                await self._run_scene(item)
                if not self._running:
                    break

        # await self._shutdown() № TODO: make sure this is needed or not

    async def _run_scene(self, item: dict[str, Any]) -> None:
        sleep_some_time = True
        scene_name = item["scene_name"]
        current_scene = self.schedule.get(scene_name)

        # Check audio file existence for news scenes before any operations
        if scene_name in ["ai_robotics_news", "web3_news"]:
            # Extract topic from scene name (ai_robotics_news -> AI_Robotics, web3_news -> Web3)
            topic = (
                scene_name.replace("_news", "")
                .replace("ai_robotics", "AI_Robotics")
                .replace("web3", "Web3")
            )

            # --- FIX: Overwrite topic to match the exact prefix used in filenames ---
            if scene_name == "ai_robotics_news":
                topic = "audio_ai_robotics"
            # --- END FIX ---

            # --- FIX: Overwrite topic to match the exact prefix used in filenames ---
            if scene_name == "web3_news":
                topic = "audio_web3"
            # --- END FIX ---

            audio_path_env = get_latest_audio_file(topic, self.settings.media)

            if not audio_path_env or not os.path.exists(audio_path_env):
                logger.warning(
                    f"❌ Audio file not found for {scene_name}: {audio_path_env}"
                )
                logger.info(f"⏭️ Skipping {scene_name} scene and moving to next item")
                return  # Skip this scene and move to next playlist item

            # Store the environment-specific absolute path for local use (e.g., getting duration)
            current_scene["audio_path_env"] = str(audio_path_env)

            # Convert to a host-specific path ONLY for communicating with OBS
            host_audio_path = to_system_path(self.settings, str(audio_path_env))
            current_scene["audio_path_obs"] = host_audio_path
            logger.info(f"🔄 Mapped path for OBS: {host_audio_path}")

            # Update the current scene with the host audio path for OBS
            current_scene["has_audio"] = True
            logger.info(
                f"✅ Found audio file for {scene_name}: {os.path.basename(str(audio_path_env))}"
            )

        # Ensure any previous subscene cycling is stopped before starting a new item
        self.subscene_cycler.stop(timeout=0.2)

        if scene_name == "dj_visual_only":
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. Dialing up the visuals—feel the rhythm with me."
            )
        elif scene_name == "working":
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. I'm focused—scanning chat and plotting my next move…"
            )
        elif scene_name == "talking":
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. I'm here—let's talk in real time."
            )
        elif scene_name == "ai_robotics_news":
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. 📰 Fresh AI & robotics intel incoming—I'll break it down."
            )
            # Send event notification
            try:
                audio_path_env = current_scene.get("audio_path_env")
                if audio_path_env:
                    duration = get_audio_duration_seconds(audio_path_env)
                    send_event(
                        "news_section_started",
                        {
                            "scene": scene_name,
                            "audio_file": os.path.basename(str(audio_path_env)),
                            "duration_seconds": duration,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to send event notification for {scene_name}: {e}"
                )
        elif scene_name == "web3_news":
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. 📰 Web3 pulse check—let's decode the decentralized frontier."
            )
            # Send event notification
            try:
                audio_path_env = current_scene.get("audio_path_env")
                if audio_path_env:
                    duration = get_audio_duration_seconds(audio_path_env)
                    send_event(
                        "news_section_started",
                        {
                            "scene": scene_name,
                            "audio_file": os.path.basename(str(audio_path_env)),
                            "duration_seconds": duration,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to send event notification for {scene_name}: {e}"
                )
        else:
            self.log_pusher.push(
                f"Agent: Switching to '{scene_name}'. Settling in—let's enjoy this moment together."
            )

        # Check if this scene has location_config for multi-location DJ scenes
        location_config = item.get("location_config")

        if location_config:
            # For location-based scenes, skip the initial scene switch
            # The location cycler will handle scene switching internally
            logger.debug(
                f"Skipping initial scene switch for '{scene_name}' - location cycler will handle it"
            )
        else:
            # Duck BGM if the scene has its own audio
            if current_scene.get("has_audio", False):
                smooth_duck_background_music()

            self.obs.switch_scene_smooth(scene_name_real := current_scene["scene_name"])

            # Special handling for news scenes - update Voice_Music_Source in util-background-voice scene
            news_audio_path_obs = None
            if scene_name in ["ai_robotics_news", "web3_news"]:
                audio_path_obs = current_scene.get("audio_path_obs")
                # Audio file existence already checked earlier, so we can proceed
                logger.info(
                    f"Updating Voice_Music_Source with news audio: {audio_path_obs}"
                )
                try:
                    update_audio_source_file("Voice_Music_Source", audio_path_obs)
                    logger.info(
                        f"✅ Successfully updated Voice_Music_Source with {scene_name} audio"
                    )
                    news_audio_path_obs = (
                        audio_path_obs  # Store the actual audio path being played
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to update Voice_Music_Source: {e}")

        if location_config:
            # Multi-location cycling mode
            locations = location_config.get("locations", [])
            # Prioritize dev setting over playlist.json config
            # If dev setting differs from production default (300), use dev setting
            playlist_location_duration = location_config.get(
                "location_switch_duration", DJ_LOCATION_SWITCH_DURATION
            )
            if DJ_LOCATION_SWITCH_DURATION != 300:
                # Dev/testing mode: use dev setting, ignore playlist.json
                location_switch_duration = DJ_LOCATION_SWITCH_DURATION
                logger.info(
                    f"Using dev setting for location_switch_duration: {location_switch_duration}s "
                    f"(playlist.json has {playlist_location_duration}s)"
                )
            else:
                # Production mode: use playlist.json value (or default)
                location_switch_duration = playlist_location_duration

            media_source_cycle_duration = item.get("media_source_cycle", {}).get(
                "duration", 10.0
            )

            # Use global total duration
            total_duration = DJ_TOTAL_DURATION

            # Warn if location duration is too long
            if location_switch_duration >= total_duration:
                logger.warning(
                    f"⚠️ location_switch_duration ({location_switch_duration}s) >= total_duration ({total_duration}s). "
                    f"Only one location will be shown!"
                )

            logger.info(
                f"Starting location-based DJ cycling: {len(locations)} locations, "
                f"{total_duration}s total, {location_switch_duration}s per location"
            )

            # Start location cycler (handles both location and video switching)
            self.subscene_cycler.start_location_cycling(
                locations=locations,
                total_duration=total_duration,
                location_switch_duration=location_switch_duration,
                media_source_cycle_duration=float(media_source_cycle_duration),
            )

            # Wait for the location cycler to complete its total duration
            logger.info(
                f"Waiting for location cycling to complete ({total_duration}s)..."
            )
            # Wait for the full duration, regardless of cycler state
            # The cycler will stop itself when total_duration is reached
            await self._interruptible_sleep(total_duration)
            logger.info(
                f"Location cycling wait completed ({total_duration}s), stopping cycler..."
            )
            # Stop the cycler explicitly to ensure cleanup
            self.subscene_cycler.stop(timeout=0.5)
            sleep_some_time = False  # Already waited, don't sleep again
            duration = None  # Duration already handled, don't set it again
            logger.debug(
                f"Location cycling complete for '{scene_name}', continuing to next playlist item..."
            )
        else:
            # Original media source cycling mode (backward compatible)
            media_sources = item.get("media_sources") or current_scene.get(
                "media_sources"
            )

            if media_sources:
                # --- FIX: Exclude BGM sources from the cycler's control ---
                bgm_sources_to_exclude = {"Background-Music", "glitch", "UTIL_LOGS"}
                filtered_media_sources = [
                    s for s in media_sources if s not in bgm_sources_to_exclude
                ]

                cycle_cfg = item.get("media_source_cycle", {})
                self.subscene_cycler.start_media_source_cycling(
                    scene_name=scene_name_real,
                    media_sources=filtered_media_sources,
                    duration=float(cycle_cfg.get("duration", 10.0)),
                    poll_interval=float(
                        cycle_cfg.get(
                            "poll_interval", SubsceneCycler.DEFAULT_POLL_INTERVAL
                        )
                    ),
                )

        # Special 'working' scene — AMA section reply

        if scene_name == "working":  # looking for messages to reply from history
            try:
                self.log_pusher.push(
                    "Agent: Listening in—preparing an AMA voice response…"
                )

                filename = None
                try:
                    _answered_ids, answered_messages = load_answered_messages(
                        self.settings
                    )
                    filename = await generate_ama_voice(
                        self.settings, answered_messages
                    )
                except Exception as e:
                    logger.error(f"Unexpected error in AMA section generation: {e}")

                if filename:
                    self.log_pusher.push(
                        "Agent: I crafted an AMA reply—cueing the audio now."
                    )
                    voice_path_container = (
                        self.settings.media.voice_output_dir / filename
                    )
                    voice_path_host = to_system_path(
                        self.settings, str(voice_path_container)
                    )

                    # --- Start Playback Logic (mimicking news section) ---

                    # 1. Duck background music
                    smooth_duck_background_music()

                    # 2. Switch to the scene that plays the audio
                    news_scene_name = self.schedule["ai_robotics_news"]["scene_name"]
                    self.obs.switch_scene_smooth(news_scene_name)

                    # 3. Update the audio source in that scene
                    try:
                        update_audio_source_file("Voice_Music_Source", voice_path_host)
                        logger.info(
                            f"✅ Successfully updated Voice_Music_Source with AMA audio: {voice_path_host}"
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to update Voice_Music_Source: {e}")

                    # 4. Wait for the audio to finish
                    # Use the environment-specific path to get duration
                    dur = get_audio_duration_seconds(str(voice_path_container))
                    logger.info(f"AMA audio duration: {dur:.2f} seconds")
                    await asyncio.sleep(dur + 1)  # Add 1s buffer

                    # 5. Restore background music
                    smooth_restore_background_music()

                    # Prevent the default playlist duration wait
                    sleep_some_time = False
                else:
                    logger.info("No new AMA voice message was generated.")
                    # Let the scene wait for its default duration to allow chat to populate
                    sleep_some_time = True

            except Exception as e:
                logger.error(f"Error in 'working' scene: {e}")
                pass

        # For location-based scenes, duration and sleep_some_time are already set above
        # Only set duration for non-location scenes
        if not location_config:
            duration = item.get("duration")

        # Skip duration calculation if already set (location-based scenes)
        if duration is None and not location_config:
            # For news scenes, use the actual audio file being played
            audio_path_for_duration = current_scene.get("audio_path_env")

            if current_scene.get("has_audio") and audio_path_for_duration:
                # Use the environment-specific absolute path for duration calculation
                logger.info(
                    f"Scene '{scene_name}' has no duration, using audio length from: {audio_path_for_duration}"
                )
                duration = get_audio_duration_seconds(audio_path_for_duration)
                # Add a small buffer
                if duration > 0:
                    duration += 1
            else:
                # If it's a non-looping video-only scene, use its duration
                video_path_rel = current_scene.get("video_path")
                if video_path_rel and not current_scene.get("loop_video"):
                    # Try get duration from OBS for the configured source
                    video_source_name = current_scene.get("video_source_name")
                    duration_val = 0.0
                    if video_source_name:
                        duration_val = self.obs.get_media_input_duration_seconds(
                            video_source_name
                        )

                    duration = (
                        float(duration_val)
                        if duration_val and duration_val > 0
                        else 10.0
                    )
                    if duration > 0:
                        duration += 1  # Add a small buffer
                else:
                    duration = 10  # Default duration
                    logger.warning(
                        f"Scene '{scene_name}' has no duration or audio. Defaulting to {duration}s."
                    )

        if sleep_some_time:
            # Use interruptible sleep that checks _running periodically
            await self._interruptible_sleep(duration)

        # Stop cycling as we are leaving this playlist item
        self.subscene_cycler.stop(timeout=0.2)
        logger.debug(f"Completed scene '{scene_name}', moving to next playlist item...")

        if current_scene.get("has_audio", False):
            smooth_restore_background_music()

        logger.debug(f"Finished processing scene '{scene_name}', function returning...")

    # ---------- Helpers ---------- #
    async def _interruptible_sleep(self, duration: float) -> None:
        """Sleep that can be interrupted by setting _running to False."""
        sleep_interval = 0.5  # Check every 0.5 seconds
        elapsed = 0.0
        while elapsed < duration and self._running:
            remaining = min(sleep_interval, duration - elapsed)
            await asyncio.sleep(remaining)
            elapsed += remaining
            if not self._running:
                logger.info("Sleep interrupted - shutdown requested")
                break

    # ---------- Shutdown ---------- #
    async def _shutdown(self) -> None:
        logger.info("Shutting down…")
        try:
            self.log_pusher.push(
                "Agent: Powering down for now—thanks for hanging out with me!"
            )
            self.subscene_cycler.stop()
            self.obs.shutdown()
            self.obs.stop_stream()
        finally:
            logger.info("Good bye!")


# ---------- Helpers ---------- #


def _setup_sigint(runner: RadioFlow) -> None:
    """Set up signal handlers for graceful shutdown."""
    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()

            def handle_signal(sig):
                logger.info(f"Received signal {sig.name}, shutting down gracefully...")
                runner._running = False

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
            logger.debug("Signal handlers registered for SIGINT and SIGTERM")
        except RuntimeError:
            # No running loop yet, will be set up later
            logger.debug(
                "No running event loop yet, signal handlers will be set up later"
            )

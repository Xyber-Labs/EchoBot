"""Wrapper over obs_functions for uniform access."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app_logging.logger import logger
from config.config import OBSSettings
from config.config import settings as global_settings
from services.obs_stream_service.obs import \
    obs_client_manager  # TODO: not really should be imported here from there
from services.obs_stream_service.obs import (hide_source_in_scene,
                                             run_audio_matched_video_segment,
                                             set_scene_transition,
                                             show_source_in_scene,
                                             start_streaming, stop_streaming,
                                             switch_to_scene,
                                             switch_to_scene_smooth)
from services.obs_stream_service.obs.ClientManager import OBSClientManager


class OBSService:
    SERVER = "rtmp://a.rtmp.youtube.com/live2"  # TODO: move to config

    def __init__(self, settings: OBSSettings) -> None:
        self._settings = settings or global_settings
        self._client_manager = OBSClientManager(settings)
        self._client = self._client_manager.get_client()
        # TODO: do we really need it here?
        self._executor = ThreadPoolExecutor(max_workers=2)

    # ---------- Public API ---------- #
    def ensure_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("OBS client is not initialized")
        version = self._client.get_version()
        if version is None:
            raise RuntimeError("Failed to get OBS version - connection may be lost")
        logger.info("Connected to OBS (version %s)", version.obs_version)

    def set_stream_key(self, stream_key: str) -> None:
        """Set the stream key and low-latency settings."""
        logger.info("Updating stream key in OBS…")
        status = self._client.get_stream_status()
        if status.output_active:
            logger.warning("OBS already streaming – stopping before update.")
            self._client.stop_stream()
            self._wait_stream_inactive()

        resp = self._client.get_stream_service_settings()
        service_settings = resp.stream_service_settings
        service_settings["server"] = self.SERVER
        service_settings["key"] = stream_key

        self._client.set_stream_service_settings(
            resp.stream_service_type, service_settings
        )

    def set_stream_destination(self, server: str, key: str) -> None:
        """Set both RTMP server and key using current stream service type."""
        logger.info("Applying stream destination in OBS…")
        status = self._client.get_stream_status()
        if status.output_active:
            logger.warning("OBS already streaming – stopping before update.")
            self._client.stop_stream()
            self._wait_stream_inactive()

        resp = self._client.get_stream_service_settings()
        service_settings = resp.stream_service_settings
        service_settings["server"] = server
        service_settings["key"] = key
        self._client.set_stream_service_settings(
            resp.stream_service_type, service_settings
        )

    def play_scene(
        self,
        current_scene: dict[str, Any],
        duck_bg_music: bool,
        bgm_active: bool,
        forced_duration: int | None = None,
    ) -> dict[str, Any]:
        """Blocking scene start; returns cleanup info."""
        logger.info("Playing scene %s", current_scene.get("scene_name"))
        return run_audio_matched_video_segment(
            video_path=current_scene.get("video_path", ""),
            audio_path=current_scene.get("audio_path"),
            scene_name=current_scene.get("scene_name", "Scene"),
            duck_background_music=duck_bg_music,
            background_music_active=bgm_active,
            normal_bg_volume=self._settings.audio.BACKGROUND_MUSIC_VOLUME_NORMAL,
            ducked_bg_volume=self._settings.audio.BACKGROUND_MUSIC_VOLUME_DUCKED,
            forced_duration=forced_duration,
        )

    def play_scene_async(
        self,
        current_scene: dict[str, Any],
        duck_bg_music: bool,
        bgm_active: bool,
        forced_duration: int | None = None,
    ) -> Any:
        return self._executor.submit(
            self.play_scene, current_scene, duck_bg_music, bgm_active, forced_duration
        )

    def switch_scene(self, scene_name: str) -> None:
        logger.info("Switching scene to %s", scene_name)
        switch_to_scene(scene_name)

    def switch_scene_smooth(
        self,
        scene_name: str,
        transition_type: str = "Fade",
        duration_ms: int = 500,
    ) -> None:
        logger.info(
            "Smooth-switching scene to %s using %s (%d ms)",
            scene_name,
            transition_type,
            duration_ms,
        )
        switch_to_scene_smooth(scene_name, transition_type, duration_ms)

    def switch_on_media_source(self, scene_name: str, source_name: str) -> bool:
        # logger.info("Switching on media source %s in %s", source_name, scene_name)
        return show_source_in_scene(scene_name, source_name)

    def switch_off_media_source(self, scene_name: str, source_name: str) -> bool:
        # logger.info("Switching off media source %s in %s", source_name, scene_name)
        return hide_source_in_scene(scene_name, source_name)

    def start_stream(self) -> None:
        set_scene_transition("Fade", 500)
        start_streaming()

    def stop_stream(self) -> None:
        stop_streaming()
        obs_client_manager.disconnect()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def get_media_input_duration_seconds(self, input_name: str) -> float:
        """
        Return the duration (in seconds) of a media input as reported by OBS via websocket.
        Returns 0.0 if unavailable.
        """
        try:
            status = self._client.get_media_input_status(input_name)
            duration_ms = status.media_duration
            if duration_ms is None:
                logger.debug(
                    "OBS did not include media duration for input '%s'", input_name
                )
                return 0.0

            try:
                duration_sec = float(duration_ms) / 1000.0
            except Exception:
                logger.warning(
                    "Failed to convert OBS media duration for '%s': %s",
                    input_name,
                    duration_ms,
                )
                return 0.0

            logger.info(
                "OBS-reported duration for '%s': %.2f seconds", input_name, duration_sec
            )
            return duration_sec
        except Exception as e:
            logger.error("Error getting OBS media duration for '%s': %s", input_name, e)
            return 0.0

    def _wait_stream_inactive(
        self, timeout_seconds: float = 10.0, poll_interval: float = 0.2
    ) -> None:
        """Block until stream output becomes inactive or timeout occurs."""
        start_ts = time.time()
        while time.time() - start_ts < timeout_seconds:
            try:
                status = self._client.get_stream_status()
                if not status.output_active:
                    return
            except Exception:
                # If querying fails briefly, keep retrying until timeout
                pass
            time.sleep(poll_interval)
        logger.warning(
            "Timed out waiting for OBS stream to stop before applying settings."
        )


# --- Test block for direct execution ---
if __name__ == "__main__":
    obs = OBSService(global_settings.obs)  # type: ignore
    obs.ensure_connected()
    # Replace with an actual key for live testing
    stream_key = "your-stream-key-here"
    obs.set_stream_key(stream_key)
    obs.start_stream()

    import time

    time.sleep(5)  # Stream for 5 seconds
    obs.stop_stream()

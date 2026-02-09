"""Reading/writing schedule.json with signal function update_current_scene."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_logging.logger import logger
from config.config import settings
from services.obs_stream_service.utils.async_tools import with_retry
from services.obs_stream_service.utils.video import update_current_scene

SCHEDULE_PATH = settings.agent.SCHEDULE_PATH


class ScheduleService:
    def __init__(self, path: Path = SCHEDULE_PATH) -> None:
        self._path = path

    # ---------- API ---------- #
    def load(self) -> dict[str, Any]:
        try:
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to load schedule: %s", exc)
            return {}

    def save(self, data: dict[str, Any]) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @with_retry()
    async def switch_scene(self, scene_name: str) -> dict[str, Any]:
        if not update_current_scene(scene_name, schedule_path=str(self._path)):
            raise RuntimeError(f"Failed to set scene {scene_name!r}")
        return self.load()

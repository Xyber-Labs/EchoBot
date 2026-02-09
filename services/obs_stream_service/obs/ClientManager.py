import os
import threading
from typing import Optional

import obsws_python as obs

from app_logging.logger import logger
from config.config import OBSSettings as ObsSettings


class OBSClientManager:
    """
    Manages a persistent connection to the OBS WebSocket server.
    Requires explicit ObsSettings passed in for configuration.
    """

    _instance: Optional["OBSClientManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "OBSClientManager":
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(OBSClientManager, cls).__new__(cls)
                    cls._instance._client: Optional[obs.ReqClient] = None
        return cls._instance

    def __init__(self, cfg: ObsSettings) -> None:
        self._enabled = True
        self._host = cfg.OBS_HOST or "localhost"
        self._port = cfg.OBS_PORT
        self._password = cfg.OBS_PASSWORD or ""
        if not cfg.OBS_HOST or not cfg.OBS_PASSWORD:
            logger.warning(
                "OBS credentials are not fully set (OBS_HOST/OBS_PASSWORD). OBS features will be disabled until configured."
            )
            self._enabled = False

        self._lock = threading.Lock()

    def get_client(self) -> Optional[obs.ReqClient]:
        """Gets the current OBS client, connecting if necessary."""
        with self._lock:
            if os.getenv("RADIO_DISABLE_OBS") == "1":
                return None  # FOR TESTS
            if not self._enabled:
                raise RuntimeError(
                    "OBS is disabled: missing OBS_HOST/OBS_PASSWORD or RADIO_DISABLE_OBS=1"
                )
            if not self.is_connected(client_to_check=self._client):
                try:
                    logger.info(
                        f"Attempting to connect to OBS at ws://{self._host}:{self._port}"
                    )
                    self._client = obs.ReqClient(
                        host=self._host,
                        port=self._port,
                        password=self._password,
                        timeout=3,
                    )
                    logger.info("Successfully connected to OBS.")
                except Exception as e:
                    logger.error(f"Failed to connect to OBS: {e}")
                    raise ConnectionError(f"Failed to connect to OBS: {e}") from e
            return self._client

    def is_connected(self, client_to_check: Optional[obs.ReqClient] = None) -> bool:
        """Checks if the client is connected to OBS."""
        client = client_to_check or self._client
        if not client:
            return False
        try:
            client.get_version()
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        """Disconnects from the OBS server."""
        with self._lock:
            if self._client:
                self._client = None  # Let the connection close
                logger.info("Disconnected from OBS.")

    @property
    def enabled(self) -> bool:
        return self._enabled

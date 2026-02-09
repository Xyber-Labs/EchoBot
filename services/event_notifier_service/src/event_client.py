"""Client library for sending events to the event notifier service."""

import logging
import threading
from typing import Any

import requests

logger = logging.getLogger(__name__)


class EventClient:
    """Client for sending events to the event notifier service."""

    def __init__(self, service_url: str = "http://127.0.0.1:8002"):
        """
        Initialize the event client.

        Args:
            service_url: Base URL of the event notifier service
        """
        self.service_url = service_url.rstrip("/")
        self.events_endpoint = f"{self.service_url}/events"

    def send_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        timeout: int = 2,
    ) -> None:
        """
        Send an event to the event notifier service (non-blocking).

        Args:
            event_type: Type of event (e.g., "news_section_started")
            data: Additional event data
            timeout: Request timeout in seconds
        """
        payload = {"event": event_type}
        if data:
            payload["data"] = data

        def send_in_thread():
            try:
                response = requests.post(
                    self.events_endpoint,
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                logger.debug(f"✅ Event '{event_type}' sent to event notifier service")
            except requests.exceptions.Timeout:
                logger.warning(
                    f"⏱️ Timeout sending event '{event_type}' to event notifier service"
                )
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"⚠️ Failed to send event '{event_type}' to event notifier service: {e}. "
                    "Event notifier service may be down or unreachable."
                )

        # Send in background thread (fire-and-forget)
        thread = threading.Thread(target=send_in_thread, daemon=True)
        thread.start()


# Global client instance (can be imported and used directly)
_default_client: EventClient | None = None


def get_client(service_url: str | None = None) -> EventClient:
    """
    Get or create the default event client instance.

    Args:
        service_url: Optional service URL. If None, uses default.

    Returns:
        EventClient instance
    """
    global _default_client

    if _default_client is None:
        url = service_url or "http://127.0.0.1:8002"
        _default_client = EventClient(service_url=url)

    return _default_client


def send_event(event_type: str, data: dict[str, Any] | None = None) -> None:
    """
    Convenience function to send an event using the default client.

    Args:
        event_type: Type of event
        data: Additional event data
    """
    client = get_client()
    client.send_event(event_type, data)

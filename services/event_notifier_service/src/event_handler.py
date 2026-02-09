"""Core event handling and webhook forwarding logic."""

import asyncio
import logging
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles event forwarding to configured webhook URLs."""

    def __init__(self, webhook_urls: list[str] | None = None):
        """
        Initialize the event handler.

        Args:
            webhook_urls: List of webhook URLs to forward events to.
                         If None or empty, events will be logged but not forwarded.
        """
        self.webhook_urls = webhook_urls or []
        self.webhook_urls = [url.strip() for url in self.webhook_urls if url.strip()]
        logger.info(
            f"Event handler initialized with {len(self.webhook_urls)} webhook URL(s)"
        )

    def _send_webhook_sync(
        self, url: str, payload: dict[str, Any], timeout: int = 5
    ) -> bool:
        """
        Send webhook synchronously (called from thread).

        Args:
            url: Webhook URL to send to
            payload: Event payload to send
            timeout: Request timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            logger.info(f"✅ Successfully sent event to {url}")
            return True
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Timeout sending event to {url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send event to {url}: {e}")
            return False

    def forward_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        retry_count: int = 1,
    ) -> None:
        """
        Forward an event to all configured webhook URLs.

        Args:
            event_type: Type of event (e.g., "news_section_started")
            data: Additional event data
            retry_count: Number of retry attempts for failed webhooks
        """
        if not self.webhook_urls:
            logger.warning(
                f"⚠️ No webhook URLs configured. Event '{event_type}' received but not forwarded. "
                "Set EVENT_WEBHOOK_URLS in your .env file to enable webhook forwarding."
            )
            return

        # Build event payload
        payload: dict[str, Any] = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if data:
            payload.update(data)

        logger.info(
            f"📤 Forwarding event '{event_type}' to {len(self.webhook_urls)} webhook(s)"
        )
        for idx, url in enumerate(self.webhook_urls, 1):
            logger.info(f"  [{idx}/{len(self.webhook_urls)}] → {url}")

        # Send to all webhooks in parallel (non-blocking)
        for url in self.webhook_urls:
            # Use threading to avoid blocking
            import threading

            def send_in_thread():
                logger.debug(f"Sending event '{event_type}' to {url}")
                success = self._send_webhook_sync(url, payload)
                # Retry logic
                if not success and retry_count > 1:
                    for attempt in range(1, retry_count):
                        logger.info(
                            f"🔄 Retrying webhook {url} (attempt {attempt + 1}/{retry_count})"
                        )
                        import time

                        time.sleep(1)  # Simple delay between retries
                        if self._send_webhook_sync(url, payload):
                            break

            thread = threading.Thread(target=send_in_thread, daemon=True)
            thread.start()

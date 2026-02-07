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
        logger.info(f"Event handler initialized with {len(self.webhook_urls)} webhook URL(s)")

    def _format_discord_embed(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Helper: Formats a flat event payload into a rich Discord Embed.
        """
        event_type = payload.get("event", "Unknown Event")
        
        # Create the Embed structure
        embed = {
            "title": f"📢 Notification: {event_type.replace('_', ' ').title()}",
            "color": 5814783,  # Soft Blue
            "timestamp": payload.get("timestamp"),
            "fields": [],
            "footer": {"text": "EchoBot Event System"}
        }

        # Add all other data fields to the embed
        for key, value in payload.items():
            if key in ["event", "timestamp"]: 
                continue # Skip these as they are already in the header
            
            # Truncate long values to prevent errors
            val_str = str(value)
            if len(val_str) > 1000:
                val_str = val_str[:997] + "..."

            embed["fields"].append({
                "name": key.replace("_", " ").title(),
                "value": val_str,
                "inline": True
            })

        return {
            "username": "EchoBot Agent",
            "embeds": [embed]
        }

    def _send_webhook_sync(self, url: str, payload: dict[str, Any], timeout: int = 5) -> bool:
        """
        Send webhook synchronously (called from thread).
        """
        try:
            # CHECK: If this is a Discord Webhook, send a fancy Embed instead of raw JSON
            data_to_send = payload
            if "discord.com" in url or "discordapp.com" in url:
                try:
                    data_to_send = self._format_discord_embed(payload)
                except Exception as e:
                    logger.warning(f"Failed to format Discord embed, sending raw JSON: {e}")

            response = requests.post(url, json=data_to_send, timeout=timeout)
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

        logger.info(f"📤 Forwarding event '{event_type}' to {len(self.webhook_urls)} webhook(s)")
        
        # Send to all webhooks in parallel (non-blocking)
        for url in self.webhook_urls:
            # Use threading to avoid blocking
            import threading

            def send_in_thread(target_url=url, target_payload=payload):
                # We capture url/payload as defaults to safely bind them to this thread
                logger.debug(f"Sending event '{event_type}' to {target_url}")
                success = self._send_webhook_sync(target_url, target_payload)
                
                # Retry logic
                if not success and retry_count > 1:
                    for attempt in range(1, retry_count):
                        logger.info(f"🔄 Retrying webhook {target_url} (attempt {attempt + 1}/{retry_count})")
                        import time
                        time.sleep(1)  # Simple delay between retries
                        if self._send_webhook_sync(target_url, target_payload):
                            break

            thread = threading.Thread(target=send_in_thread, daemon=True)
            thread.start()

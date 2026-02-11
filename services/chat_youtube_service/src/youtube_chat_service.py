from __future__ import annotations

from typing import Any, Optional

from app_logging.logger import logger
from services.chat_youtube_service.src.youtube.models import (
    LiveChatMessage,
    LiveChatMessageListResponse,
)
from services.chat_youtube_service.src.youtube.module import YoutubeClientClass


class YoutubeChatService:
    """Handles low-level YouTube broadcast and chat operations."""

    def __init__(self, youtube_client: Optional[YoutubeClientClass]) -> None:
        self.youtube_client = youtube_client

    def get_chat_url(self) -> str:
        """Return the current watch URL if available, otherwise empty string."""
        if self.youtube_client and self.youtube_client.current_watch_url:
            return self.youtube_client.current_watch_url
        return ""

    def start_broadcast(self, title_prefix: str, force: bool = False) -> dict[str, Any]:
        """Start or reuse a YouTube broadcast and return details."""
        if not self.youtube_client:
            logger.error("YouTube client is not initialized.")
            return {}

        try:
            stream_key, watch_url, broadcast_id, is_new = (
                self.youtube_client.create_new_broadcast(title_prefix, force=force)
            )
            return {
                "stream_key": stream_key,
                "watch_url": watch_url,
                "broadcast_id": broadcast_id,
                "rtmp_url": f"rtmp://a.rtmp.youtube.com/live2/{stream_key}",
                "is_new": is_new,
            }
        except Exception as e:
            logger.error(f"Failed to start broadcast: {e}", exc_info=True)
            return {}

    def fetch_relevant_messages(
        self,
        broadcast_id: str,
        answered_ids: set[str],
    ) -> tuple[str, list[LiveChatMessage]]:
        """Fetch relevant, unanswered messages for the given broadcast."""
        live_chat_id = self.youtube_client.get_live_chat_id(broadcast_id)  # type: ignore[union-attr]
        chat_response: LiveChatMessageListResponse = (
            self.youtube_client.get_chat_messages(live_chat_id)  # type: ignore[union-attr]
        )
        messages: list[LiveChatMessage] = chat_response.items
        logger.info("Fetched %d messages from chat", len(messages))

        unanswered = [m for m in messages if m.id not in answered_ids]
        logger.info("Found %d unanswered messages", len(unanswered))

        relevant = self.youtube_client.filter_relevant_messages(unanswered)  # type: ignore[union-attr]
        logger.info("Found %d relevant messages", len(relevant))
        return live_chat_id, relevant

    def post_chat_message(self, live_chat_id: str, message: str) -> None:
        """Post a response message to YouTube live chat."""
        self.youtube_client.post_chat_message(live_chat_id, message)  # type: ignore[union-attr]

    def get_current_broadcast_id(self) -> Optional[str]:
        """Return current broadcast id from YouTube client."""
        if not self.youtube_client:
            return None
        return self.youtube_client.current_broadcast_id

    def clear_broadcast_parameters(self) -> None:
        """Clear cached broadcast parameters on the YouTube client."""
        if self.youtube_client:
            self.youtube_client.clear_broadcast_parameters()

    def get_broadcast_details(self) -> dict[str, str | None]:
        """Return active broadcast details, clearing stale cache if inactive."""
        if self.youtube_client and self.youtube_client.current_broadcast_id:
            if self.youtube_client.is_broadcast_active(
                self.youtube_client.current_broadcast_id
            ):
                return {
                    "watch_url": self.youtube_client.current_watch_url,
                    "broadcast_id": self.youtube_client.current_broadcast_id,
                    "stream_key": self.youtube_client.current_stream_key,
                    "live_chat_id": self.youtube_client.current_live_chat_id,
                    "rtmp_url": (
                        f"rtmp://a.rtmp.youtube.com/live2/{self.youtube_client.current_stream_key}"
                        if self.youtube_client.current_stream_key
                        else None
                    ),
                }

            logger.warning(
                "Broadcast %s is no longer active. Clearing details.",
                self.youtube_client.current_broadcast_id,
            )
            self.youtube_client.clear_broadcast_parameters()

        return {}

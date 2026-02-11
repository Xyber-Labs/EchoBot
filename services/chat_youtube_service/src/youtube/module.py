import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Literal

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app_logging.logger import logger
from config.config import Settings
from services.chat_youtube_service.src.youtube.exceptions import (
    YoutubeAPIError, YoutubeLiveChatNotFoundError, YoutubeVideoNotFoundError)
from services.chat_youtube_service.src.youtube.models import (
    LiveChatMessage, LiveChatMessageListResponse, Video)

settings = Settings()


class YoutubeClientClass:
    """YouTube API client with high-level abstractions for live chat operations"""

    def __init__(self, credentials: Credentials) -> None:
        """Initialize YouTube client with OAuth2 credentials"""
        self.credentials = credentials
        self._client: Any = None
        self._next_page_token_file = "state/.next_page_token"
        self._next_page_token: str | None = self._load_next_page_token()

        # Current broadcast parameters
        self._current_stream_key: str | None = None
        self._current_watch_url: str | None = None
        self._current_broadcast_id: str | None = None
        self._current_stream_id: str | None = None
        self._current_live_chat_id: str | None = None

    def _save_next_page_token(self) -> None:
        """Save the next page token to a local file"""
        try:
            if self._next_page_token is not None:
                # Create the directory if it doesn't exist
                # TODO: should be resolved by MediaManages
                import os

                os.makedirs(os.path.dirname(self._next_page_token_file), exist_ok=True)
                with open(self._next_page_token_file, "w") as f:
                    f.write(self._next_page_token)
                logger.debug(f"Saved next page token to {self._next_page_token_file}")
        except Exception as e:
            logger.error(f"Failed to save next page token: {e}")

    def _load_next_page_token(self) -> str:
        """Load the next page token from a local file if it exists"""
        try:
            with open(self._next_page_token_file) as f:
                token = f.read().strip()
                logger.debug(
                    f"Loaded next page token from {self._next_page_token_file}"
                )
                return token
        except FileNotFoundError:
            logger.debug(
                f"No next page token file found at {self._next_page_token_file}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to load next page token: {e}")
            return None

    def _initialize_client(self) -> None:
        """Initialize YouTube API client with OAuth2 credentials"""
        try:
            self._client = build("youtube", "v3", credentials=self.credentials)

        except Exception as e:
            logger.error(f"Error initializing YouTube API client: {e}")
            raise YoutubeAPIError(f"Failed to initialize YouTube API client: {e}")

    @property
    def client(self) -> Any:
        """Get the underlying YouTube API client"""
        if self._client is None:
            self._initialize_client()
        return self._client

    @property
    def current_stream_key(self) -> str | None:
        """Get current stream key"""
        return self._current_stream_key

    @property
    def current_watch_url(self) -> str | None:
        """Get current watch URL"""
        return self._current_watch_url

    @property
    def current_broadcast_id(self) -> str | None:
        """Get current broadcast ID"""
        return self._current_broadcast_id

    @property
    def current_stream_id(self) -> str | None:
        """Get current stream ID"""
        return self._current_stream_id

    @property
    def current_live_chat_id(self) -> str | None:
        """Get current live chat ID"""
        return self._current_live_chat_id

    def clear_broadcast_parameters(self) -> None:
        """Clear current broadcast parameters"""
        self._current_stream_key = None
        self._current_watch_url = None
        self._current_broadcast_id = None
        self._current_stream_id = None
        self._current_live_chat_id = None
        logger.info("Cleared broadcast parameters")

    def get_video_info(self, video_id: str) -> Video:
        """Get basic information about a video including live chat details"""
        try:
            request = self.client.videos().list(
                part="snippet,liveStreamingDetails", id=video_id
            )
            response = request.execute()
            if response["items"]:
                video_data = response["items"][0]
                return Video(**video_data)
            raise YoutubeVideoNotFoundError(f"No video found for id: {video_id}")
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise YoutubeAPIError(f"Error getting video info: {e}")

    def is_broadcast_active(self, broadcast_id: str) -> bool:
        """Check if a broadcast is still active or upcoming."""
        if not broadcast_id:
            return False
        try:
            video_info = self.get_video_info(broadcast_id)
            status = video_info.snippet.liveBroadcastContent
            is_active = status in ["live", "upcoming"]
            logger.debug(
                f"Broadcast {broadcast_id} status: {status}, active: {is_active}"
            )
            return is_active
        except YoutubeVideoNotFoundError:
            logger.info(f"Broadcast {broadcast_id} not found - treating as inactive")
            return False
        except Exception as e:
            logger.warning(
                f"Could not verify broadcast status for {broadcast_id}: {e}. Assuming broadcast is active"
            )
            return True

    def get_live_chat_id(self, video_id: str) -> str:
        """Get live chat ID for a given video ID with retry to allow chat to initialize."""
        max_wait_seconds = 30
        poll_interval_seconds = 3
        deadline = time.time() + max_wait_seconds

        while True:
            video = self.get_video_info(video_id)
            if (
                video.liveStreamingDetails
                and video.liveStreamingDetails.activeLiveChatId
            ):
                logger.info(
                    f"Found live chat ID: {video.liveStreamingDetails.activeLiveChatId}"
                )
                return video.liveStreamingDetails.activeLiveChatId

            # No chat yet; if we still have time left, sleep and retry
            if time.time() < deadline:
                logger.warning(
                    f"No active live chat yet for video ID: {video_id}. Retrying in {poll_interval_seconds}s..."
                )
                time.sleep(poll_interval_seconds)
                continue

            # Exhausted retries
            logger.warning(
                f"No active live chat found for video ID: {video_id} after waiting {max_wait_seconds}s"
            )
            raise YoutubeLiveChatNotFoundError(
                f"No active live chat found for video ID: {video_id}"
            )

    def get_chat_messages(
        self, live_chat_id: str, new_only: bool = True
    ) -> LiveChatMessageListResponse:
        """Get chat messages from live stream"""
        try:
            request_params: dict[str, Any] = {
                "liveChatId": live_chat_id,
                "part": "snippet,authorDetails",
                "maxResults": 200,
            }

            if new_only and self._next_page_token:
                request_params["pageToken"] = self._next_page_token

            request = self.client.liveChatMessages().list(**request_params)
            response = LiveChatMessageListResponse(**request.execute())
            self._next_page_token = response.nextPageToken
            self._save_next_page_token()

            return response

        except HttpError as e:
            logger.error(f"HTTP error getting chat messages: {e}")
            raise YoutubeAPIError(f"HTTP error getting chat messages: {e}")

        except Exception as e:
            logger.error(f"Error getting chat messages: {e}")
            raise YoutubeAPIError(f"Error getting chat messages: {e}")

    def post_chat_message(self, live_chat_id: str, message_text: str) -> None:
        """Post a message to the live chat"""
        try:
            message_body = {
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message_text},
                }
            }

            logger.info(f"Attempting to post message to chat ID: {live_chat_id}")
            logger.info(f"Message text: {message_text}")

            request = self.client.liveChatMessages().insert(
                part="snippet", body=message_body
            )

            response = request.execute()
            logger.info(f"Successfully posted message: {message_text}...")
            logger.info(f"Response: {response}")

        except HttpError as e:
            logger.error(f"HTTP error posting chat message: {e}")
            logger.error(f"Error details: {e.error_details}")
            raise YoutubeAPIError(f"HTTP error posting chat message: {e}")

        except Exception as e:
            logger.error(f"Error posting chat message: {e}")
            raise YoutubeAPIError(f"Error posting chat message: {e}")

    def get_broadcasts_by_status(
        self, broadcast_status: Literal["active", "upcoming"]
    ) -> list[dict[str, Any]]:
        """
        Get all broadcasts with a given status for the authenticated channel.
        Returns list of broadcast dictionaries with their details.
        """
        try:
            request = self.client.liveBroadcasts().list(
                part="snippet,status,contentDetails",
                broadcastStatus=broadcast_status,
                maxResults=50,
            )
            response = request.execute()
            return response.get("items", [])
        except HttpError as e:
            logger.error(f"HTTP error getting {broadcast_status} broadcasts: {e}")
            raise YoutubeAPIError(
                f"HTTP error getting {broadcast_status} broadcasts: {e}"
            )
        except Exception as e:
            logger.error(f"Error getting {broadcast_status} broadcasts: {e}")
            raise YoutubeAPIError(f"Error getting {broadcast_status} broadcasts: {e}")

    def get_latest_active_broadcast(self) -> dict[str, Any] | None:
        """
        Get the most recent broadcast that is either 'active' or 'upcoming'.
        Prioritizes 'active' broadcasts over 'upcoming' ones.
        Returns None if no such broadcasts are found.
        """
        try:
            # First, check for active broadcasts
            active_broadcasts = self.get_broadcasts_by_status("active")
            if active_broadcasts:
                active_broadcasts.sort(
                    key=lambda x: x["snippet"]["publishedAt"], reverse=True
                )
                logger.info(
                    f"Found {len(active_broadcasts)} active broadcast(s). Reusing the latest one."
                )
                return active_broadcasts[0]

            # If no active broadcasts, check for upcoming ones
            upcoming_broadcasts = self.get_broadcasts_by_status("upcoming")
            if upcoming_broadcasts:
                upcoming_broadcasts.sort(
                    key=lambda x: x["snippet"]["publishedAt"], reverse=True
                )
                logger.info(
                    f"Found {len(upcoming_broadcasts)} upcoming broadcast(s). Reusing the latest one."
                )
                return upcoming_broadcasts[0]

            return None
        except Exception as e:
            logger.error(f"Error getting latest active broadcast: {e}")
            return None

    def create_new_broadcast(
        self, title_prefix: str = "My Automated Stream", force: bool = False
    ) -> tuple[str, str, str, bool]:
        """
        Create a new YouTube live broadcast and stream, bind them together,
        and return (stream_key, watch_url, broadcast_id, is_new).

        If 'force' is False and an active broadcast already exists, returns its
        parameters instead of creating a new one.
        """
        if not force:
            # First, check if there's already an active broadcast
            existing_broadcast = self.get_latest_active_broadcast()
            if existing_broadcast:
                bcast_id = existing_broadcast["id"]
                watch_url = f"https://www.youtube.com/watch?v={bcast_id}"

                # Get stream details for the existing broadcast
                try:
                    stream_details = (
                        self.client.liveBroadcasts()
                        .list(part="contentDetails", id=bcast_id)
                        .execute()
                    )

                    if stream_details["items"]:
                        stream_id = stream_details["items"][0]["contentDetails"][
                            "boundStreamId"
                        ]

                        # Get stream key
                        stream_info = (
                            self.client.liveStreams()
                            .list(part="cdn", id=stream_id)
                            .execute()
                        )

                        if stream_info["items"]:
                            stream_key = stream_info["items"][0]["cdn"][
                                "ingestionInfo"
                            ]["streamName"]

                            # Save parameters to object
                            self._current_stream_key = stream_key
                            self._current_watch_url = watch_url
                            self._current_broadcast_id = bcast_id
                            self._current_stream_id = stream_id
                            self._current_live_chat_id = self.get_live_chat_id(bcast_id)

                            logger.info("Using existing active broadcast: %s", bcast_id)
                            return stream_key, watch_url, bcast_id, False

                except Exception as e:
                    logger.warning(
                        f"Could not get stream details for existing broadcast: {e}"
                    )
                    # Fall through to create new broadcast

        # No active broadcast found or force=True, create a new one
        now = datetime.utcnow()
        title = f"{title_prefix} – {now:%Y-%m-%d %H:%M:%S}"

        logger.info(
            "Creating new YouTube broadcast «%s» with privacy status: %s",
            title,
            settings.youtube.PRIVACY_STATUS,
        )

        try:
            # 1. Broadcast
            bcast_resp = (
                self.client.liveBroadcasts()
                .insert(
                    part="snippet,status,contentDetails",
                    body={
                        "snippet": {
                            "title": title,
                            "scheduledStartTime": (
                                now + timedelta(seconds=5)
                            ).isoformat()
                            + "Z",  # noqa
                        },
                        "status": {"privacyStatus": settings.youtube.PRIVACY_STATUS},
                        "contentDetails": {
                            "enableAutoStart": True,
                            "enableAutoStop": True,
                            "latencyPreference": "low",
                        },
                    },
                )
                .execute()
            )
            bcast_id = bcast_resp["id"]
            watch_url = f"https://www.youtube.com/watch?v={bcast_id}"

            # 2. Stream
            stream_resp = (
                self.client.liveStreams()
                .insert(
                    part="snippet,cdn",
                    body={
                        "snippet": {"title": title},
                        "cdn": {
                            "ingestionType": "rtmp",
                            "resolution": "1080p",
                            "frameRate": "30fps",
                        },
                    },
                )
                .execute()
            )
            stream_id = stream_resp["id"]
            stream_key = stream_resp["cdn"]["ingestionInfo"]["streamName"]

            # 3. Bind
            self.client.liveBroadcasts().bind(
                part="id,contentDetails", id=bcast_id, streamId=stream_id
            ).execute()

            # Save parameters to object
            self._current_stream_key = stream_key
            self._current_watch_url = watch_url
            self._current_broadcast_id = bcast_id
            self._current_stream_id = stream_id
            self._current_live_chat_id = self.get_live_chat_id(bcast_id)

            logger.info("Broadcast ready (%s). Stream key: %s", bcast_id, stream_key)
            return stream_key, watch_url, bcast_id, True
        except HttpError as e:
            logger.error(f"HTTP error creating broadcast: {e}")
            raise YoutubeAPIError(f"HTTP error creating broadcast: {e}")
        except Exception as e:
            logger.error(f"Error creating broadcast: {e}")
            raise YoutubeAPIError(f"Error creating broadcast: {e}")

    def filter_relevant_messages(
        self, messages: list[LiveChatMessage]
    ) -> list[LiveChatMessage]:
        """Filter messages so agent won't answer to itself"""
        if settings.youtube.DEBUG:
            return messages

        relevant_messages: list[LiveChatMessage] = [
            message
            for message in messages
            if not (
                message.authorDetails.isChatOwner
                # Removed filtering for moderators and sponsors
                # message.authorDetails.isChatModerator or
                # message.authorDetails.isChatSponsor
            )
        ]

        return relevant_messages

    def _parse_chat_message(self, item: dict[str, Any]) -> dict[str, Any]:
        """Parse a chat message item from YouTube API response"""
        snippet: dict[str, Any] = item["snippet"]
        author_details: dict[str, Any] = item["authorDetails"]

        return {
            "message_id": item["id"],
            "author_name": author_details.get("displayName", "Unknown"),
            "author_channel_id": author_details.get("channelId"),
            "message_text": snippet.get("textMessageDetails", {}).get(
                "messageText", ""
            ),
            "published_at": snippet.get("publishedAt"),
            "type": snippet.get("type", "textMessageEvent"),
        }


@lru_cache(maxsize=1)
def get_youtube_client(credentials: Credentials) -> YoutubeClientClass:
    """Get cached YouTube client instance using OAuth2 credentials"""
    return YoutubeClientClass(credentials)

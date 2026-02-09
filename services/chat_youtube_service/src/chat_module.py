from __future__ import annotations

import asyncio
import datetime
import json
import random
import re
import signal
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from app_logging.logger import logger
from config.config import Settings
from LLM import load_agent_personality, load_json
from LLM.llm_utils import initialize_llm
from services.chat_youtube_service.src.agent.graph import \
    Youtube_Responder_Agent
from services.chat_youtube_service.src.youtube.exceptions import (
    YoutubeClientError, YoutubeLiveChatNotFoundError,
    YoutubeVideoNotFoundError)
from services.chat_youtube_service.src.youtube.models import (
    LiveChatMessage, LiveChatMessageListResponse)
from services.chat_youtube_service.src.youtube.module import YoutubeClientClass
from voice.generate import generate_voice


class ChatService:
    """
    Automated service for responding in a YouTube live chat.

    ▸ Accepts a ready-to-use YoutubeClientClass (with OAuth2 authorization).
    ▸ Stores a history of already processed messages in a JSON file
      `memory_file` to avoid duplicate responses.
    ▸ Can operate synchronously (respond_to_chat_once) or
      run in a separate thread (start_async).
    """

    def __init__(
        self,
        youtube_client: Optional[YoutubeClientClass],
        youtube_responder_agent: Youtube_Responder_Agent,
        memory_file: Path,
        settings: Settings,
        max_workers: int = 1,
    ) -> None:
        self.youtube_client = youtube_client
        self.youtube_responder_agent = youtube_responder_agent
        self.memory_file = memory_file
        self.settings = settings
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._future: Future[bool] | None = None
        self.should_stop: bool = False

    def get_chat_url(self) -> str:
        """
        Return the current watch URL if available, otherwise empty string.
        """
        if self.youtube_client and self.youtube_client.current_watch_url:
            return self.youtube_client.current_watch_url
        return ""

    def start_broadcast(self, title_prefix: str, force: bool = False) -> dict[str, Any]:
        """
        Starts a new YouTube broadcast.

        Args:
            title_prefix: The title prefix for the new broadcast.
            force: If True, it will try to create a new broadcast even if one is active.

        Returns:
            A dictionary with broadcast details and a flag indicating if it's a new broadcast.
        """
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

    # ---------- Helper Methods ---------- #

    def _fetch_relevant_messages(
        self, broadcast_id: str
    ) -> tuple[str, list[LiveChatMessage], list[dict], set[str]]:
        live_chat_id: str = self.youtube_client.get_live_chat_id(broadcast_id)  # type: ignore[union-attr]
        chat_response: LiveChatMessageListResponse = (
            self.youtube_client.get_chat_messages(live_chat_id)  # type: ignore[union-attr]
        )
        messages: list[LiveChatMessage] = chat_response.items
        logger.info("Fetched %d messages from chat", len(messages))

        answered_ids, answered_messages = self.load_memory()
        unanswered = [m for m in messages if m.id not in answered_ids]
        logger.info("Found %d unanswered messages", len(unanswered))

        relevant = self.youtube_client.filter_relevant_messages(unanswered)  # type: ignore[union-attr]
        logger.info("Found %d relevant messages", len(relevant))

        return live_chat_id, relevant, answered_messages, answered_ids

    async def _reply_to_messages(
        self,
        live_chat_id: str,
        messages: list[LiveChatMessage],
        answered_messages: list[dict[str, object]],
        answered_ids: set[str],
    ) -> list[dict[str, object]]:
        if not self.youtube_client:
            logger.warning(
                "Youtube clint not provided. Probably system in development mode"
            )
            return []

        # Build chat history with author names and better structure
        chat_history = [
            {
                "author": msg.get("author", "Unknown"),
                "message": msg.get("message"),
                "agent_reply_text": msg.get("agent_reply_text"),
            }
            for msg in answered_messages
            if msg.get("agent_reply_text")
        ][-15:]  # Increased from 10 to 15 for better context

        newly_answered = []
        for msg in messages:
            filename = None
            is_voice = "[voice]" in msg.snippet.displayMessage
            answer_text = None
            formatted_answer = None

            logger.debug(
                "Processing message '%s' from '%s'",
                msg.snippet.displayMessage,
                msg.authorDetails.displayName,
            )

            try:
                # Include recent messages from the same user for better conversation tracking
                current_user_recent_messages = [
                    {
                        "author": hist_msg.get("author", "Unknown"),
                        "message": hist_msg.get("message"),
                        "agent_reply_text": hist_msg.get("agent_reply_text"),
                    }
                    for hist_msg in answered_messages
                    if hist_msg.get("author") == msg.authorDetails.displayName
                ][-5:]  # Last 5 messages from this user

                response = await self.youtube_responder_agent.graph.ainvoke(
                    {
                        "message": msg.snippet.displayMessage,
                        "author": msg.authorDetails.displayName,
                        "chat_history": chat_history,
                        "user_recent_messages": current_user_recent_messages,
                    }
                )

                if isinstance(response, dict) and response.get("agent_reply_text"):
                    answer_text = response["agent_reply_text"]
                    author_name = msg.authorDetails.displayName
                    logger.debug(f"Original LLM reply: {answer_text}")
                    logger.debug(f"Author name: {author_name}")

                    # CRITICAL: Remove ALL @ symbols and @mentions from the LLM's reply
                    # The system will add @{author} automatically, so any @ in the reply causes double @@

                    # First, remove any @mentions that match the author's name (most common case)
                    # Pattern: @ or @@ followed by author name, optionally followed by comma/space
                    answer_text = re.sub(
                        rf"@+{re.escape(author_name)}[,\s]*",
                        "",
                        answer_text,
                        flags=re.IGNORECASE,
                    )

                    # Remove ALL other @mentions (any @ followed by word characters)
                    answer_text = re.sub(r"@+[\w_]+[,\s]*", "", answer_text)

                    # Remove any remaining standalone @ symbols
                    answer_text = answer_text.replace("@", "").strip()

                    # Additional safeguard: if reply starts with author's name (without @), remove it
                    # This prevents "@Author, Author, message" pattern
                    if answer_text.lower().startswith(author_name.lower()):
                        answer_text = re.sub(
                            rf"^{re.escape(author_name)}[,\s]*",
                            "",
                            answer_text,
                            flags=re.IGNORECASE,
                        ).strip()

                    # Clean up formatting: remove extra spaces, commas, etc.
                    answer_text = re.sub(r"\s+", " ", answer_text).strip()
                    answer_text = re.sub(
                        r",\s*,", ",", answer_text
                    )  # Remove double commas
                    answer_text = answer_text.strip(
                        ","
                    ).strip()  # Remove leading/trailing commas

                    logger.debug(f"Cleaned LLM reply: {answer_text}")

                    # Now add the @mention at the start
                    # Ensure author_name doesn't already have an @ prefix
                    clean_author_name = author_name.lstrip("@")
                    formatted_answer = f"@{clean_author_name}, {answer_text}"

                    logger.info(f"Final formatted answer: {formatted_answer}")

                    if is_voice:
                        filename = generate_voice(
                            formatted_answer,
                            api_config=self.settings.elevenlabs,
                            file_path=self.settings.media.voice_output_dir,
                        )
                        logger.info(f"Voice generated with filename: {filename}")
                else:
                    logger.warning("Scam detected or unexpected response for message ")
            except Exception as e:
                logger.error("Error generating response for message %s: %s", msg.id, e)

            if formatted_answer:
                try:
                    await asyncio.sleep(random.randint(3, 7))
                    if not is_voice:
                        self.youtube_client.post_chat_message(  # type: ignore[union-attr]
                            live_chat_id, formatted_answer
                        )
                    logger.info("Posted response to message id=%s", msg.id)
                except Exception as e:
                    logger.error("Error posting response for message %s: %s", msg.id, e)

            newly_answered.append(
                {
                    "id": msg.id,
                    "author": msg.authorDetails.displayName,
                    "message": msg.snippet.displayMessage,
                    "timestamp": msg.snippet.publishedAt,
                    "voice": bool(is_voice and answer_text),
                    "spoken": False,
                    "filename": filename,
                    "agent_reply_text": answer_text,
                }
            )
            answered_ids.add(msg.id)
        return newly_answered

    # ---------- Public API ---------- #

    def respond_to_chat_once_async(self, broadcast_id: str) -> None:
        if self._future and not self._future.done():
            return
        self._future = self._executor.submit(
            lambda: asyncio.run(self.respond_to_chat_once(broadcast_id))
        )

    async def respond_to_chat_once(self, broadcast_id: str) -> bool:
        """
        Fetches and responds to chat messages for a single iteration.

        Returns:
            bool: True if successful, False if the broadcast is no longer valid.
        """
        try:
            (
                live_chat_id,
                relevant_messages,
                answered_messages,
                answered_ids,
            ) = self._fetch_relevant_messages(broadcast_id)

            if not relevant_messages:
                logger.info("No new relevant messages to answer.")
                return True

            newly_answered = await self._reply_to_messages(
                live_chat_id, relevant_messages, answered_messages, answered_ids
            )

            all_messages = newly_answered + answered_messages

            logger.info(f"Answered {len(newly_answered)} new messages")
            logger.info("Saving answered messages to memory file")
            self._save_memory(all_messages)
            return True

        except (YoutubeVideoNotFoundError, YoutubeLiveChatNotFoundError) as e:
            logger.error(
                f"Broadcast '{broadcast_id}' is no longer valid or has ended: {e}"
            )
            return False  # Signal to the run loop that this broadcast ID is dead
        except YoutubeClientError as e:
            logger.warning("YouTube client error (may be transient): %s", e)
            return True  # Don't clear broadcast on transient errors
        except Exception as e:
            logger.error("Unexpected chat‑service error: %s", e, exc_info=True)
            return True  # Don't clear broadcast on unexpected errors

    def is_done(self) -> bool:
        return bool(self._future and self._future.done())

    def success(self) -> bool:
        return bool(self._future and self._future.done() and self._future.result())

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    async def run(self, install_signal_handlers: bool = False) -> None:
        """Run the chat service continuously in the background."""
        self.should_stop = False
        last_heartbeat = 0
        poll_interval_seconds = self.settings.youtube.POLL_INTERVAL_SECONDS

        if install_signal_handlers:
            loop = asyncio.get_running_loop()

            def signal_handler():
                logger.info("Received signal. Shutting down chat service...")
                self.should_stop = True

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, signal_handler)
                except (ValueError, RuntimeError) as e:
                    logger.warning(f"Could not install signal handler for {sig}: {e}")

        logger.info("Starting chat service continuous runner...")

        while not self.should_stop:
            try:
                if (
                    self.youtube_client
                    and self.settings.youtube.YOUTUBE_ENABLED
                    and self.youtube_client.current_broadcast_id
                ):
                    broadcast_id = self.youtube_client.current_broadcast_id
                    is_broadcast_still_valid = await self.respond_to_chat_once(
                        broadcast_id
                    )
                    if not is_broadcast_still_valid:
                        logger.error(
                            f"CRITICAL: Broadcast {broadcast_id} is no longer valid. Clearing details and entering disconnected state."
                        )
                        logger.error(
                            "Service will now return 503 on healthcheck. Manual restart required."
                        )
                        self.youtube_client.clear_broadcast_parameters()

                else:
                    logger.debug(
                        "YouTube client not initialized, disabled, or no active broadcast. Sleeping..."
                    )

                current_time = time.time()
                if current_time - last_heartbeat > 300:
                    if self.youtube_client and self.youtube_client.current_broadcast_id:
                        logger.info(
                            f"Chat service heartbeat: Active on broadcast {self.youtube_client.current_broadcast_id}"
                        )
                    else:
                        logger.warning(
                            "Chat service heartbeat: Running but NOT connected to any broadcast"
                        )
                    last_heartbeat = current_time

                for _ in range(poll_interval_seconds):
                    if self.should_stop:
                        break
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Critical error in chat service loop: {e}", exc_info=True)
                if self.youtube_client:
                    self.youtube_client.clear_broadcast_parameters()
                logger.info("Pausing for 60 seconds before retry...")
                await asyncio.sleep(60)

        logger.info("Chat service shutdown complete")
        self.shutdown()

    # ---------- Internal Methods ---------- #

    def load_memory(self) -> tuple[set[str], list[dict[str, object]]]:
        logger.info(f"Opening memory: {self.memory_file}")
        try:
            with open(self.memory_file, encoding="utf-8") as fp:
                data: list[dict[str, object]] = json.load(fp)
            return {item["id"] for item in data}, data
        except (FileNotFoundError, json.JSONDecodeError):
            return set(), []

    def _save_memory(self, data: list[dict[str, object]]) -> None:
        logger.info(f"Saving memory: {self.memory_file}")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)

    def get_broadcast_details(self) -> dict[str, str | None]:
        """
        Return the current broadcast details if available, and verify the broadcast is active.
        """
        if self.youtube_client and self.youtube_client.current_broadcast_id:
            # Actively verify the broadcast is still valid
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
            else:
                # The broadcast is no longer active, so clear the stale details
                logger.warning(
                    f"Broadcast {self.youtube_client.current_broadcast_id} is no longer active. Clearing details."
                )
                self.youtube_client.clear_broadcast_parameters()

        return {}


def create_chat_service(settings: Settings) -> ChatService:
    """Create instances and return ChatService without side effects."""
    LLM_SPARE = initialize_llm(llm_type="spare", raise_on_error=True)
    LLM = initialize_llm(llm_type="main", raise_on_error=True)
    if LLM_SPARE:
        LLM = LLM.with_fallbacks([LLM_SPARE])
    LLM_THINKING = initialize_llm(llm_type="thinking", raise_on_error=True)
    if LLM_THINKING:
        LLM_THINKING = LLM_THINKING.with_fallbacks([LLM_SPARE])
    LLM_VALIDATION = initialize_llm(llm_type="validation", raise_on_error=True)
    if LLM_VALIDATION:
        LLM_VALIDATION = LLM_VALIDATION.with_fallbacks([LLM_SPARE])

    try:
        logger.info("Loading agent personality...")
        agent_personality = load_agent_personality(
            settings.agent.agent_personality_path
        )
        logger.info("Loading agent disclaimer...")
        youtube_disclaimer = load_json(settings.agent.youtube_disclaimer)
        logger.info("Agent disclaimer loaded.")
        logger.info("Agent personality loaded.")
        logger.info("Loading agent knowledge...")
        agent_knowledge = load_json(settings.agent.agent_knowledge_path)
        logger.info("Agent knowledge loaded.")
        logger.info("Loading agent chat rules...")
        chat_rules = load_json(settings.agent.agent_chat_rules_path)
        logger.info("Agent chat rules loaded.")
    except Exception as e:
        logger.error(f"Error loading agent personality or knowledge: {e}")
        sys.exit(1)

    youtube_client = None
    if settings.youtube.YOUTUBE_ENABLED:
        logger.info("Initializing YouTube Client...")
        creds = settings.youtube.credentials
        if creds:
            youtube_client = YoutubeClientClass(creds)
            logger.info("YouTube Client Initialized.")
        else:
            logger.error(
                "Failed to get YouTube credentials. Disabling YouTube features."
            )

    youtube_responder_agent = Youtube_Responder_Agent(
        agent_name=agent_personality["agent"]["identity"]["name"],
        llm=LLM,
        llm_thinking=LLM_THINKING,
        llm_validation=LLM_VALIDATION,
        agent_personality=agent_personality,
        agent_knowledge=agent_knowledge,
        settings=settings,
        chat_rules=chat_rules,
        youtube_disclaimer=youtube_disclaimer,
    )

    memory_file_path = settings.media.memory_output_dir / "memory.json"

    chat_service = ChatService(
        youtube_client=youtube_client,
        youtube_responder_agent=youtube_responder_agent,
        memory_file=memory_file_path,
        settings=settings,
    )
    return chat_service

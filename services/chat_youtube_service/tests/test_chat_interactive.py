# This is the test script for testing the youtube interface chat functional
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import services.obs_stream_service.services.log_pusher as log_pusher
from app_logging.logger import logger
from config.config import Settings
from LLM import initialize_llm
from services.chat_youtube_service.src.agent.graph import \
    Youtube_Responder_Agent
from services.chat_youtube_service.src.chat_module import ChatService
from services.chat_youtube_service.src.youtube.module import get_youtube_client
from services.obs_stream_service.services.schedule_service import \
    ScheduleService

# Add project root to path to allow imports from other modules
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

# Store project root for later use
project_root = Path(__file__).resolve().parent.parent.parent

# lets initialise the LLMs
logger.info("Loading configuration...")
try:
    settings = Settings()
    logger.info("Configuration loaded.")
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    sys.exit(1)

# check if directory exist
logger.info("Checking media directories...")

# Ensure all necessary media directories exist
Path(settings.media.voice_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.news_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.state_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.memory_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.videos_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.google_drive_music_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.suno_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.soundcloud_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.media.config_dir).mkdir(parents=True, exist_ok=True)


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


class MockOBSService:
    """A mock OBS service that logs scene switches instead of performing them."""

    def switch_scene_smooth(self, scene_name: str) -> None:
        logger.info(f"[Mock OBS] Switching to scene: {scene_name}")


class MockBGMService:
    """A mock BGM service that logs voice initializations."""

    def init_voice_in_scene(self, voice_path: str) -> bool:
        logger.info(f"[Mock BGM] Initializing voice in scene with path: {voice_path}")
        return True


class ChatTester:
    """A test class for running YouTube chat functionalities in isolation."""

    def __init__(
        self, settings: Settings, youtube_responder_agent: Youtube_Responder_Agent
    ) -> None:
        """
        Initializes the ChatTester with settings and necessary services.
        It sets up a YouTube client and chat service, along with mock services
        for OBS and BGM to allow for isolated testing.
        """
        self.settings = settings
        # --- YouTube ------------------------------------------------------- #
        if settings.youtube.YOUTUBE_ENABLED:
            # Add a check for the refresh token
            if not settings.youtube.YOUTUBE_REFRESH_TOKEN:
                logger.error(
                    "YouTube refresh token is missing. Please set YOUTUBE_REFRESH_TOKEN in your .env file."
                )
                sys.exit(1)

            creds = settings.youtube.credentials
            if not creds:
                logger.error("Could not initialize YouTube credentials. Exiting.")
                sys.exit(1)
            self.youtube = get_youtube_client(creds)
            self.chat = ChatService(
                self.youtube,
                youtube_responder_agent,
                settings.media.memory_output_dir / "memory.json",
                settings=settings,
            )
        else:
            self.youtube = None
            self.chat = None
            logger.warning(
                "YouTube is not enabled in settings. Chat testing will not work."
            )
            return

        # --- Mock or real services ------------------------------------------ #
        self.obs = MockOBSService()
        self.schedule_service = ScheduleService()
        self.schedule = self.schedule_service.load()["_available_scenes"]
        self.bgm = MockBGMService()
        self.log_pusher = log_pusher

    async def test_chat_logic(self) -> None:
        """
        Executes the main chat testing logic.
        This method fetches relevant messages, replies to them, handles voice
        responses, and logs the process, mimicking the behavior of the main application flow.
        """
        if not self.chat:
            logger.error("ChatService not initialized.")
            return

        # try:
        #     self.log_pusher.push("Scanning for new messages in the crowd…")
        #     broadcast_id = self.chat.youtube_client.current_broadcast_id
        #     if broadcast_id:
        #         await self.chat.respond_to_chat_once(broadcast_id)
        #     else:
        #         logger.warning("No active broadcast found. Skipping chat processing.")

        # except YoutubeClientError as e:
        #     logger.error(f"YouTube client error while replying to chat: {e}")

        # except Exception as e:
        #     logger.error(f"Unexpected error in chat reply flow: {e}")

        # Section to test AMA
        try:
            # Load the chat history from memory file
            answered_ids, answered_messages = self.chat._load_memory()
            # Use current broadcast ID from YouTube client
            broadcast_id = self.chat.youtube_client.current_broadcast_id or ""
            await self.chat.AMA_ask_me_anything_section(broadcast_id, answered_messages)
        except Exception as e:
            logger.error(f"Unexpected error in AMA section: {e}")


async def main() -> None:
    """Main function to run the chat tester."""
    # Ensure the state directory exists
    (settings.media.state_output_dir).mkdir(exist_ok=True)

    main_settings = Settings()

    agent_personality = json.loads(
        (main_settings.agent_data.agent_personality_path).read_text()
    )
    agent_knowledge = json.loads(
        (main_settings.agent_data.agent_knowledge_path).read_text()
    )
    youtube_disclaimer = json.loads(
        (main_settings.agent_data.youtube_disclaimer).read_text()
    )

    youtube_responder_agent = Youtube_Responder_Agent(
        agent_name="Test Agent",
        llm=LLM,
        llm_thinking=LLM_THINKING,
        llm_validation=LLM_VALIDATION,
        agent_personality=agent_personality,
        agent_knowledge=agent_knowledge,
        settings=settings,
        youtube_disclaimer=youtube_disclaimer,
    )

    tester = ChatTester(settings, youtube_responder_agent)

    while True:
        await tester.test_chat_logic()
        logger.info("Waiting for 10 seconds before next chat poll...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user. Shutting down.")

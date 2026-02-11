#!/usr/bin/env python
import asyncio
import signal
import sys
import time

import schedule

from app_logging.logger import logger
# Removed unused typing imports
from config.config import Settings
from LLM import initialize_llm, load_agent_personality, load_json
from services.music_service.media.media_service import initialize_media_once
from services.music_service.music_agent.music_graph import MusicGeneration
from services.music_service.music_agent.state import MusicGenerationState

# Load the configuration
logger.info("Loading configuration...")
try:
    settings = Settings()
    logger.info("Configuration loaded.")
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    sys.exit(1)

# Initialize the Main LLM, with fallback to Spare on failure
LLM = None
try:
    LLM = initialize_llm(llm_type="main", raise_on_error=True)
    if LLM:
        logger.info(f"Main LLM initialized: {type(LLM).__name__}")
except Exception as e:
    logger.warning(f"Failed to initialize main LLM: {e}")
    logger.warning("Attempting to use spare LLM as main.")

# Initialize the Spare LLM (only if main LLM failed or to set as fallback)
LLM_SPARE = initialize_llm(llm_type="spare", raise_on_error=False)
if LLM_SPARE:
    logger.info(f"Spare LLM initialized: {type(LLM_SPARE).__name__}")

# If main LLM failed, use spare as main
if not LLM and LLM_SPARE:
    LLM = LLM_SPARE
    logger.info("Using spare LLM as the main LLM.")
# If main LLM succeeded, add spare as fallback
elif LLM and LLM_SPARE:
    LLM = LLM.with_fallbacks([LLM_SPARE])
    logger.info("Main LLM with fallbacks is ready.")

# If still no LLM, we can't continue
if not LLM:
    logger.critical("Could not initialize any LLM. Exiting.")
    sys.exit(1)

# Initialize the Thinking LLM (returns None on failure)
LLM_THINKING = initialize_llm(llm_type="thinking", raise_on_error=False)
if LLM_THINKING:
    logger.info(f"Thinking LLM initialized: {type(LLM_THINKING).__name__}")
    # Optionally, give the thinking LLM a fallback as well
    if LLM_SPARE:
        LLM_THINKING = LLM_THINKING.with_fallbacks([LLM_SPARE])
        logger.info("Thinking LLM with fallbacks is ready.")
else:
    logger.warning("Thinking LLM could not be initialized. Continuing without it.")

# Initialize the Validation LLM (returns None on failure)
LLM_VALIDATION = initialize_llm(llm_type="validation", raise_on_error=False)
if LLM_VALIDATION:
    logger.info(f"Validation LLM initialized: {type(LLM_VALIDATION).__name__}")
else:
    logger.warning("Validation LLM could not be initialized. Continuing without it.")


async def main():
    # Loading files
    try:
        agent_personality = load_agent_personality(
            settings.agent.agent_personality_path
        )
        music_style = load_json(settings.agent.agent_music_style_path)
        music_memory = load_json(settings.media.music_memory_path)
        agent_knowledge = load_json(settings.agent.agent_knowledge_path)
        history_file_path = settings.media.music_memory_path
        agent_name = agent_personality["agent"]["identity"]["name"]
        call_back_url = settings.suno.SUNO_CALLBACK_URL
        logger.info(
            "Successfully loaded all files including agent personality, music style, music memory and history file path"
        )
    except Exception as e:
        logger.error(
            f"Error loading files, stopping the program, please ensure the pathes are set correctly: {e}"
        )
        sys.exit(1)
    # -----------------------------------------------------------#

    # Initialize the agent
    agent = MusicGeneration(
        LLM,
        LLM_THINKING,
        music_memory=music_memory,
        music_style=music_style,
        agent_personality=agent_personality,
        agent_name=agent_name,
        call_back_url=call_back_url,
        settings=settings,
        history_file_path=history_file_path,
        agent_knowledge=agent_knowledge,
    )
    logger.info("Agent instance created.")
    result = await agent.graph.ainvoke(MusicGenerationState())
    return result


async def generate_music(number_of_songs: int):
    """
    Runs the complete music generation and audio synthesis process.
    """
    logger.info(f"Starting music generation for {number_of_songs} songs...")
    for _ in range(number_of_songs):
        logger.info(f"Generating song {_ + 1} of {number_of_songs}")
        await main()
    logger.info(f"Music generation completed for {number_of_songs} songs")


class MusicGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.should_stop = False

    def setup_scheduling(self):
        """Set up scheduling for periodic music generation."""
        logger.info("Setting up schedule for music generation")
        schedule.every(self.settings.schedule.MUSIC_GENERATION_INTERVAL).hours.do(
            self._generate_music_sync
        )
        logger.info("Music generation service scheduling configured.")

    def _generate_music_sync(self):
        """Synchronous wrapper for async music generation with timeout."""
        try:
            number_of_songs = self.settings.suno.NUMBER_OF_SONGS
            logger.info(
                f"Starting scheduled music generation for {number_of_songs} songs..."
            )

            # Set a timeout for the entire music generation process (30 minutes per song)
            timeout_minutes = 30 * number_of_songs
            logger.info(f"Music generation timeout set to {timeout_minutes} minutes")

            # Run with timeout
            asyncio.run(
                asyncio.wait_for(
                    generate_music(number_of_songs),
                    timeout=timeout_minutes * 60,  # Convert to seconds
                )
            )
            logger.info("Scheduled music generation completed")
        except asyncio.TimeoutError:
            logger.error(f"Music generation timed out after {timeout_minutes} minutes")
        except Exception as e:
            logger.error(f"Error in scheduled music generation: {e}")

    def generate_initial_music(self):
        """Generate initial batch of music with timeout."""
        try:
            number_of_songs = self.settings.suno.NUMBER_OF_SONGS
            logger.info(
                f"Starting initial music generation for {number_of_songs} songs..."
            )

            # Set a timeout for the entire music generation process (30 minutes per song)
            timeout_minutes = 30 * number_of_songs
            logger.info(f"Music generation timeout set to {timeout_minutes} minutes")

            # Run with timeout
            asyncio.run(
                asyncio.wait_for(
                    generate_music(number_of_songs),
                    timeout=timeout_minutes * 60,  # Convert to seconds
                )
            )
            logger.info("Initial music generation completed")
        except asyncio.TimeoutError:
            logger.error(
                f"Initial music generation timed out after {timeout_minutes} minutes"
            )
        except Exception as e:
            logger.error(f"Error in initial music generation: {e}")

    def run(self):
        """Run the full service with scheduling (for standalone use)."""

        while True:  # Outer loop for automatic restarts
            self._run_internal()

            if self.should_stop:
                break  # Exit if shutdown requested

            logger.info("Service restarting...")
            time.sleep(10)  # Delay before restart to avoid rapid looping

    def _run_internal(self):
        """Internal run logic with scheduling and monitoring."""

        # generate initial music
        self.generate_initial_music()

        # setup scheduling
        self.setup_scheduling()

        # Keep the script running to execute scheduled tasks with timeout
        logger.info("Starting music generation scheduled task runner...")
        start_time = time.time()
        max_runtime_hours = 24  # Run for max 24 hours then restart
        last_heartbeat = 0  # Timestamp for heartbeat logging

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(
                f"Received signal {signum}. Shutting down music generation service..."
            )
            self.should_stop = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while not self.should_stop:
            try:
                schedule.run_pending()

                # Periodic heartbeat log
                current_time = time.time()
                if current_time - last_heartbeat > 300:  # Every 5 minutes
                    logger.info("Service heartbeat: Still running, no issues detected")
                    last_heartbeat = current_time

                # Check if we've been running too long
                runtime_hours = (time.time() - start_time) / 3600
                if runtime_hours > max_runtime_hours:
                    logger.info(
                        f"Music generation service has been running for {runtime_hours:.1f} hours. Restarting..."
                    )
                    break

                # Wait for up to a minute, but check for shutdown signal every second
                # for responsiveness.
                for _ in range(60):
                    if self.should_stop:
                        break
                    time.sleep(1)

            except KeyboardInterrupt:
                logger.info("Music generation service stopped by user")
                self.should_stop = True  # Ensure we exit cleanly
                break
            except Exception as e:
                logger.error(f"Error in music generation scheduler: {e}")
                logger.info("Restarting scheduler in 5 minutes...")
                time.sleep(300)  # Wait 5 minutes before continuing

        logger.info("Music generation service shutdown complete")


def setup_music_generation_service():
    """Initialize music generation service and set up scheduling (for integration with main app)."""
    settings = Settings()
    music_service = MusicGenerationService(settings)
    music_service.setup_scheduling()
    return music_service


def run_music_generation_service():
    """Run as standalone service with continuous scheduling."""
    settings = Settings()
    music_service = MusicGenerationService(settings)
    music_service.run()


if __name__ == "__main__":
    # Run the services
    initialize_media_once()
    run_music_generation_service()

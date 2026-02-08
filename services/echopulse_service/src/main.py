#!/usr/bin/env python
import asyncio
import sys
import os
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path

from mutagen.mp3 import MP3

# Removed unused typing imports

from langchain_mcp_adapters.client import MultiServerMCPClient
from config.config import MediaSettings, Settings
from app_logging.logger import logger
from services.obs_stream_service.services.schedule_updater import (
    update_scene_audio_path_in_schedule,
)
from services.obs_stream_service.utils.media import get_latest_audio_file

from services.news_service.src.graph import NewsGenerator
from LLM import (
    load_agent_personality,
    load_mcp_servers_config,
    load_news_memory,
    save_news_memory,
    load_json,
    initialize_llm,
)


from voice.generate import generate_voice


# Create a global asyncio Event to signal shutdown
# shutdown_event = asyncio.Event()


# def signal_handler(signum, frame):
#     """Signal handler to set the shutdown event."""
#     logger.info(f"Received signal {signum}. Shutting down news generation service...")
#     shutdown_event.set()


# Register the signal handlers
# signal.signal(signal.SIGINT, signal_handler)
# signal.signal(signal.SIGTERM, signal_handler)


# Load the configuration
logger.info("Loading configuration...")
try:
    settings = Settings()
    agent_personality = settings.agent.agent_personality_path
    logger.info("Configuration loaded.")
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    sys.exit(1)


async def main(topic: str):
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
        logger.warning(
            "Validation LLM could not be initialized. Continuing without it."
        )

    # Initialize the tools for data feeds
    # This block is dedicated to load the mcp servers and configure them
    # -----------------------------------------------------------#
    # -----------------------------------------------------------#
    # -----------------------------------------------------------#
    MCP_SERVERS_CONFIG = load_mcp_servers_config(
        apify_token=settings.APIFY_TOKEN,
        mcp_tavily_url=settings.search_mcp.MCP_TAVILY_URL,
        mcp_arxiv_url=settings.search_mcp.MCP_ARXIV_URL,
        apify_actors_list=["apidojo/twitter-scraper-lite"],
        mcp_telegram_parser_url=settings.search_mcp.MCP_TELEGRAM_PARSER_URL,
    )

    # Try to connect to each MCP server individually
    mcp_tools = []
    successful_connections = 0
    failed_connections = 0

    logger.info("Attempting to connect to MCP servers individually...")

    for server_name, server_config in MCP_SERVERS_CONFIG.items():
        try:
            logger.info(
                f"Connecting to {server_name} at {server_config.get('url', 'No URL')}..."
            )

            # Create a single-server client for this server
            single_server_config = {server_name: server_config}
            single_client = MultiServerMCPClient(single_server_config)

            # Try to get tools from this specific server with timeout
            server_tools = await asyncio.wait_for(
                single_client.get_tools(), timeout=30.0
            )

            if server_tools:
                mcp_tools.extend(server_tools)
                successful_connections += 1
                tool_names = [tool.name for tool in server_tools]
                logger.info(
                    f"SUCCESS: {server_name} connected successfully - tools: {tool_names}"
                )
            else:
                logger.warning(
                    f"WARNING: {server_name} connected but returned no tools"
                )
                successful_connections += 1  # Still count as successful connection

        except asyncio.TimeoutError:
            failed_connections += 1
            logger.error(f"ERROR: {server_name} connection timed out after 30 seconds")
            continue
        except Exception as e:
            failed_connections += 1
            error_message = str(e)
            # Check for ExceptionGroup and extract sub-exceptions for clearer logging
            if hasattr(e, "exceptions") and e.exceptions:
                # Extract details from the first sub-exception
                sub_exc = e.exceptions[0]
                error_message = f"{type(sub_exc).__name__}: {sub_exc}"

            logger.error(f"ERROR: Failed to connect to {server_name}: {error_message}")
            logger.debug(f"Full error for {server_name}:", exc_info=True)
            continue

    # Log summary
    logger.info(
        f"MCP Connection Summary: {successful_connections} successful, {failed_connections} failed"
    )

    if successful_connections == 0:
        logger.error("CRITICAL ERROR: No MCP servers could be initialized!")
        sys.exit(1)
    else:
        logger.info(
            f"SUCCESS: Proceeding with {len(mcp_tools)} tools from {successful_connections} working servers"
        )
        if mcp_tools:
            tool_names = [tool.name for tool in mcp_tools]
            logger.info(f"Available MCP tools: {tool_names}")

    # -----------------------------------------------------------#
    # -----------------------------------------------------------#
    # -----------------------------------------------------------#
    # -----------------------------------------------------------#
    # Agent personality load
    agent_personality = load_agent_personality(settings.agent.agent_personality_path)
    agent_name = agent_personality["agent"]["identity"]["name"]
    logger.info(f"Agent personality loaded: {agent_personality}")
    # -----------------------------------------------------------#

    # Load the topics
    if topic == "AI_Robotics":
        topics_file_path = "config/agent_data/AI_Robotics_topics.json"
        topics = load_json(topics_file_path)
        news_memory_file_path = (
            settings.media.news_output_dir / "news_memory_AI_Robotics.json"
        )
    elif topic == "Web3":
        topics_file_path = "config/agent_data/Web3_topics.json"
        topics = load_json(topics_file_path)
        news_memory_file_path = settings.media.news_output_dir / "news_memory_Web3.json"
    else:
        logger.error(f"Invalid topic: {topic}")
        return None
    topics = topics["topics"]
    topics_list = list(topics.keys())
    logger.info(f"Topics: {topics_list}")

    # load the news memory for the specific topic
    try:
        news_memory = load_news_memory(news_memory_file_path, limit=5, titles_only=True)
        logger.info(f"News memory loaded: {news_memory}")
    except Exception as e:
        logger.error(f"Error loading news memory: {e}")
        news_memory = []

    # Initialize the agent
    agent = NewsGenerator(
        LLM,
        LLM_THINKING,
        tools=mcp_tools,
        news_memory=news_memory,
        agent_personality=agent_personality,
        agent_name=agent_name,
        research_topics=topics_list,
        topics_file_path=topics_file_path,
    )
    logger.info("Agent instance created.")
    result = await agent.graph.ainvoke({"research_topic": topics_list})
    return result, news_memory_file_path


async def generate_news(topic: str):
    """
    Runs the complete news generation and audio synthesis process.

    Args:
        output_dir: The directory to save the generated audio file.

    Returns:
        A tuple containing the audio file path and the news article data,
        or None if the process fails.
    """
    attempts = 3
    logger.info(f"Generating news for {topic} with {attempts} attempts...")
    for attempt in range(attempts):
        logger.info(f"Attempt {attempt + 1} of {attempts}...")
        result, news_memory_file_path = await main(topic)

        if not result or not result.get("news_article_content"):
            logger.error("News generation failed: No news article content was created.")
            continue

        news_article_content = result["news_article_content"]
        if news_article_content == "No news article content available":
            logger.info("News generation process failed. Not saving to memory.")
            continue
        else:
            save_news_memory(result, news_memory_file_path)

            # generate audio
            logger.info("Starting audio generation...")
            elevenlabs_config = settings.elevenlabs
            filename = generate_voice(
                text=news_article_content,
                api_config=elevenlabs_config,
                file_path=str(settings.media.voice_output_dir),
                topic=topic,
            )

            # Ensure the filename is not None and construct the full path
            if filename and len(filename) > 0:
                full_path = Path(settings.media.voice_output_dir) / filename

                # Check the audio file length to ensure it's not empty
                try:
                    audio = MP3(full_path)
                    logger.info(f"Audio file length: {audio.info.length:.2f} seconds")
                    if audio.info.length > 5:  # minimum duration of 5 seconds
                        logger.info(
                            f"Voice file generated at: {full_path} with duration: {audio.info.length:.2f} seconds"
                        )
                        return full_path, result
                    else:
                        logger.warning(
                            f"Generated audio file has less than 5 seconds: {full_path}"
                        )
                        continue
                except Exception as e:
                    logger.error(f"Failed to read audio file metadata: {e}")
                    continue
            else:
                logger.info("Audio generation failed: No audio file was generated.")
                continue

    logger.error("Failed to generate news after all attempts.")


# Configuration: News lifetime (hardcoded for now)
NEWS_LIFETIME_HOURS = 24  # News is considered fresh for 24 hours


def is_news_fresh(topic: str, media_settings: MediaSettings) -> tuple[bool, str | None]:
    """
    Check if we have fresh news for the given topic.
    Returns (is_fresh, audio_file_path)
    """
    # Check if news memory file exists
    news_file = media_settings.news_output_dir / f"news_memory_{topic}.json"
    if not os.path.exists(news_file):
        return False, None

    # Check if we have a corresponding audio file
    audio_file = get_latest_audio_file(topic, media_settings)
    if not audio_file:
        return False, None

    # Check if the audio file is fresh (within NEWS_LIFETIME_HOURS)
    file_mtime = datetime.fromtimestamp(os.path.getmtime(audio_file))
    now = datetime.now()
    age = now - file_mtime

    is_fresh = age < timedelta(hours=NEWS_LIFETIME_HOURS)

    if is_fresh:
        logger.info(f"Found fresh {topic} news (age: {age})")
    else:
        logger.warning(
            f"{topic} news is stale (age: {age}, limit: {NEWS_LIFETIME_HOURS}h)"
        )

    return is_fresh, audio_file


def update_schedule_with_cached_audio(topic: str, audio_file_path: str) -> None:
    """
    Update the schedule.json file with the cached audio file path.
    """
    scene_name = f"{topic.lower()}_news"
    update_scene_audio_path_in_schedule(scene_name, audio_path=audio_file_path)
    logger.info(
        f"✅ Updated schedule for {scene_name} with cached audio: {os.path.basename(audio_file_path)}"
    )


async def generate_news_for_ai_robotics(force: bool = False):

    if force:
        logger.info("Force mode: Bypassing cache check for AI_Robotics news...")
    else:
        logger.info("Checking for fresh AI_Robotics news...")

    settings = Settings()
    media_settings = settings.media

    # # Check if we already have fresh news (unless force is True)
    # if not force:
    #     is_fresh, cached_audio_file = is_news_fresh("AI_Robotics", media_settings)
    #     if is_fresh and cached_audio_file:
    #         logger.info("Using cached AI_Robotics news")
    #         update_schedule_with_cached_audio("AI_Robotics", cached_audio_file)
    #         return

    logger.info("Generating new AI_Robotics news...")
    try:
        news_generation_result = await generate_news("AI_Robotics")
        if not news_generation_result:
            logger.warning("News generation for AI_Robotics returned no result")
            return

        audio_file_path, news_article = news_generation_result

        save_news_memory(
            news_article,
            str(media_settings.news_output_dir / "news_memory_AI_Robotics.json"),
        )
        # Update the schedule.json file to set the news audio path for the news section on the stream
        update_scene_audio_path_in_schedule(
            "ai_robotics_news", audio_path=str(audio_file_path)
        )
        logger.info("AI_Robotics news generation completed")
        logger.info("News generator for AI_Robotics topic completed")
    except (ValueError, IOError) as e:
        logger.error(f"Error generating news for AI_Robotics: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during AI_Robotics news generation: {e}"
        )


async def generate_news_for_web3(force: bool = False):
    # if force:
    #     logger.info("Force mode: Bypassing cache check for Web3 news...")
    # else:
    #     logger.info("Checking for fresh Web3 news...")

    settings = Settings()
    media_settings = settings.media

    # Check if we already have fresh news (unless force is True)
    if not force:
        is_fresh, cached_audio_file = is_news_fresh("Web3", media_settings)
        if is_fresh and cached_audio_file:
            logger.info("Using cached Web3 news")
            update_schedule_with_cached_audio("Web3", cached_audio_file)
            return

    logger.info("Generating new Web3 news...")
    try:
        news_generation_result = await generate_news("Web3")
        if not news_generation_result:
            logger.warning("News generation for Web3 returned no result.")
            return

        audio_file_path, news_article = news_generation_result

        save_news_memory(
            news_article, str(media_settings.news_output_dir / "news_memory_Web3.json")
        )
        update_scene_audio_path_in_schedule(
            "web3_news", audio_path=str(audio_file_path)
        )
        logger.info("Web3 news generation completed")
        logger.info("News generator for Web3 topic completed")
    except (ValueError, IOError) as e:
        logger.error(f"Error generating news for Web3: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Web3 news generation: {e}")


class NewsGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.should_stop = False

    def setup_scheduling(self):
        """Set up scheduling for periodic news generation."""
        logger.info("Setting up schedule for news generation")
        schedule.every(1).day.at("10:00").do(
            lambda: asyncio.create_task(generate_news_for_ai_robotics())
        )
        schedule.every(1).day.at("10:00").do(
            lambda: asyncio.create_task(generate_news_for_web3())
        )
        logger.info("News generation service scheduling configured.")

    async def run(self):
        """Run the full service with scheduling (for standalone use)."""

        while True:  # Outer loop for automatic restarts
            try:
                await self._run_internal()
            except asyncio.CancelledError:
                logger.info("News generation service run cancelled.")
                break
            except Exception as e:
                logger.error(f"News generation service crashed: {e}. Restarting...")

            logger.info("News generation service restarting...")
            await asyncio.sleep(10)  # Use asyncio.sleep for non-blocking delay

    async def _run_internal(self):
        """Internal run logic with scheduling and monitoring."""

        # Generate initial news on startup
        logger.info("Generating initial news on service startup...")
        try:
            await generate_news_for_web3()
            await generate_news_for_ai_robotics()
            logger.info("Initial news generation completed")
        except Exception as e:
            logger.error(f"Error generating initial news: {e}")

        # Setup scheduling
        self.setup_scheduling()

        # Keep the script running to execute scheduled tasks with timeout
        logger.info("Starting news generation scheduled task runner...")
        start_time = time.time()
        max_runtime_hours = 24  # Run for max 24 hours then restart
        last_heartbeat = 0  # Timestamp for heartbeat logging

        while True:
            try:
                schedule.run_pending()

                # Periodic heartbeat log
                current_time = time.time()
                if current_time - last_heartbeat > 300:  # Every 5 minutes
                    logger.info(
                        "News generation service heartbeat: Still running, no issues detected"
                    )
                    last_heartbeat = current_time

                # Check if we've been running too long
                runtime_hours = (current_time - start_time) / 3600
                if runtime_hours > max_runtime_hours:
                    logger.info(
                        f"News generation service has been running for {runtime_hours:.1f} hours. Triggering restart..."
                    )
                    return  # Exit internal loop to trigger outer restart

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("News generation scheduler loop cancelled.")
                raise  # Propagate cancellation
            except Exception as e:
                logger.error(f"Error in news generation scheduler: {e}")
                logger.info("Pausing scheduler for 5 minutes before retry...")
                await asyncio.sleep(300)

    def setup_schedule_for_news_generation():
        """Initialize news generation service and set up scheduling (for integration with main app)."""
        settings = Settings()
        news_service = NewsGenerationService(settings)
        news_service.setup_scheduling()
        return news_service


async def run_news_generation_service_async():
    """Run as standalone service with continuous scheduling."""
    settings = Settings()
    news_service = NewsGenerationService(settings)
    await news_service.run()


if __name__ == "__main__":
    try:
        asyncio.run(run_news_generation_service_async())
    except KeyboardInterrupt:
        logger.info("News generation service stopped by user.")

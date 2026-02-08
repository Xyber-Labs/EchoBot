#!/usr/bin/env python
"""
This is the main script that controls OBS Stream Service.
"""
import asyncio
from config.config import Settings
from services.obs_stream_service.core.flow import RadioFlow
from app_logging.logger import logger
from services.music_service.media.media_service import initialize_media_once
import os

settings = Settings()


logger.info(f"OBS_HOST = {settings.obs.OBS_HOST}")
logger.info(f"OBS_PORT = {settings.obs.OBS_PORT}")


def main() -> None:
    # Initialize all media before starting any services
    if os.getenv("OBS_ONLY_MODE") == "true":
        logger.info("⚡ OBS ONLY MODE — skip media initialization")
    else:
        logger.info("🚀 Initializing all media...")
        initialize_media_once()
        logger.info("✅ All media initialized successfully.")

    # Start API process first
    logger.info("Starting radio flow...")
    radio_flow = RadioFlow(settings)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(radio_flow.start())
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
        radio_flow._running = False
    finally:
        # Ensure cleanup
        try:
            loop.run_until_complete(radio_flow._shutdown())
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
        finally:
            loop.close()
            logger.info("Radio flow stopped.")


if __name__ == "__main__":
    main()

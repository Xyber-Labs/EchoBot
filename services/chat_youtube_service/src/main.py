from __future__ import annotations

import argparse
import asyncio
import os
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app_logging.logger import logger
from config.config import Settings
from services.chat_youtube_service.src.api import router as api_router
from services.chat_youtube_service.src.chat_module import (ChatService,
                                                           create_chat_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing settings and chat service (lifespan startup)...")
    settings = Settings()
    chat_service: ChatService = create_chat_service(settings)
    app.state.chat_service = chat_service

    # Automatically start the broadcast on service startup
    if settings.youtube.YOUTUBE_ENABLED:
        logger.info("Attempting to start YouTube broadcast on startup...")
        broadcast_details = chat_service.start_broadcast(title_prefix="EchoBot")
        if broadcast_details.get("broadcast_id"):
            logger.info(
                f"Successfully started or found broadcast: {broadcast_details['broadcast_id']}"
            )
            logger.info(
                "\nWatch URL: %s\nStream key: %s\nRTMP URL: %s",
                broadcast_details.get("watch_url"),
                broadcast_details.get("stream_key"),
                broadcast_details.get("rtmp_url"),
            )
        else:
            logger.error(
                "Failed to start or find broadcast on startup. The service will run without a live stream."
            )

    def _run_async_in_thread():
        asyncio.run(chat_service.run(install_signal_handlers=False))

    chat_thread = threading.Thread(target=_run_async_in_thread, daemon=True)
    chat_thread.start()
    app.state.chat_thread = chat_thread
    logger.info("Chat service background thread started")
    try:
        yield
    finally:
        logger.info("Lifespan shutdown: requesting chat service stop...")
        try:
            chat_service.should_stop = True
        except Exception:
            pass


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Chat YouTube Service",
        version="0.0.1",
        lifespan=lifespan,
        description="Monitors a YouTube live stream chat and provides AI-powered responses.",
    )
    app.include_router(api_router)
    return app


app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Chat YouTube Service")
    # Load settings so host/port defaults come from a single source of truth
    _settings_cli = Settings()
    parser.add_argument(
        "--host",
        default=_settings_cli.youtube.CHAT_YOUTUBE_HOST,
        help="Host to bind to (Default: CHAT_YOUTUBE_HOST or 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_settings_cli.youtube.CHAT_YOUTUBE_PORT or 8000),
        help="Port to listen on (Default: CHAT_YOUTUBE_PORT or 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("CHAT_YOUTUBE_HOT_RELOAD", "false").lower()
        in ("true", "1", "t", "yes"),
        help="Enable hot reload (env: CHAT_YOUTUBE_HOT_RELOAD)",
    )

    args = parser.parse_args()
    logger.info(f"Starting Chat YouTube Service on {args.host}:{args.port}")

    uvicorn.run(
        "services.chat_youtube_service.src.main:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )

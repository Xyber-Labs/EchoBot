#!/usr/bin/env python
"""Event Notifier Service - FastAPI service for receiving and forwarding events."""

import argparse
import logging
import sys
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.config import Settings
from services.event_notifier_service.src.event_handler import EventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Event Notifier Service")

# Initialize settings and event handler
settings = Settings()
event_handler: EventHandler | None = None


def initialize_event_handler() -> None:
    """Initialize the event handler with webhook URLs from settings."""
    global event_handler

    webhook_urls_str = settings.event_notifier.WEBHOOK_URLS
    webhook_urls = []

    if webhook_urls_str:
        # Parse comma-separated URLs
        webhook_urls = [
            url.strip() for url in webhook_urls_str.split(",") if url.strip()
        ]

    if webhook_urls:
        logger.info(
            f"Initializing event handler with {len(webhook_urls)} webhook URL(s)"
        )
        for url in webhook_urls:
            logger.info(f"  - {url}")
    else:
        logger.warning(
            "No webhook URLs configured. Events will be logged but not forwarded."
        )

    event_handler = EventHandler(webhook_urls=webhook_urls)


# Initialize on startup
initialize_event_handler()


class EventRequest(BaseModel):
    """Request model for event submission."""

    event: str
    data: dict[str, Any] | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "event_notifier"}


@app.post("/events")
async def receive_event(request: EventRequest) -> JSONResponse:
    """
    Receive an event and forward it to configured webhooks.

    Request body:
    {
        "event": "news_section_started",
        "data": {
            "scene": "ai_robotics_news",
            "audio_file": "...",
            "duration_seconds": 180.5
        }
    }
    """
    if not event_handler:
        logger.error("Event handler not initialized")
        raise HTTPException(status_code=500, detail="Event handler not initialized")

    try:
        logger.info(f"📥 Received event: {request.event}")
        if request.data:
            logger.debug(f"   Event data: {request.data}")

        event_handler.forward_event(
            event_type=request.event,
            data=request.data,
            retry_count=2,  # Retry failed webhooks once
        )

        webhook_count = len(event_handler.webhook_urls) if event_handler else 0
        logger.info(
            f"✅ Event '{request.event}' processed. Forwarded to {webhook_count} webhook(s)"
        )

        return JSONResponse(
            {"ok": True, "event": request.event, "forwarded_to": webhook_count}
        )
    except Exception as e:
        logger.error(f"❌ Error processing event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing event: {str(e)}")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "event_notifier",
        "status": "running",
        "webhooks_configured": len(event_handler.webhook_urls) if event_handler else 0,
    }


def main() -> None:
    """Run the event notifier service."""
    parser = argparse.ArgumentParser(description="Event Notifier Service")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port to listen on",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable hot reload",
    )
    args = parser.parse_args()

    logger.info(f"Starting Event Notifier Service on {args.host}:{args.port}")
    logger.info(
        f"Webhook URLs configured: {len(event_handler.webhook_urls) if event_handler else 0}"
    )

    import uvicorn

    uvicorn.run(
        "services.event_notifier_service.src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["services/event_notifier_service"] if args.reload else None,
    )


if __name__ == "__main__":
    main()

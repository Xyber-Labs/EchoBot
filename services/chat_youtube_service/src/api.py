from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from services.chat_youtube_service.src.chat_module import ChatService

router = APIRouter()


class HealthCheckResponse(BaseModel):
    watch_url: Optional[str] = Field(
        None, example="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    broadcast_id: Optional[str] = Field(None, example="dQw4w9WgXcQ")
    stream_key: Optional[str] = Field(None, example="abcd-1234-efgh-5678")
    rtmp_url: Optional[str] = Field(
        None, example="rtmp://a.rtmp.youtube.com/live2/abcd-1234-efgh-5678"
    )
    live_chat_id: Optional[str] = Field(
        None,
        example="Cg0KC2VSejZpOWkzY2NzKicKGFVDNHIyck4zTDM4cWZiZDVUdjNDb1lVQRILZVJ6Nmk5aTNjY3M",
    )


class ServiceUnavailableResponse(BaseModel):
    detail: str = Field(..., example="No active YouTube chat session found.")


@router.get(
    "/healthcheck",
    summary="Check the health of the YouTube chat service",
    description="Returns the current broadcast details if the service is running and a stream is active.",
    response_model=HealthCheckResponse,
    responses={
        status.HTTP_200_OK: {
            "description": "Service is healthy and connected to a YouTube chat.",
            "model": HealthCheckResponse,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service is running but not connected to an active YouTube chat.",
            "model": ServiceUnavailableResponse,
        },
    },
)
def healthcheck(request: Request) -> HealthCheckResponse:
    chat_service: ChatService | None = getattr(request.app.state, "chat_service", None)

    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not available.",
        )

    details = chat_service.get_broadcast_details()

    if details.get("broadcast_id"):
        return HealthCheckResponse(**details)
    else:
        # No active broadcast - return 503 to signal monitoring systems
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active YouTube chat session found.",
        )


class StartStreamResponse(BaseModel):
    stream_key: Optional[str]
    watch_url: Optional[str]
    broadcast_id: Optional[str]
    rtmp_url: Optional[str]
    message: str


@router.post(
    "/start",
    summary="Start a new YouTube broadcast",
    description="Creates a new YouTube live broadcast and stream, and returns the details.",
    response_model=StartStreamResponse,
)
def start_broadcast(
    request: Request,
    title: str = Query(
        "EchoBot Live Stream", description="Title for the new YouTube broadcast."
    ),
    force: bool = Query(
        False,
        description="If true, a new broadcast will be created even if one is already active.",
    ),
) -> StartStreamResponse:
    chat_service: ChatService | None = getattr(request.app.state, "chat_service", None)
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not available.",
        )

    result = chat_service.start_broadcast(title_prefix=title, force=force)
    if result.get("broadcast_id"):
        message = (
            "A new broadcast was started successfully."
            if result["is_new"]
            else "An existing broadcast is already running."
        )
        return StartStreamResponse(**result, message=message)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start broadcast.",
        )

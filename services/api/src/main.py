import asyncio
import logging
from collections import deque
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse, StreamingResponse)

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR.parent / "index.html"
FAVICON_FILE = BASE_DIR.parent / "favicon.ico"

MAX_LINES = 2000  # keep only the last N log lines in memory
logs: deque[str] = deque(maxlen=MAX_LINES)
subscribers: set[asyncio.Queue[str]] = set()
lock = asyncio.Lock()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    # serve static index.html
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except FileNotFoundError:
        return PlainTextResponse("index.html not found", status_code=404)


@app.get("/favicon.ico")
async def favicon() -> Response:
    if FAVICON_FILE.exists():
        return FileResponse(FAVICON_FILE)
    return PlainTextResponse("", status_code=204)


@app.get("/logs", response_class=PlainTextResponse)
async def get_logs() -> PlainTextResponse:
    # return the current tail as plain text
    return PlainTextResponse("\n".join(logs))


@app.get("/stream")
async def stream() -> StreamingResponse:
    """
    SSE stream: each subscriber receives new log lines.
    """
    queue: asyncio.Queue[str] = asyncio.Queue()
    subscribers.add(queue)
    logging.info(f"New subscriber connected. Total subscribers: {len(subscribers)}")

    async def event_gen() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    # wait for next line or send heartbeat to keep connections alive
                    line = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {line}\n\n"
                except TimeoutError:
                    # SSE heartbeat comment to avoid buffering/timeouts
                    yield ": keep-alive\n\n"
        finally:
            subscribers.discard(queue)
            logging.info(
                f"Subscriber disconnected. Total subscribers: {len(subscribers)}"
            )

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # disable Nginx buffering for streaming
    }
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=headers,  # type: ignore
    )


@app.post("/log")
async def post_log(request: Request) -> Response:
    """
    Accept a new log line.
    - application/json: {"line": "..."}
    - text/plain: raw string in body
    """
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        data = await request.json()
        line = str(data.get("line", "")).rstrip("\n")
    else:
        body = await request.body()
        line = body.decode("utf-8").rstrip("\n")

    if not line:
        return JSONResponse({"ok": False, "reason": "empty line"}, status_code=400)

    logging.info(f"Received log: '{line}'. Pushing to {len(subscribers)} subscribers.")

    # append to buffer and fan out to subscribers
    async with lock:
        # Create log entry with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M")
        log_entry = f"{timestamp}|{line}"
        logs.append(log_entry)
        for q in tuple(subscribers):
            try:
                q.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass

    return {"ok": True, "stored": len(logs)}


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run EchoBot Log API")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable hot reload",
    )
    args = parser.parse_args()

    uvicorn.run(
        "services.api.src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["services/api"] if args.reload else None,
    )

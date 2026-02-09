from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from app_logging.logger import logger
from config.config import Settings
from LLM.llm_utils import generate_llm_response_async, clean_for_voice
from LLM import load_agent_personality, load_json
from services.obs_stream_service.core.ama_promts import AMA_reply_prompt
from voice.generate import generate_voice
import yaml



settings = Settings()


def load_answered_messages(
    settings: Settings,
) -> tuple[set[str], list[dict[str, Any]]]:
    """Load answered chat messages memory used for AMA generation."""
    memory_file: Path = settings.media.memory_output_dir / "memory.json"
    try:
        with open(memory_file, encoding="utf-8") as fp:
            data: list[dict[str, Any]] = json.load(fp)
        return {item.get("id", "") for item in data if isinstance(item, dict)}, data
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), []


def load_yaml(file_path: str) -> dict[str, Any]:
    """Load YAML file and return its contents as a dictionary."""
    with open(file_path, encoding="utf-8") as fp:
        return yaml.safe_load(fp)


async def generate_ama_voice(
    settings: Settings, answered_messages: list[dict[str, Any]]
) -> str | None:
    """Generate AMA reply audio based on recent answered messages.

    Returns the generated filename (not full path) or None on failure.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    five_minutes = datetime.timedelta(minutes=5)
    chat_history: list[dict[str, Any]] = [
        {
            "message": msg.get("message"),
            "agent_reply_text": msg.get("agent_reply_text"),
            "author": msg.get("author"),
        }
        for msg in answered_messages
        if msg.get("agent_reply_text")
        and msg.get("timestamp")
        and (now - datetime.datetime.fromisoformat(msg.get("timestamp")) < five_minutes)
    ][:30]

    try:
        # Load agent data (kept here for minimal dependency footprint)
        agent_personality = load_agent_personality(
            settings.agent.agent_personality_path
        )
        agent_knowledge = load_json(settings.agent.agent_knowledge_path)
   
        formatted_prompt = AMA_reply_prompt.format(
            agent_personality=agent_personality,
            agent_knowledge=agent_knowledge,
            chat_history=chat_history,
        )

        response = await generate_llm_response_async(formatted_prompt)
        logger.info(f"Response: {response}")
        if not hasattr(response, "content"):
            logger.error("Response object has no content attribute")
            return None

        content: str = response.content  # type: ignore[attr-defined]
        json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content

        parsed_response = json.loads(json_str)
        reply_text: str = parsed_response.get("reply_text", "")
        logger.info(f"AMA Reply: {reply_text}")

        reply_text_cleaned = clean_for_voice(reply_text)
        file_path = settings.media.voice_output_dir
        logger.info(f"File path: {file_path}")

        try:
            filename = generate_voice(
                reply_text_cleaned,
                api_config=settings.elevenlabs,
                file_path=file_path,
                topic="AMA",
            )
            logger.info(f"Voice generated with filename: {filename}")
            return filename
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error generating voice for AMA reply: {e}")
            return None

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error generating response for message {e}")
        return None


if __name__ == "__main__":
    import asyncio

    settings = Settings()
    answered_messages = [
        {
            "message": "What is the secret word for today?",
            "agent_reply_text": "I can't tell you!",
            "author": "TestUser",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        {
            "message": "What is the secret word for today?",
            "agent_reply_text": "I can't tell you!",
            "author": "TestUser",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        
    ]

    filename = asyncio.run(generate_ama_voice(settings, answered_messages))
    logger.info(f"Filename: {filename}")

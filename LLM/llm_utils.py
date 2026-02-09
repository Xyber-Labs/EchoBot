# Libraries for different LLMs
import json
import os
import re
from datetime import datetime
from functools import lru_cache
from logging import LoggerAdapter
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_together import ChatTogether

from app_logging.logger import logger
from config.config import LLMSettings

PROJECT_ROOT = os.getenv(
    "PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def load_news_memory(file_path: str, limit: int = None, titles_only: bool = False):
    if not os.path.exists(file_path):
        logger.info(f"News memory file not found at {file_path}. Creating it.")
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump({}, f)

    with open(file_path) as f:
        data = json.load(f)

    # Get the last N items from the dictionary
    keys = list(data.keys())
    if limit is not None:
        last_keys = keys[-limit:] if len(keys) >= limit else keys
        data = {key: data[key] for key in last_keys}

    # If titles_only is True, extract only the article titles
    if titles_only:
        titles = []
        for key, article in data.items():
            # Handle different article structures
            if isinstance(article, dict):
                title = article.get("news_article_title")
                if title:
                    titles.append(title)
        return titles

    return data


def load_agent_personality(file_path: str):
    with open(file_path) as f:
        data = json.load(f)
    return data


def load_json(file_path, create_file=False):
    """Loads JSON file."""
    try:
        logger.info(f"Attempting to load file from: {file_path}")
        if not os.path.exists(file_path):
            logger.warning(
                f"File does not exist at path. Creating new file: {file_path}"
            )
            if create_file:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
                return {}
            return {}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                logger.warning(
                    f"File is empty: {file_path}. Returning empty dictionary."
                )
                return {}
            data = json.loads(content)
            logger.info(f"Successfully loaded JSON data from {file_path}")
            return data

    except json.JSONDecodeError as je:
        logger.error(
            f"JSON parsing error in {file_path}: {je}. Returning empty dictionary."
        )
        return {}

    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        return {}


def save_news_memory(new_article: dict, file_path: str):
    """Add a new article to the news memory, preserving existing articles.

    Args:
        new_article: Dictionary containing news_article_title, news_article_summary, news_article_content
        file_path: Path to the news memory JSON file
    """
    # Load existing memory or create empty dict
    if os.path.exists(file_path):
        try:
            with open(file_path) as f:
                existing_memory = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_memory = {}
    else:
        existing_memory = {}

    # Generate a unique key for the new article
    # Use timestamp to ensure uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_key = f"news_article_{timestamp}"

    # Ensure the key is unique (in case of rapid successive calls)
    counter = 1
    original_key = new_key
    while new_key in existing_memory:
        new_key = f"{original_key}_{counter}"
        counter += 1

    # Add the new article to the memory
    existing_memory[new_key] = new_article

    # Save the updated memory
    with open(file_path, "w") as f:
        json.dump(existing_memory, f, indent=2)


# ------------------------------------------------------------------------------------------------
# Block dedicated for the LLM initialization
# ------------------------------------------------------------------------------------------------
LLM_Type = Literal["main", "spare", "validation", "thinking"]


class BaseChatModel:
    def __init__(self, model: str, **kwargs):
        self.model = model
        print(f"Initialized {self.__class__.__name__} with model: {self.model}")

    def with_fallbacks(self, fallbacks: list):
        print(f"Applied fallbacks to {self.__class__.__name__}")
        return self


@lru_cache(maxsize=8)
def initialize_llm(
    llm_type: Literal["main", "validation", "spare", "thinking"] = "main",
    raise_on_error: bool = True,
) -> BaseChatModel:
    """
    Initializes and returns a language model client based on the specified type.
    This function is cached to avoid reloading models on subsequent calls.
    """
    config = LLMSettings()
    logger.info(f"Setting up '{llm_type}' LLM...")

    model_name = None

    # 1. Define mappings to find the correct config attributes and provider details
    ATTRIBUTE_MAP: Dict[LLM_Type, Tuple[str, str]] = {
        "main": ("MODEL_PROVIDER", "MODEL_NAME"),
        "spare": ("MODEL_PROVIDER_SPARE", "MODEL_NAME_SPARE"),
        "validation": ("MODEL_VALIDATION_PROVIDER", "MODEL_VALIDATION_NAME"),
        "thinking": ("MODEL_PROVIDER_THINKING", "MODEL_NAME_THINKING"),
    }

    PROVIDER_MAP: Dict[str, Dict[str, Any]] = {
        "together": {
            "class": ChatTogether,
            "api_key_name": "TOGETHER_API_KEY",
            "init_arg": "together_api_key",
        },
        "google": {
            "class": ChatGoogleGenerativeAI,
            "api_key_name": "GOOGLE_API_KEY",
            "init_arg": "google_api_key",
        },
        "mistral": {
            "class": ChatMistralAI,
            "api_key_name": "MISTRAL_API_KEY",
            "init_arg": "api_key",
        },
    }

    # 2. Get model provider and name from config using the attribute map
    provider_attr, name_attr = ATTRIBUTE_MAP[llm_type]
    model_provider = getattr(config, provider_attr, None)
    model_name = getattr(config, name_attr, None)

    if not all([model_provider, model_name]):
        msg = f"Configuration for '{llm_type}' LLM ('{provider_attr}', '{name_attr}') is incomplete."
        logger.error(msg)
        if raise_on_error:
            raise ValueError(msg)
        return None

    # 3. Get provider-specific details from the provider map
    provider_details = PROVIDER_MAP.get(model_provider.lower())
    if not provider_details:
        msg = f"Unsupported model provider for '{llm_type}': {model_provider}"
        logger.error(msg)
        if raise_on_error:
            raise ValueError(msg)
        return None

    # 4. Check for the required API key
    api_key_name = provider_details["api_key_name"]
    api_key_value = getattr(config, api_key_name, None)
    if not api_key_value:
        msg = f"'{api_key_name}' is required for provider '{model_provider}' but is not set."
        logger.error(msg)
        if raise_on_error:
            raise ValueError(msg)
        return None

    # 5. Initialize and return the model
    try:
        ModelClass: Type[BaseChatModel] = provider_details["class"]
        init_kwargs = {
            provider_details["init_arg"]: api_key_value,
            "model": model_name,
        }
        llm_instance = ModelClass(**init_kwargs)
        logger.info(
            f"Successfully initialized '{llm_type}' LLM with provider '{model_provider}'."
        )
        return llm_instance
    except Exception as e:
        msg = f"Failed to initialize '{llm_type}' LLM from provider '{model_provider}': {e}"
        logger.error(msg, exc_info=True)
        if raise_on_error:
            raise
        return None


def clean_response(response_text: str) -> str:
    """Clean the response text by removing markdown code block markers if present."""
    try:
        # Clean response text by removing markdown code block markers if present
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```json"):
            # Remove ```json from start and ``` from end
            cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # Remove ```
        elif cleaned_response.startswith("```"):
            # Remove ``` from start and end (generic code block)
            cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]

        cleaned_response = cleaned_response.strip()

        return cleaned_response
    except Exception as e:
        logger.error(f"Error cleaning response: {e}")


def clean_for_voice(text: str) -> str:
    """Clean text for voice generation by removing emojis, problematic Unicode, and excessive newlines."""
    import re

    try:
        # Remove emojis and other symbols
        # This regex matches most emoji characters
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002702-\U000027b0"  # dingbats
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub("", text)

        # Replace problematic Unicode characters with readable alternatives
        unicode_replacements = {
            "\u2019": "'",  # Right single quotation mark
            "\u2018": "'",  # Left single quotation mark
            "\u201c": '"',  # Left double quotation mark
            "\u201d": '"',  # Right double quotation mark
            "\u2013": "-",  # En dash
            "\u2014": "-",  # Em dash
            "\u2026": "...",  # Horizontal ellipsis
            "\u00a0": " ",  # Non-breaking space
            "\u2022": "*",  # Bullet point
            "\u00b7": "*",  # Middle dot
            "\u00ae": "(R)",  # Registered trademark
            "\u00a9": "(C)",  # Copyright
            "\u2122": "(TM)",  # Trademark
        }

        for unicode_char, replacement in unicode_replacements.items():
            text = text.replace(unicode_char, replacement)

        # Remove any remaining problematic Unicode characters
        # Keep only ASCII printable characters, spaces, and basic punctuation
        text = "".join(char for char in text if ord(char) < 127 or char.isspace())

        # Clean up excessive newlines and whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)  # Replace 3+ newlines with 2
        # Replace multiple spaces with single space
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\t+", " ", text)  # Replace tabs with spaces

        # Remove special characters that might cause TTS issues
        text = re.sub(r"[^\w\s.,!?;:@$%\-\n]", "", text)

        # Clean up any remaining multiple spaces
        text = re.sub(r" {2,}", " ", text)

        return text.strip()

    except Exception as e:
        logger.error(f"Error cleaning text for voice: {e}")
        return text


def load_mcp_servers_config(
    apify_token: Optional[str] = None,
    mcp_telegram_url: Optional[str] = None,
    telegram_token: Optional[str] = None,
    telegram_channel: Optional[str] = None,
    mcp_youtube_url: Optional[str] = None,
    mcp_tavily_url: Optional[str] = None,
    mcp_arxiv_url: Optional[str] = None,
    mcp_twitter_url: Optional[str] = None,
    apify_actors_list: Optional[List[str]] = None,
    mcp_deepresearch_url: Optional[str] = None,
    mcp_image_generation_url: Optional[str] = None,
    mcp_telegram_parser_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load and configure MCP servers based on provided environment variables.

    Args:
        apify_token: Apify API token
        mcp_telegram_url: Telegram MCP server URL
        telegram_token: Telegram bot token
        telegram_channel: Telegram channel
        mcp_youtube_url: YouTube MCP server URL
        mcp_tavily_url: Tavily MCP server URL
        mcp_arxiv_url: Arxiv MCP server URL
        mcp_twitter_url: Twitter MCP server URL
        apify_actors_list: List of Apify actors to include (defaults to tweet-scraper)
        mcp_deepresearch_url: Deep Research MCP server URL

    Returns:
        Dictionary containing MCP server configurations
    """
    mcp_servers_config = {}

    # Default Apify actors if not specified
    if apify_actors_list is None:
        apify_actors_list = ["apidojo/tweet-scraper"]

    # --- Apify MCP Server ---
    try:
        logger.info(
            f"DEBUG: Checking Apify configuration - APIFY_TOKEN={'SET' if apify_token else 'NOT SET'} ({len(apify_token) if apify_token else 0} chars)"
        )
        if apify_token is not None:
            # Build URL with specific actors to limit what's available
            actors_param = ",".join(apify_actors_list)
            apify_url = f"https://mcp.apify.com/sse?actors={actors_param}"

            mcp_servers_config["apify"] = {
                "transport": "sse",
                "url": apify_url,
                "headers": {"Authorization": "Bearer " + apify_token},
            }
            logger.info(
                f"Apify MCP server configured with {len(apify_actors_list)} specific actors: {apify_actors_list}"
            )
        else:
            logger.info(
                "Apify MCP server not configured - APIFY_TOKEN is None. Skipping..."
            )
    except Exception as e:
        logger.error(f"Error configuring Apify MCP server: {e}")

    # --- Telegram MCP Server ---
    try:
        if mcp_telegram_url and telegram_token and telegram_channel:
            mcp_servers_config["telegram"] = {
                "url": mcp_telegram_url,
                "transport": "streamable_http",
                "headers": {
                    "X-Telegram-Token": telegram_token,
                    "X-Telegram-Channel": telegram_channel,
                },
            }
            logger.info("Telegram MCP server configured")
        else:
            logger.info("Telegram MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Telegram MCP server: {e}")

    # --- YouTube MCP Server ---
    try:
        if mcp_youtube_url and mcp_youtube_url != "":
            mcp_servers_config["youtube"] = {
                "url": mcp_youtube_url,
                "transport": "streamable_http",
            }
            logger.info("YouTube MCP server configured")
        else:
            logger.info("YouTube MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring YouTube MCP server: {e}")

    # --- Tavily MCP Server ---
    try:
        if mcp_tavily_url and mcp_tavily_url != "":
            mcp_servers_config["tavily"] = {
                "url": mcp_tavily_url,
                "transport": "streamable_http",
            }
            logger.info("Tavily MCP server configured")
        else:
            logger.info("Tavily MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Tavily MCP server: {e}")

    # --- Arxiv MCP Server ---
    try:
        if mcp_arxiv_url and mcp_arxiv_url != "":
            mcp_servers_config["arxiv"] = {
                "url": mcp_arxiv_url,
                "transport": "streamable_http",
            }
            logger.info("Arxiv MCP server configured")
        else:
            logger.info("Arxiv MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Arxiv MCP server: {e}")

    # --- Twitter MCP Server ---
    try:
        if mcp_twitter_url and mcp_twitter_url != "":
            mcp_servers_config["twitter"] = {
                "url": mcp_twitter_url,
                "transport": "streamable_http",
            }
            logger.info("Twitter MCP server configured")
        else:
            logger.info("Twitter MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Twitter MCP server: {e}")

    # --- Deep Research MCP Server ---
    try:
        if mcp_deepresearch_url and mcp_deepresearch_url != "":
            mcp_servers_config["deepresearch"] = {
                "url": mcp_deepresearch_url,
                "transport": "streamable_http",
            }
            logger.info("Deep Research MCP server configured")
        else:
            logger.info("Deep Research MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Deep Research MCP server: {e}")

    # --- Image Generation MCP Server ---

    try:
        if mcp_image_generation_url and mcp_image_generation_url != "":
            mcp_servers_config["image_generation"] = {
                "url": mcp_image_generation_url,
                "transport": "streamable_http",
            }
            logger.info("Image Generation MCP server configured")
        else:
            logger.info("Image Generation MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Image Generation MCP server: {e}")

    # --- Telegram Parser MCP Server ---

    try:
        if mcp_telegram_parser_url and mcp_telegram_parser_url != "":
            mcp_servers_config["telegram_parser"] = {
                "url": mcp_telegram_parser_url,
                "transport": "streamable_http",
            }
            logger.info("Telegram Parser MCP server configured")
        else:
            logger.info("Telegram Parser MCP server not configured. Skipping...")
    except Exception as e:
        logger.error(f"Error configuring Telegram Parser MCP server: {e}")

    logger.info(f"Total MCP servers configured: {len(mcp_servers_config)}")

    # Log which servers were configured
    if mcp_servers_config:
        logger.info("Configured MCP servers:")
        for server_name, config in mcp_servers_config.items():
            url = config.get("url", "No URL")
            transport = config.get("transport", "No transport")
            logger.info(f"  - {server_name}: {url} ({transport})")
    else:
        logger.warning(
            "No MCP servers were configured. Check your environment variables."
        )

    return mcp_servers_config


def create_mcp_tasks(
    mcp_tools,
    search_query,
    topic: Optional[str] = None,
    twitter_sources: Optional[List[str]] = None,
    telegram_sources: Optional[List[str]] = None,
):
    """
    Creates MCP tasks using Pydantic schemas for validation, then converts to dict format for tool calls.

    Args:
        mcp_tools: List of available MCP tools
        search_query: The search query string
        topic: Optional topic filter
        twitter_sources: Optional list of Twitter URLs to scrape
        telegram_sources: Optional list of Telegram channels to parse

    Returns:
        Tuple of (tasks, task_names) where tasks are coroutines with validated parameters
    """
    tasks = []
    task_names = []
    for tool in mcp_tools:
        if tool.name == "tavily_web_search":
            # Tavily expects a 'request' parameter with the search data
            tasks.append(
                tool.coroutine(request={"query": search_query, "max_results": 3})
            )
            task_names.append(tool.name)  # Track the name
            logger.info(f"  - Added task: {tool.name}")
        elif tool.name == "parse_telegram_channels":
            if telegram_sources:
                # Create Pydantic schema object for validation, then convert to dict
                request_data = {"channels": telegram_sources, "limit": 3}
                tasks.append(tool.coroutine(**request_data))
                task_names.append(tool.name)  # Track the name
                logger.info(f"  - Added task: {tool.name}")
        elif tool.name == "arxiv_search":
            # Arxiv might also expect a 'request' parameter
            tasks.append(
                tool.coroutine(request={"query": search_query, "max_results": 3})
            )
            task_names.append(tool.name)  # Track the name
            logger.info(f"  - Added task: {tool.name}")
        elif tool.name == "youtube_search_and_transcript":
            # Create Pydantic schema object for validation, then convert to dict
            request_data = {"query": search_query, "max_results": 2}
            tasks.append(tool.coroutine(**request_data))
            task_names.append(tool.name)  # Track the name
            LoggerAdapter.info(f"  - Added task: {tool.name}")
        # This is where you match and activate the Apify tool
        elif tool.name == "apidojo-slash-twitter-scraper-lite":
            logger.info(f"  - Adding task: {tool.name}")

            # Use twitter_sources if available, otherwise use search_query
            if twitter_sources:
                request_data = {
                    "searchTerms": twitter_sources,
                    "maxItems": 20,
                    "proxyConfiguration": {"useApifyProxy": True},
                }
            else:
                request_data = {
                    "searchTerms": [search_query],
                    "maxItems": 20,
                    "proxyConfiguration": {"useApifyProxy": True},
                }

            tasks.append(tool.coroutine(**request_data))
            task_names.append(tool.name)
    return tasks, task_names


def extract_source_info(content: str, source_name: str) -> Dict[str, str]:
    """Extracts Title and URL from a tool's string output."""
    source_info = {"name": source_name, "title": "N/A", "url": "N/A"}

    # Try to find a URL first
    url_match = re.search(r"URL: (https?://[^\s]+)", content)
    if url_match:
        source_info["url"] = url_match.group(1)

    # Try to find a Title
    title_match = re.search(r"Title: ([^\n]+)", content)
    if title_match:
        source_info["title"] = title_match.group(1).strip()
    # If no title, use the first line as a fallback
    elif not title_match:
        source_info["title"] = content.split("\n")[0].strip()

    return source_info


# --- Helper Function 2: To format the final sources list ---


def format_sources(sources: List[Dict[str, str]]) -> str:
    """Formats a list of source dictionaries into a numbered string."""
    if not sources:
        return "No valid sources found."

    formatted_list = []
    for i, source in enumerate(sources):
        # Format as: 1. [Source Name] Title of Content (URL)
        formatted_list.append(
            f"{i + 1}. [{source['name']}] {source['title']} ({source.get('url', 'No URL')})"
        )
    return "\n".join(formatted_list)


def clean_apify_tweet_data(data: str) -> str:
    """
    Cleans the tweet data from Apify to extract relevant fields like text, username, and timestamp.
    This function can handle both a single JSON array of tweets and line-delimited JSON (JSONL).

    Args:
        data: A string containing raw output from Apify.

    Returns:
        A formatted string with the cleaned tweet text, including username and timestamp,
        with each tweet on a new line.
    """
    logger.info(f"Raw Apify data received for cleaning:\n{data}")

    # Extract JSON part from the raw string, as actor output may include summary text
    json_match = re.search(r"(\[.*\])", data, re.DOTALL)
    if json_match:
        json_data = json_match.group(1)
        logger.info("Successfully extracted JSON array from raw input.")
    else:
        logger.warning(
            "Could not find a JSON array in the raw data. Attempting to parse as is."
        )
        json_data = data

    cleaned_tweets_info = []
    tweets = []

    try:
        tweets = json.loads(json_data)
        # Ensure it's a list, as a single tweet object could also be valid JSON
        if not isinstance(tweets, list):
            tweets = [tweets]
        logger.info(f"Successfully parsed data as JSON. Type: {type(tweets)}")
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse data as a single JSON object. Assuming JSONL format."
        )

        for line in data.splitlines():
            try:
                tweet = json.loads(line)
                if isinstance(tweet, dict):
                    tweets.append(tweet)
            except json.JSONDecodeError:
                continue

    # Process the list of tweets
    logger.info(f"Processing {len(tweets)} tweets...")
    for i, tweet in enumerate(tweets):
        logger.info(f"Processing tweet #{i + 1}: {tweet}")
        if isinstance(tweet, dict):
            tweet_text = tweet.get("text")
            if tweet_text:
                cleaned_tweets_info.append(tweet_text)

    logger.info(f"Cleaned {len(cleaned_tweets_info)} tweets successfully.")
    final_result = "\n\n".join(cleaned_tweets_info)
    logger.info(f"Final cleaned tweet text:\n{final_result}")
    return final_result


def get_twitter_sources_for_topic(topic: str, topics_file_path: str) -> List[str]:
    """
    Loads twitter sources from the provided topics file for a given topic.

    Args:
        topic: The topic to get twitter sources for.
        topics_file_path: The path to the topics JSON file.

    Returns:
        A list of twitter source URLs.
    """
    try:
        topics_data = load_json(topics_file_path)
        if topics_data and "topics" in topics_data:
            topic_info = topics_data["topics"].get(topic)
            if topic_info and "twitter_sources" in topic_info:
                logger.info(
                    f"Found {len(topic_info['twitter_sources'])} Twitter sources for topic '{topic}'"
                )
                return topic_info["twitter_sources"]
    except Exception as e:
        logger.error(f"Error getting twitter sources for topic '{topic}': {e}")

    logger.warning(f"No Twitter sources found for topic '{topic}'")
    return []


def get_telegram_sources_for_topic(topic: str, topics_file_path: str) -> List[str]:
    """
    Loads telegram sources from the provided topics file for a given topic.

    Args:
        topic: The topic to get telegram sources for.
        topics_file_path: The path to the topics JSON file.

    Returns:
        A list of telegram source URLs.
    """
    try:
        topics_data = load_json(topics_file_path)
        if topics_data and "topics" in topics_data:
            topic_info = topics_data["topics"].get(topic)
            if topic_info and "telegram_sources" in topic_info:
                logger.info(
                    f"Found {len(topic_info['telegram_sources'])} Telegram sources for topic '{topic}'"
                )
                return topic_info["telegram_sources"]
    except Exception as e:
        logger.error(f"Error getting telegram sources for topic '{topic}': {e}")

    logger.warning(f"No Telegram sources found for topic '{topic}'")
    return []


async def generate_llm_response_async(message: str) -> str:
    llm = initialize_llm("main")
    llm_thinking = initialize_llm("thinking")
    llm_spare = initialize_llm("spare")
    llm = llm.with_fallbacks([llm_spare])
    llm_thinking = llm_thinking.with_fallbacks([llm_spare])
    response = await llm_thinking.ainvoke(message)
    if not response:
        response = clean_response(response.content)
        response = JsonOutputParser().parse(response)
    return response


def initialize_llm_from_config(
    config: Optional[Dict[str, Any]],
) -> Optional[BaseChatModel]:
    """
    Initializes and returns a language model client from a configuration dictionary.
    """
    if not config:
        return None

    logger.info(f"Setting up LLM from config: {config}...")

    model_provider = config.get("provider")
    model_name = config.get("model_name")

    PROVIDER_MAP: Dict[str, Dict[str, Any]] = {
        "together": {
            "class": ChatTogether,
            "api_key_name": "TOGETHER_API_KEY",
            "init_arg": "together_api_key",
        },
        "google": {
            "class": ChatGoogleGenerativeAI,
            "api_key_name": "GOOGLE_API_KEY",
            "init_arg": "google_api_key",
        },
        "mistral": {
            "class": ChatMistralAI,
            "api_key_name": "MISTRAL_API_KEY",
            "init_arg": "api_key",
        },
    }

    if not all([model_provider, model_name]):
        msg = (
            "LLM configuration is incomplete. 'provider' and 'model_name' are required."
        )
        logger.warning(msg)
        return None

    provider_details = PROVIDER_MAP.get(model_provider.lower())
    if not provider_details:
        msg = f"Unsupported model provider: {model_provider}"
        logger.warning(msg)
        return None

    api_key_name = provider_details["api_key_name"]
    # It's better to fetch API keys from the global config/environment
    # instead of passing them in each simulation config.
    global_config = LLMSettings()
    api_key_value = getattr(global_config, api_key_name, None)

    if not api_key_value:
        msg = f"'{api_key_name}' is required for provider '{model_provider}' but is not set in the environment."
        logger.warning(msg)
        return None

    try:
        ModelClass: Type[BaseChatModel] = provider_details["class"]
        init_kwargs = {
            provider_details["init_arg"]: api_key_value,
            "model": model_name,
        }
        # Pass through any other parameters from the config
        extra_params = config.get("parameters", {})
        init_kwargs.update(extra_params)

        llm_instance = ModelClass(**init_kwargs)
        logger.info(
            f"Successfully initialized LLM '{model_name}' from provider '{model_provider}'."
        )
        return llm_instance
    except Exception as e:
        msg = f"Failed to initialize LLM from provider '{model_provider}': {e}"
        logger.warning(msg, exc_info=True)
        return None

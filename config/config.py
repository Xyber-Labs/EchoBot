from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from google.oauth2.credentials import Credentials
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_logging.logger import logger

# Define the path to the root .env file to ensure consistent loading
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"


class YouTubeSettings(BaseSettings):
    """Consolidated settings for all YouTube operations."""

    # Core OAuth Credentials
    OAUTH_CLIENT_ID: str | None = Field(default=None, env="OAUTH_CLIENT_ID")
    OAUTH_CLIENT_SECRET: str | None = Field(default=None, env="OAUTH_CLIENT_SECRET")

    # Refresh Token from environment
    YOUTUBE_REFRESH_TOKEN: str | None = Field(default=None, env="YOUTUBE_REFRESH_TOKEN")

    # Service control and API details
    YOUTUBE_ENABLED: bool = Field(default=True, env="YOUTUBE_ENABLED")
    DEBUG: bool = Field(default=False, env="DEBUG")
    POLL_INTERVAL_SECONDS: int = Field(default=30, env="POLL_INTERVAL_SECONDS")
    PRIVACY_STATUS: str = Field(default="unlisted", env="PRIVACY_STATUS")

    # Chat YouTube Service endpoint (used by other services to call it)
    CHAT_YOUTUBE_HOST: str = Field(default="127.0.0.1", env="CHAT_YOUTUBE_HOST")
    CHAT_YOUTUBE_PORT: int = Field(default=8000, env="CHAT_YOUTUBE_PORT")

    # API constants (rarely changed)
    SCOPES: list[str] = ["https://www.googleapis.com/auth/youtube.force-ssl"]

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )

    @computed_field  # type: ignore[misc]
    @property
    def credentials(self) -> Credentials | None:
        """Authenticate and return OAuth2 credentials using environment variables."""
        if not self.YOUTUBE_ENABLED:
            return None

        logger.info("Using environment-based OAuth with refresh token for YouTube")
        if not all(
            [self.YOUTUBE_REFRESH_TOKEN, self.OAUTH_CLIENT_ID, self.OAUTH_CLIENT_SECRET]
        ):
            logger.error(
                "Missing one or more required YouTube OAuth credentials (YOUTUBE_REFRESH_TOKEN, OAUTH_CLIENT_ID, or OAUTH_CLIENT_SECRET)."
            )
            raise ValueError("Missing YouTube OAuth credentials")

        return Credentials.from_authorized_user_info(
            {
                "refresh_token": self.YOUTUBE_REFRESH_TOKEN,
                "client_id": self.OAUTH_CLIENT_ID,
                "client_secret": self.OAUTH_CLIENT_SECRET,
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            self.SCOPES,
        )


class ScheduleSettings(BaseSettings):
    # Please only use hours here for the intervals
    MEDIA_INITIALIZATION_INTERVAL: int = Field(
        default=2, env="MEDIA_INITIALIZATION_INTERVAL"
    )
    NEWS_GENERATION_INTERVAL: int = Field(default=2, env="NEWS_GENERATION_INTERVAL")
    MUSIC_GENERATION_INTERVAL: int = Field(default=2, env="MUSIC_GENERATION_INTERVAL")
    SOUNDCLOUD_DOWNLOADER_INTERVAL: int = Field(
        default=2, env="SOUNDCLOUD_DOWNLOADER_INTERVAL"
    )

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class Google_drive(BaseSettings):
    GOOGLE_DRIVE_FOLDER_URL: str | None = Field(
        default=None, env="GOOGLE_DRIVE_FOLDER_URL"
    )
    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class LLMSettings(BaseSettings):
    """Configuration settings for the LLMs."""

    TOGETHER_API_KEY: str | None = Field(default=None, env="TOGETHER_API_KEY")
    GOOGLE_API_KEY: str | None = Field(default=None, env="GOOGLE_API_KEY")
    MISTRAL_API_KEY: str | None = Field(default=None, env="MISTRAL_API_KEY")
    MODEL_PROVIDER: str = Field(default="google")
    MODEL_NAME: str = Field(default="gemini-2.5-flash")
    MODEL_PROVIDER_SPARE: str = Field(default="together")
    MODEL_NAME_SPARE: str = Field(default="deepseek-ai/DeepSeek-V3")
    MODEL_PROVIDER_THINKING: Optional[str] = Field(default="google")
    MODEL_NAME_THINKING: Optional[str] = Field(default="gemini-2.5-pro")
    MODEL_VALIDATION_PROVIDER: Optional[str] = Field(default="google")
    MODEL_VALIDATION_NAME: Optional[str] = Field(default="gemini-2.0-flash")

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class SearchMCP_Config(BaseSettings):
    MCP_TAVILY_URL: Optional[str] = Field(default=None, env="MCP_TAVILY_URL")
    MCP_YOUTUBE_URL: Optional[str] = Field(default=None, env="MCP_YOUTUBE_URL")
    MCP_ARXIV_URL: Optional[str] = Field(default=None, env="MCP_ARXIV_URL")
    MCP_DEEP_RESEARCHER_URL: Optional[str] = Field(
        default=None, env="MCP_DEEP_RESEARCHER_URL"
    )
    APIFY_TOKEN: Optional[str] = Field(default=None, env="APIFY_TOKEN")
    MCP_TWITTER_URL: Optional[str] = Field(default=None, env="MCP_TWITTER_URL")
    MCP_APIFY_URL: Optional[str] = Field(default=None, env="MCP_APIFY_URL")
    MCP_IMAGE_GENERATION: Optional[str] = Field(
        default=None, env="MCP_IMAGE_GENERATION"
    )
    APIFY_TWEET_MAX_AGE_DAYS: int = Field(default=3, env="APIFY_TWEET_MAX_AGE_DAYS")
    MCP_TELEGRAM_PARSER_URL: Optional[str] = Field(
        default=None, env="MCP_TELEGRAM_PARSER_URL"
    )

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class AudioSettings(BaseSettings):
    BACKGROUND_MUSIC_VOLUME_NORMAL: float = Field(
        default=0.3, env="BACKGROUND_MUSIC_VOLUME_NORMAL"
    )
    BACKGROUND_MUSIC_VOLUME_DUCKED: float = Field(
        default=0.01, env="BACKGROUND_MUSIC_VOLUME_DUCKED"
    )

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class OBSSettings(BaseSettings):
    OBS_HOST: str = Field(default="", env="OBS_HOST")
    OBS_PORT: int = Field(default=0, env="OBS_PORT")
    OBS_PASSWORD: str = Field(default="", env="OBS_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class SoundcloudSettings(BaseSettings):
    SOUNDCLOUD_CLIENT_ID: str = Field(default="", env="SOUNDCLOUD_CLIENT_ID")
    SOUNDCLOUD_CLIENT_SECRET: str = Field(default="", env="SOUNDCLOUD_CLIENT_SECRET")
    SOUNDCLOUD_CLIENT_CODE: str = Field(default="", env="SOUNDCLOUD_CLIENT_CODE")
    SOUNDCLOUD_ACCESS_TOKEN: str = Field(default="", env="SOUNDCLOUD_ACCESS_TOKEN")
    SOUNDCLOUD_REFRESH_TOKEN: str | None = Field(
        default=None, env="SOUNDCLOUD_REFRESH_TOKEN"
    )
    SOUNDCLOUD_PLAYLIST_NAME: str = Field(default="", env="SOUNDCLOUD_PLAYLIST_NAME")
    SOUNDCLOUD_PLAYLIST_URL: list[str] = Field(
        default=["https://soundcloud.com/your-channel/sets/your-playlist"],
        env="SOUNDCLOUD_PLAYLIST_URL",
    )

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class SunoSettings(BaseSettings):
    SUNO_API_KEY: Optional[str] = Field(default=None, env="SUNO_API_KEY")
    SUNO_CALLBACK_URL: Optional[str] = Field(default=None, env="SUNO_CALLBACK_URL")
    NUMBER_OF_SONGS: int = Field(default=5, env="NUMBER_OF_SONGS")

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class ElevenLabsSettings(BaseSettings):
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: Optional[str] = Field(default=None, env="ELEVENLABS_VOICE_ID")
    ELEVENLABS_MODEL_ID: Optional[str] = Field(default=None, env="ELEVENLABS_MODEL_ID")
    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class MediaSettings(BaseSettings):
    """Defines all media paths based on a single root directory."""

    MEDIA_HOST_DIR: Path | None = Field(default=None, env="MEDIA_HOST_DIR")
    MEDIA_CONTAINER_DIR: Path = Field(
        default=Path("/app/media"), env="MEDIA_CONTAINER_DIR"
    )

    @computed_field
    @property
    def media_root_dir(self) -> Path:
        """Dynamically provides the correct media root path based on environment."""
        if self.MEDIA_HOST_DIR:
            logger.debug(
                f"Running locally. Using MEDIA_HOST_DIR: {self.MEDIA_HOST_DIR}"
            )
            return self.MEDIA_HOST_DIR
        logger.debug(
            f"Running in container. Using MEDIA_CONTAINER_DIR: {self.MEDIA_CONTAINER_DIR}"
        )
        return self.MEDIA_CONTAINER_DIR

    @computed_field
    @property
    def voice_output_dir(self) -> Path:
        return self.media_root_dir / "voice" / "generated_audio"

    @computed_field
    @property
    def news_output_dir(self) -> Path:
        return self.media_root_dir / "news"

    @computed_field
    @property
    def state_output_dir(self) -> Path:
        return self.media_root_dir / "state"

    @computed_field
    @property
    def memory_output_dir(self) -> Path:
        return self.media_root_dir / "memory"

    @computed_field
    @property
    def videos_output_dir(self) -> Path:
        return self.media_root_dir / "videos"

    @computed_field
    @property
    def google_drive_music_dir(self) -> Path:
        return self.media_root_dir / "music" / "google_drive_songs"

    @computed_field
    @property
    def soundcloud_output_dir(self) -> Path:
        return self.media_root_dir / "music" / "soundcloud_songs"

    @computed_field
    @property
    def suno_output_dir(self) -> Path:
        return self.media_root_dir / "music" / "suno_songs"

    @computed_field
    @property
    def music_style_path(self) -> Path:
        # This seems more like config than media, but keeping it consistent for now
        return self.media_root_dir / "state" / "music_style.json"

    @computed_field
    @property
    def music_memory_path(self) -> Path:
        return self.media_root_dir / "state" / "music_generation_history.json"

    @computed_field
    @property
    def config_dir(self) -> Path:
        return self.media_root_dir / "config"

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class AgentConfig(BaseSettings):
    agent_personality_path: Optional[str] = Field(
        default="config/agent_data/Agent.json"
    )
    agent_music_style_path: Optional[str] = Field(
        default="config/agent_data/Agent_music_style.json"
    )
    agent_knowledge_path: Optional[str] = Field(
        default="config/agent_data/Agent_knowledge.json",
    )
    agent_chat_rules_path: Optional[str] = Field(
        default="config/agent_data/Agent_chat_rules.json"
    )
    youtube_disclaimer: Optional[str] = Field(
        default="config/agent_data/Youtube_disclaimer.json"
    )
    SCHEDULE_PATH: str = Field(default="config/schedule.json")
    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


class EventNotifierSettings(BaseSettings):
    """Settings for the event notifier service."""

    WEBHOOK_URLS: str | None = Field(
        default="https://your-hub.example.com/api/agents/generic/event",
        env="EVENT_WEBHOOK_URLS",
    )  # Comma-separated list of webhook URLs
    SERVICE_HOST: str = Field(default="127.0.0.1", env="EVENT_NOTIFIER_HOST")
    SERVICE_PORT: int = Field(default=8002, env="EVENT_NOTIFIER_PORT")

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


def to_system_path(settings: Settings, container_path: str) -> str:
    """
    Convert a container path under MEDIA_CONTAINER_DIR into a host path under MEDIA_HOST_DIR.
    If mapping not configured, return original.
    """
    host_root = settings.media.MEDIA_HOST_DIR
    container_root = str(settings.media.MEDIA_CONTAINER_DIR)
    if host_root and container_root:
        p = str(container_path)
        if p.startswith(container_root):
            return (str(host_root) + p[len(container_root) :]).replace("\\", "/")  # noqa
    return container_path


class Settings(BaseSettings):
    # API Keys
    GOOGLE_API_KEY: str | None = Field(default=None, env="GOOGLE_API_KEY")
    TAVILY_API_KEY: str | None = Field(default=None, env="TAVILY_API_KEY")
    MISTRAL_API_KEY: str | None = Field(default=None, env="MISTRAL_API_KEY")
    TOGETHER_API_KEY: str | None = Field(default=None, env="TOGETHER_API_KEY")
    APIFY_TOKEN: str | None = Field(default=None, env="APIFY_TOKEN")
    CARTESIA_API_KEY: str | None = Field(default=None, env="CARTESIA_API_KEY")

    # Nested settings
    media: MediaSettings = MediaSettings()
    youtube: YouTubeSettings = YouTubeSettings()
    llm: LLMSettings = LLMSettings()
    audio: AudioSettings = AudioSettings()
    obs: OBSSettings = OBSSettings()
    soundcloud: SoundcloudSettings = SoundcloudSettings()
    elevenlabs: ElevenLabsSettings = ElevenLabsSettings()
    suno: SunoSettings = SunoSettings()
    agent: AgentConfig = AgentConfig()
    search_mcp: SearchMCP_Config = SearchMCP_Config()
    google_drive: Google_drive = Google_drive()
    schedule: ScheduleSettings = ScheduleSettings()

    event_notifier: EventNotifierSettings = EventNotifierSettings()
    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )


# Global settings instance
settings = Settings()


def to_container_path(settings: Settings, system_or_rel_path: str) -> str:
    """
    Best-effort: if given an absolute host path under MEDIA_HOST_DIR, map to MEDIA_CONTAINER_DIR.
    Otherwise return unchanged.
    """
    host_root = settings.media.MEDIA_HOST_DIR
    container_root = str(settings.media.MEDIA_CONTAINER_DIR)
    if host_root and container_root:
        p = str(system_or_rel_path)
        if p.startswith(str(host_root)):
            return container_root + p[len(str(host_root)) :]
    return system_or_rel_path


# ---- Backward-compat constants (legacy imports) --------------------------- # TODO: this should be removed in the future
# Many modules used to import constants directly from radio.config.
# Keep these aliases so old code keeps working during the transition.

# General API Keys
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
TAVILY_API_KEY = settings.TAVILY_API_KEY
MISTRAL_API_KEY = settings.MISTRAL_API_KEY
TOGETHER_API_KEY = settings.TOGETHER_API_KEY
APIFY_TOKEN = settings.APIFY_TOKEN
CARTESIA_API_KEY = settings.CARTESIA_API_KEY

# Google Drive
GOOGLE_DRIVE_FOLDER_URL = settings.google_drive.GOOGLE_DRIVE_FOLDER_URL

# YouTube (now unified)
SCOPES = settings.youtube.SCOPES
YOUTUBE_ENABLED = settings.youtube.YOUTUBE_ENABLED
OAUTH_CLIENT_ID = settings.youtube.OAUTH_CLIENT_ID
OAUTH_CLIENT_SECRET = settings.youtube.OAUTH_CLIENT_SECRET
OAUTH_REFRESH_TOKEN = (
    settings.youtube.YOUTUBE_REFRESH_TOKEN
)  # Points to the direct token for legacy use


# Schedule
MEDIA_INITIALIZATION_INTERVAL = settings.schedule.MEDIA_INITIALIZATION_INTERVAL
NEWS_GENERATION_INTERVAL = settings.schedule.NEWS_GENERATION_INTERVAL
MUSIC_GENERATION_INTERVAL = settings.schedule.MUSIC_GENERATION_INTERVAL
SOUNDCLOUD_DOWNLOADER_INTERVAL = settings.schedule.SOUNDCLOUD_DOWNLOADER_INTERVAL
SOUNDCLOUD_REFRESH_TOKEN = settings.soundcloud.SOUNDCLOUD_REFRESH_TOKEN


# LLM
MODEL_PROVIDER = settings.llm.MODEL_PROVIDER
MODEL_NAME = settings.llm.MODEL_NAME
MODEL_VALIDATION_PROVIDER = settings.llm.MODEL_VALIDATION_PROVIDER
MODEL_VALIDATION_NAME = settings.llm.MODEL_VALIDATION_NAME
MODEL_PROVIDER_SPARE = settings.llm.MODEL_PROVIDER_SPARE
MODEL_NAME_SPARE = settings.llm.MODEL_NAME_SPARE

# Audio
BACKGROUND_MUSIC_VOLUME_NORMAL = settings.audio.BACKGROUND_MUSIC_VOLUME_NORMAL
BACKGROUND_MUSIC_VOLUME_DUCKED = settings.audio.BACKGROUND_MUSIC_VOLUME_DUCKED

# OBS
OBS_HOST = settings.obs.OBS_HOST
OBS_PORT = settings.obs.OBS_PORT
OBS_PASSWORD = settings.obs.OBS_PASSWORD

# ElevenLabs
ELEVENLABS_API_KEY = settings.elevenlabs.ELEVENLABS_API_KEY
ELEVENLABS_VOICE_ID = settings.elevenlabs.ELEVENLABS_VOICE_ID
ELEVENLABS_MODEL_ID = settings.elevenlabs.ELEVENLABS_MODEL_ID

# Media Paths (new unified way)
VOICE_OUTPUT_DIR = settings.media.voice_output_dir
NEWS_OUTPUT_DIR = settings.media.news_output_dir
STATE_OUTPUT_DIR = settings.media.state_output_dir
MEMORY_OUTPUT_DIR = settings.media.memory_output_dir
VIDEOS_OUTPUT_DIR = settings.media.videos_output_dir
GOOGLE_DRIVE_MUSIC_DIR = settings.media.google_drive_music_dir
SOUNDCLOUD_OUTPUT_DIR = settings.media.soundcloud_output_dir
SUNO_OUTPUT_DIR = settings.media.suno_output_dir
MUSIC_STYLE_PATH = settings.media.music_style_path
MUSIC_MEMORY_PATH = settings.media.music_memory_path

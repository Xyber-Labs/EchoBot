import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from radio.dev.obs.switch_media_sources import run_media_source_cycler_for
from radio.services.obs_service import OBSService

from config.config import Settings

# Resolve project root relative to this file and try loading .env from there first
PROJECT_ROOT = Path(__file__).resolve().parents[3]
explicit_env = PROJECT_ROOT / ".env"
loaded = False

if explicit_env.exists():
    load_dotenv(explicit_env, override=False)
    loaded = True
else:
    # Fallback: search upwards for the nearest .env
    found = find_dotenv()
    if found:
        load_dotenv(found, override=False)
        explicit_env = Path(found)
        loaded = True

# Debug info to understand what's happening
print(f"CWD: {os.getcwd()}")
print(f"Attempted .env path: {explicit_env}")
print(f".env exists: {explicit_env.exists()}")
print(f"Loaded .env: {loaded}")
print("OBS_HOST =", os.getenv("OBS_HOST"))
print("RADIO_DISABLE_OBS =", os.getenv("RADIO_DISABLE_OBS"))

if __name__ == "__main__":
    settings = Settings()
    obs = OBSService(settings.obs)
    obs.ensure_connected()

    # switch_scenes(obs)
    # switch_subscenes(10, obs)
    run_media_source_cycler_for(10, obs)

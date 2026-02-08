import json
import random
import time
import os
import subprocess
from datetime import datetime, timezone

import sys
from pathlib import Path

# Ensure this service folder is on the Python path (needed when launched via start_services.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_utils import find_latest_audio_file

# -------------------------
# Core EchoPulse settings
# -------------------------
PULSE_FILE = os.getenv("ECHOPULSE_SOURCE", "app/media/state/pulse.json")
INTERVAL_MINUTES = int(os.getenv("ECHOPULSE_INTERVAL_MINUTES", "60"))

VOICE_DIR = os.getenv("ECHOPULSE_VOICE_DIR", "app/media/voice/pulse")
AUDIO_TOPIC = os.getenv("ECHOPULSE_AUDIO_TOPIC", "pulse")

# -------------------------
# OBS settings (optional)
# -------------------------
# Set ECHOPULSE_OBS_ENABLED=1 to enable OBS switching
OBS_ENABLED = os.getenv("ECHOPULSE_OBS_ENABLED", "0") == "1"
OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

OBS_SCENE = os.getenv("ECHOPULSE_OBS_SCENE", "pulse_scene")
OBS_RETURN_SCENE = os.getenv("ECHOPULSE_OBS_RETURN_SCENE", "default_scene")


def load_pulses():
    try:
        with open(PULSE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[echopulse] failed to load pulse file: {e}")
        return []


def try_play_pulse_audio() -> str | None:
    """
    Best-effort: find and play newest audio file matching:
    {VOICE_DIR}/audio_<topic>_*.mp3 (or other extensions if you updated audio_utils.py)
    Returns the audio path if found, else None.
    """
    audio_path = find_latest_audio_file(topic=AUDIO_TOPIC, voice_dir=VOICE_DIR)

    if not audio_path:
        print(f"[echopulse] no audio file found to play for topic '{AUDIO_TOPIC}'")
        return None

    print(f"[echopulse] playing audio: {audio_path}")

    # macOS playback (afplay)
    try:
        subprocess.run(["afplay", audio_path], check=False)
    except Exception as e:
        print(f"[echopulse] failed to play audio: {e}")

    return audio_path


def obs_get_client():
    """
    Creates an OBS websocket client if enabled and credentials exist.
    Uses obsws-python (obsws_python).
    """
    if not OBS_ENABLED:
        return None

    if not OBS_PASSWORD:
        print("[echopulse] OBS enabled but OBS_PASSWORD is not set. Skipping OBS.")
        return None

    try:
        import obsws_python as obs
    except Exception as e:
        print("[echopulse] obsws_python not installed. Install with: pip3 install obsws-python")
        print(f"[echopulse] OBS import error: {e}")
        return None

    try:
        return obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD, timeout=3)
    except Exception as e:
        print(f"[echopulse] failed to connect to OBS at ws://{OBS_HOST}:{OBS_PORT}: {e}")
        return None


def obs_switch_scene(client, scene_name: str) -> bool:
    """
    Switch OBS program scene. Tries multiple parameter styles to be robust.
    """
    if not client:
        return False

    # Try keyword styles
    for kwargs in ({"sceneName": scene_name}, {"scene_name": scene_name}, {"scene": scene_name}):
        try:
            client.set_current_program_scene(**kwargs)
            print(f"[echopulse] OBS switched scene -> {scene_name}")
            return True
        except TypeError:
            continue
        except Exception as e:
            print(f"[echopulse] OBS scene switch failed: {e}")
            return False

    # Try positional
    try:
        client.set_current_program_scene(scene_name)
        print(f"[echopulse] OBS switched scene -> {scene_name}")
        return True
    except Exception as e:
        print(f"[echopulse] OBS scene switch failed: {e}")
        return False


def run():
    print("[echopulse] service started")
    print(f"[echopulse] interval: {INTERVAL_MINUTES} minutes")
    print(f"[echopulse] pulse file: {PULSE_FILE}")
    print(f"[echopulse] voice dir: {VOICE_DIR}")
    print(f"[echopulse] audio topic: {AUDIO_TOPIC}")

    if OBS_ENABLED:
        print(f"[echopulse] OBS enabled: ws://{OBS_HOST}:{OBS_PORT}")
        print(f"[echopulse] OBS scene: {OBS_SCENE}")
        print(f"[echopulse] OBS return scene: {OBS_RETURN_SCENE}")
    else:
        print("[echopulse] OBS disabled (set ECHOPULSE_OBS_ENABLED=1 to enable)")

    while True:
        pulses = load_pulses()

        if pulses:
            pulse = random.choice(pulses)
            timestamp = datetime.now(timezone.utc).isoformat()

            print("\n==============================")
            print(f"[echopulse] {timestamp}")
            print(f"[echopulse] {pulse}")
            print("==============================\n")

            # Connect to OBS (optional)
            obs_client = obs_get_client()

            # Switch to pulse scene (optional)
            if obs_client:
                obs_switch_scene(obs_client, OBS_SCENE)

            # Play audio (local) if available
            try_play_pulse_audio()

            # Switch back (optional)
            if obs_client:
                obs_switch_scene(obs_client, OBS_RETURN_SCENE)
        else:
            print("[echopulse] no pulses found")

        time.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run()

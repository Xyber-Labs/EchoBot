# EchoPulse Service

EchoPulse is a minimal scheduled “announcement agent” for EchoBot.

It periodically:
1) reads a list of short messages (“pulses”) from a JSON file
2) prints one with a timestamp
3) optionally plays an audio clip
4) optionally switches OBS scenes before/after playback

This is designed as a contributor-friendly example of an autonomous loop.

---

## Pulse file

Default path:

app/media/state/pulse.json

Example format:

[
  "system check: stream is running smoothly.",
  "market pulse: volatility is quiet right now.",
  "community note: drop a question for the next pulse."
]

---

## Audio (optional)

EchoPulse can play the newest audio file matching this pattern:

app/media/voice/pulse/audio_<topic>_*.mp3

Default topic is `pulse`, so this works:

app/media/voice/pulse/audio_pulse_001.mp3

macOS playback uses `afplay`.

---

## OBS scene switching (optional)

EchoPulse can connect to OBS via WebSocket and switch scenes before/after audio playback.

You need:
- OBS WebSocket server enabled in OBS (Tools → WebSocket Server Settings)
- host/port/password configured

---

## Run locally

Fast test (every 1 minute):

ECHOPULSE_INTERVAL_MINUTES=1 python3 services/echopulse_service/generate_pulse.py

With OBS enabled:

ECHOPULSE_INTERVAL_MINUTES=1 \
ECHOPULSE_OBS_ENABLED=1 \
OBS_HOST=localhost \
OBS_PORT=4455 \
OBS_PASSWORD='YOUR_PASSWORD' \
ECHOPULSE_OBS_SCENE='pulse_scene' \
ECHOPULSE_OBS_RETURN_SCENE='default_scene' \
python3 services/echopulse_service/generate_pulse.py

---

## Environment variables

ECHOPULSE_SOURCE
- Path to pulse.json
- Default: app/media/state/pulse.json

ECHOPULSE_INTERVAL_MINUTES
- How often to publish a pulse
- Default: 60

ECHOPULSE_VOICE_DIR
- Directory containing audio files
- Default: app/media/voice/pulse

ECHOPULSE_AUDIO_TOPIC
- Topic used to select audio files (audio_<topic>_*.mp3)
- Default: pulse

ECHOPULSE_OBS_ENABLED
- Enable OBS scene switching
- Default: 0 (disabled)
- Set to 1 to enable

OBS_HOST / OBS_PORT / OBS_PASSWORD
- OBS WebSocket connection details

ECHOPULSE_OBS_SCENE
- Scene to switch to before playback
- Default: pulse_scene

ECHOPULSE_OBS_RETURN_SCENE
- Scene to switch back to after playback
- Default: default_scene

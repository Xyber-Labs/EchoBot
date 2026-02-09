# EchoBot - AI Agent Context

This document provides essential context for AI agents working on the EchoBot codebase.

## Project Overview

EchoBot is a microservices platform for autonomous AI-powered YouTube live streaming. It controls OBS Studio to manage scenes, plays background music, generates news content with voiceovers, and interacts with YouTube chat.

## Architecture

### Services

| Service | Location | Purpose |
|---------|----------|---------|
| **OBS Stream** | `services/obs_stream_service/` | Core orchestrator - controls OBS, executes playlist |
| **News** | `services/news_service/` | Generates news scripts and voiceovers |
| **Music** | `services/music_service/` | Manages background music (Suno/SoundCloud) |
| **Chat YouTube** | `services/chat_youtube_service/` | YouTube chat interaction |
| **API** | `services/api_service/` | REST API for external control |
| **Event Notifier** | `services/event_notifier_service/` | Webhook forwarding |

### Key Files

| File | Purpose |
|------|---------|
| `config/schedule.json` | Scene registry - defines all available scenes with video/audio paths |
| `services/obs_stream_service/core/playlist.json` | Execution sequence - what scenes play and for how long |
| `services/obs_stream_service/core/flow.py` | **RadioFlow** - main orchestration loop |
| `services/obs_stream_service/services/schedule_service.py` | Reads/writes schedule.json |
| `services/obs_stream_service/services/schedule_updater.py` | Updates audio paths in schedule.json |
| `config/config.py` | Pydantic settings, environment variables |
| `start_services.py` | Service launcher (tmux-based) |
| `services/obs_stream_service/scripts/init_obs_scenes.py` | Auto-creates OBS scenes from schedule.json |

## How Scene Switching Works

```
playlist.json (sequence)     schedule.json (registry)
        │                            │
        ▼                            ▼
    RadioFlow ──────────────────────────────────────►  OBS Studio
        │                                                  │
        │  1. Read next scene from playlist                │
        │  2. Look up scene definition in schedule.json    │
        │  3. Switch OBS scene                             │
        │  4. Update video/audio sources                   │
        │  5. Wait for duration (or audio completion)      │
        │  6. Loop to next scene                           │
        ▼                                                  ▼
    News Service ──► Updates schedule.json with generated audio paths
```

**Important**: `schedule.json` is NOT edited manually during operation. Services update it programmatically (e.g., news service updates `audio_path` after generating voiceovers).

## Background Music System

Background music works differently from scenes:

- **Not a scene**: It's a persistent audio source that plays underneath all scenes
- **Never switch to it**: The "Background-Music" scene in OBS is just a container
- **Auto-ducking**: When a scene has `"has_audio": true`, background music volume automatically drops from `volume_normal` (default 0.3) to `volume_ducked` (default 0.1)
- **Configuration**: Set in `schedule.json` under `background_music` key
- **Management**: RadioFlow manages it automatically - you don't interact with it directly

## Configuration

### Environment Variables (`.env`)

Essential:
- `OBS_HOST`, `OBS_PORT`, `OBS_PASSWORD` - OBS WebSocket connection
- `MEDIA_HOST_DIR` - Absolute path to `app/media/` directory

Optional (for advanced features):
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` - Voice generation
- `TOGETHER_API_KEY` / `GOOGLE_API_KEY` - LLM for news scripts
- `SUNO_API_KEY` - Music generation
- `SOUNDCLOUD_CLIENT_ID` - SoundCloud music downloads (optional)
- `GOOGLE_DRIVE_FOLDER_URL` - Google Drive video sync (optional)
- YouTube OAuth credentials - Chat interaction

**Note**: Google Drive and SoundCloud are optional. If not configured, you can use local media files in `app/media/`.

### Media Structure

```
app/media/
├── videos/              # Scene video files
├── voice/generated_audio/  # Generated voiceovers
├── music/               # Background music
├── news/                # News scripts and memory
├── state/               # Service state
└── memory/              # Agent memory
```

## Common Tasks

### Adding a New Scene

1. Add video file to `app/media/videos/`
2. Add scene definition to `config/schedule.json` under `_available_scenes`
3. Add scene to `playlist.json` with desired duration
4. Run `uv run python -m services.obs_stream_service.scripts.init_obs_scenes` to create OBS scene

### Creating Transition Videos with Text

Use Python + Pillow to create images, then convert to video:

```python
from PIL import Image, ImageDraw, ImageFont

# Create image with text
img = Image.new('RGB', (1920, 1080), color='black')
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 72)
text = "Your Text Here"
bbox = draw.textbbox((0, 0), text, font=font)
x = (1920 - (bbox[2] - bbox[0])) // 2
y = (1080 - (bbox[3] - bbox[1])) // 2
draw.text((x, y), text, fill='white', font=font)
img.save('transition.png')
```

Convert to video:
```bash
ffmpeg -loop 1 -i transition.png -t 3 -pix_fmt yuv420p -vf "scale=1920:1080" videos/transition.mp4
```

### Running Services

```bash
uv run python start_services.py --launch obs          # OBS only
uv run python start_services.py --launch obs news     # OBS + News
uv run python start_services.py --launch              # All services
python start_services.py --stop                       # Stop all
python start_services.py --stop obs                   # Stop specific service
python start_services.py --launch obs --force         # Restart OBS
```

### Managing tmux Sessions

```bash
# List running sessions
tmux ls

# Attach to OBS service
tmux attach -t obs

# Detach from session (while inside tmux)
Ctrl+b, then d

# View logs (while inside tmux)
Ctrl+b, then [    # Enter scroll mode
q                  # Exit scroll mode

# Kill a session
tmux kill-session -t obs
```

### Testing OBS Connection

```python
from services.obs_stream_service.services.obs_service import OBSService
from config.config import settings

obs = OBSService(settings.obs)
obs.switch_scene_smooth("Scene-Music")
```

## Code Patterns

### Settings Access

The settings object is a **singleton**, not a function:

```python
from config.config import settings

# Correct
media_root = settings.media.media_root_dir
obs_host = settings.obs.OBS_HOST

# Incorrect (old pattern, don't use)
settings = get_settings()  # This function doesn't exist
```

### Path Resolution

Media paths in `schedule.json` are **relative**. They get resolved to absolute paths using `MEDIA_HOST_DIR`:

```python
import os
from config.config import settings

# Correct way to resolve paths
media_root = settings.media.media_root_dir
relative_path = "videos/NeverGona.mp4"
absolute_path = os.path.join(media_root, relative_path)
```

### Import Patterns

**Correct imports** (use these):
```python
from services.obs_stream_service.services.schedule_service import ScheduleService
from services.obs_stream_service.obs import init_background_music
from config.config import settings
from LLM import load_agent_personality, load_json
from LLM.llm_utils import generate_llm_response_async, clean_for_voice
```

**Legacy imports to avoid** (obsolete):
```python
from radio.services.schedule_service import ...  # Wrong - "radio" module doesn't exist
from radio.core.flow import RadioFlow            # Wrong
from config.config import get_settings           # Wrong - use "settings" singleton
```

### Schedule Updates (from services)

```python
from services.obs_stream_service.services.schedule_updater import update_scene_audio_path_in_schedule
update_scene_audio_path_in_schedule("ai_robotics_news", audio_path="/path/to/audio.mp3")
```

### Event Notifications

```python
from services.obs_stream_service.services.event_client import send_event
send_event("news_section_started", {"scene": "ai_robotics_news", "duration_seconds": 180})
```

## Dependencies

Required:
- Python 3.13+
- `uv` package manager
- OBS Studio with WebSocket enabled
- ffmpeg (for audio/video duration detection)
- tmux (for service management)

Install via Homebrew (macOS):
```bash
brew install ffmpeg tmux
```

Python packages are managed via `uv sync`.

## Known Issues & Fixes

### Issue: Media initialization crashes service

**Problem**: Service exits with `sys.exit(1)` when SoundCloud/Google Drive are not configured.

**Fix**: Changed to warnings instead of fatal errors in `services/music_service/media/media_service.py`:
- Google Drive and SoundCloud are now optional
- Service continues with local media files if external sources fail

### Issue: Import errors from legacy "radio" module

**Problem**: Old code references `from radio.services...` which doesn't exist.

**Fix**: Update to current structure:
- `radio` → `services.obs_stream_service`
- All imports now use full service paths

### Issue: Project root calculation incorrect

**Problem**: Script couldn't find `.env` file - was only going 2 levels up instead of 3.

**Fix**: In `init_obs_scenes.py`:
```python
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
```

### Issue: Settings imported as function instead of singleton

**Problem**: Code tried `from config.config import get_settings` but that function doesn't exist.

**Fix**: Use the singleton:
```python
from config.config import settings  # It's a pre-initialized object, not a function
```

## Debugging Tips

### tmux Session Management
- Check running sessions: `tmux ls`
- Attach to OBS service: `tmux attach -t obs`
- Detach without stopping: `Ctrl+b, d`
- Services run in sessions matching their names: `obs`, `news`, `music`, `youtube`, `api`, `event_notifier`

### Log Locations
- tmux output shows real-time logs
- Persistent logs in `logs/` directory (if configured)
- API service logs: port 8000 connection errors are normal if API service isn't running

### OBS Connection Issues
- Verify password in `.env` matches OBS WebSocket settings
- Check OBS WebSocket is enabled: Tools → WebSocket Server Settings
- Test connection: `telnet localhost 4455`

### Media Path Issues
- All paths in `schedule.json` are relative to `MEDIA_HOST_DIR`
- Check `MEDIA_HOST_DIR` is absolute path in `.env`
- Verify media files exist: `ls $MEDIA_HOST_DIR/videos/`

### Scene Switching Not Working
- Check playlist.json syntax (must be valid JSON)
- Verify scene names in playlist.json exist in schedule.json `_available_scenes`
- Attach to tmux session to see real-time errors: `tmux attach -t obs`

## Project History Notes

### Code Smells to Watch For
- Legacy "radio" imports scattered throughout codebase
- Inconsistent path handling (some code uses relative paths incorrectly)
- Duplicated settings initialization in some files
- Mix of old and new import patterns

### Active Development Areas
- Scene management and playlist execution (stable)
- Media initialization (recently fixed to handle optional services)
- Background music ducking system (working)
- News generation with voiceovers (requires API keys)
- YouTube chat integration (requires OAuth setup)

## Quick Reference

### File Locations
- Scenes config: `config/schedule.json`
- Playlist: `services/obs_stream_service/core/playlist.json`
- Environment: `.env`
- Service launcher: `start_services.py`
- OBS scene creator: `services/obs_stream_service/scripts/init_obs_scenes.py`

### Common Commands
```bash
# Setup
uv sync
cp .example.env .env

# Run
uv run python start_services.py --launch obs

# Debug
tmux attach -t obs
tmux ls

# Stop
python start_services.py --stop
```

### Port Reference
- OBS WebSocket: 4455 (configurable)
- API Service: 8000
- Log Service: 8000

---

**Last Updated**: 2026-02-09
**Maintained by**: AI Agents + Human Contributors

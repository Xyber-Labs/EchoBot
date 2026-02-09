<div align="center">

# 🎬 EchoBot

The ultimate framework for **AI Agents** to go live on YouTube

Microservices-based platform that enables AI personas to autonomously host dynamic live streams — from content generation to OBS studio controls

[![Python](https://img.shields.io/badge/Python-3.13+-yellow?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![OBS](https://img.shields.io/badge/OBS-WebSocket-purple?logo=obsstudio)](https://obsproject.com)
[![YouTube](https://img.shields.io/badge/YouTube-Live-red?logo=youtube)](https://www.youtube.com/@XyLumira)

</div>

## 🎥 See it in Action

Check out a working example of EchoBot in action:

- **[XyLumira YouTube Channel](https://www.youtube.com/@XyLumira)** - A live streaming agent powered by EchoBot

## ✨ Features

- **Microservices Architecture**: A scalable and maintainable architecture with dedicated services for each core functionality.
- **Dynamic Scheduling**: Control your broadcast in real-time by editing a `schedule.json` file.
- **OBS Automation**: Seamlessly switch scenes, manage media, and control your stream via OBS WebSockets.
- **Autonomous Agent Content**: The AI Agent automatically generates news reports, voiceovers, and music to keep the stream fresh and engaging.
- **Unified Media Management**: A centralized media directory simplifies content management and ensures consistent access across all services.
- **Live Agent Interaction**: The AI Agent engages with your audience in real-time via YouTube chat, answering questions and reacting to comments.

## 🏗️ Architecture

| Service | Description |
|---------|-------------|
| **API Service** | Exposes an API for managing the streaming agent and its services |
| **Chat YouTube Service** | Manages YouTube chat interaction and AI-powered responses |
| **Music Service** | Handles music generation, downloads, and playback |
| **News Service** | Aggregates news and generates scripts for the AI persona |
| **OBS Stream Service** | Controls OBS and manages the live stream |
| **Event Notifier Service** | Receives events from other services and forwards them to configured webhook URLs |

## 📌 Status

EchoBot is under active development. Community contributions are welcome via pull requests.

---

## 📋 Prerequisites

Install the following tools before proceeding:


| Tool | Purpose |
|------|---------|
| **Python 3.13+** | Runtime |
| **ffmpeg** | Audio/video duration detection |
| **tmux** | Service management (required by start_services.py) |
| **OBS Studio** | Stream control (has built-in WebSocket server) |
| **Docker** | Optional, for containerized deployment |

**Install via Homebrew (macOS/Linux):**
```bash
brew install ffmpeg tmux
```

---

## 🚀 Quickstart

### 1. Install `uv` Package Manager

If you don't have `uv` installed, install it with the following command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Install Dependencies

```bash
git clone <repository-url>
cd echobot
uv sync
```

### 3. Create Environment File

```bash
cp .example.env .env
```

Edit `.env` with minimum required values:

```env
# OBS Connection
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your_obs_password

# Media root (absolute path to your media folder)
MEDIA_HOST_DIR=/path/to/echobot/app/media
```

### 4. Enable OBS WebSocket

1. Open OBS Studio
2. **Menu bar** (top of screen on macOS) → **Tools** → **WebSocket Server Settings**
3. Check "Enable WebSocket server"
4. Set a password and note the port (default: 4455)
5. Click OK

### 5. Create Media Directories

```bash
mkdir -p app/media/{videos,voice/generated_audio,music,news,state,memory}
```


### 6. Prepare Your Media 🎞️

All media files are stored in `app/media/`:

```
app/media/
├── videos/              # Your video files (.mp4, .mov, .webm)
├── music/               # Background music and soundtracks (.mp3, .wav)
└── voice/generated_audio/  # Generated voiceovers (auto-created by news service)
```

**Videos**: Place all video files in `app/media/videos/`
- Use for scene backgrounds (looping animations, DJ visuals, etc.)
- Supported formats: `.mp4`, `.mov`, `.webm`
- Tip: Videos without audio track work best (audio is managed separately)

**Music**: Place audio files in `app/media/music/`
- Use for background music that plays continuously
- Supported formats: `.mp3`, `.wav`


### 7. Configure Your Scenes 📅

EchoBot uses **two configuration files** to control what plays and when:

| File | Purpose |
|------|---------|
| `config/schedule.json` | **Scene Registry** — defines available scenes with their video/audio files |
| `services/obs_stream_service/core/playlist.json` | **Execution Sequence** — defines which scenes play and for how long |

#### Step 1: Edit `config/schedule.json`

Define all available scenes and match them to your media files:

```jsonc
{
  "background_music": {
    "enabled": true,
    "file_path": "music/song.mp3",      // Your music file from step 6
    "loop": true,
    "volume_normal": 0.3,
    "volume_ducked": 0.1
  },
  "current_scene": {
    "scene_name": "Scene-Music",
    "video_path": "videos/visual.mp4",
    "has_audio": false
  },
  "_available_scenes": {
    "music": {                           // Scene identifier (use this in playlist.json)
      "scene_name": "Scene-Music",       // OBS scene name (will be auto-created)
      "video_path": "videos/visual.mp4", // Your video file from step 6
      "video_source_name": "MusicVideo", // [Required] Unique identifier
      "has_audio": false,                // [Required] false = music stays at 30%
      "loop_video": true                 // [Required] true = loops forever
    }
    // Add more scenes here as needed
  }
}
```

#### Step 2: Edit `services/obs_stream_service/core/playlist.json`

Define the execution sequence:

```jsonc
{
    "variables": {
        "music_duration": 300           // 5 minutes in seconds
    },
    "playlist": [
        {
            "scene_name": "music",      // References "music" from schedule.json above
            "duration": "$music_duration"
        }
        // Add more scenes here to create a sequence
    ]
}
```

**How it works:**
- RadioFlow reads the `playlist` array sequentially
- For each scene, it looks up the definition in `schedule.json`
- After the duration expires, it moves to the next scene
- When the playlist ends, it loops back to the beginning
- The system runs **fully autonomously** — no manual intervention required

#### Step 3: Auto-Create OBS Scenes

Run this script to create all scenes in OBS automatically:

```bash
uv run python -m services.obs_stream_service.scripts.init_obs_scenes
```

This reads your `schedule.json` and creates the OBS scenes with video/audio sources.

---

## 9. Running EchoBot ▶️

### Launch the OBS Service

```bash
uv run python start_services.py --launch obs
```

This will:
- Connect to OBS via WebSocket
- Loop through the playlist automatically
- Switch scenes, manage audio ducking, and cycle media sources

### How Scene Switching Works

1. **RadioFlow** reads `playlist.json` and executes scenes sequentially
2. For each scene, it looks up the definition in `schedule.json`
3. News/Music services update `schedule.json` with generated content paths
4. When a scene with `duration: null` is reached, it waits for audio to complete
5. The playlist loops forever

**No manual intervention required** — the system is fully autonomous once launched.

### Managing Services

```bash
# Launch specific services
python start_services.py --launch obs

# Stop all services
python start_services.py --stop

# Stop specific service
python start_services.py --stop obs

# Restart a service
python start_services.py --launch obs --force
```

Available services: `youtube`, `obs`, `music`, `news`, `api`, `event_notifier`

---

## 📁 Media Directory Structure

All media paths in `schedule.json` are relative to `MEDIA_HOST_DIR`:

```
app/media/
├── videos/              # Video files for scenes
├── voice/
│   └── generated_audio/ # Generated voiceovers
├── music/               # Background music
├── news/                # Generated news scripts
├── state/               # Service state files
└── memory/              # Agent memory
```


## ⚙️ Optional: Advanced Features

The following features require additional API keys and configuration. See `.example.env` for all available options.

### 📰 News Generation Service

Generates AI news reports with voiceover. Requires:
- ElevenLabs API key (voice generation)
- LLM provider API key (script generation)

### 🎵 Music Generation Service

Generates original music. Requires:
- Suno API key or SoundCloud credentials

### 💬 YouTube Chat Service

Enables live chat interaction. Requires:
- YouTube API credentials
- OAuth configuration

### 🔔 Event Notifier Service

Forwards events to external webhooks for integration with your website or other services. Configure `EVENT_WEBHOOK_URLS` in `.env`.

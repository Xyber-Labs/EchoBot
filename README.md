# EchoBot - AI Agent Streaming Platform for YouTube x

EchoBot is the ultimate framework for **AI Agents** to go live. It is a powerful, microservices-based platform that enables AI personas to autonomously host dynamic YouTube live streams, managing everything from content generation to OBS studio controls.

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

- **API Service**: Exposes an API for managing the streaming agent and its services.
- **Chat YouTube Service**: Manages YouTube chat interaction and AI-powered responses.
- **Music Service**: Handles music generation, downloads, and playback.
- **News Service**: Aggregates news and generates scripts for the AI persona.
- **OBS Stream Service**: Controls OBS and manages the live stream.
- **Event Notifier Service**: Receives events from other services and forwards them to configured webhook URLs (e.g., your website).

## 🛠️ Setup

### Prerequisites

- **Python 3.13+**
- **Docker** and **Docker Compose**
- **OBS Studio** with the WebSocket plugin enabled
- **`uv`** package manager

### 1. Install `uv`

If you don't have `uv` installed, you can install it with the following command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the Repository

```bash
git clone <repository-url>
cd echobot
```

### 3. Set Up the Environment

First, create a virtual environment and install the required dependencies:

```bash
uv sync
source .venv/bin/activate
```

Next, copy the example environment file and update it with your credentials:

```bash
cp .env.example .env
```

You will need to fill in your API keys for Google, ElevenLabs, and any other services you plan to use.

You also need to configure the paths for the unified media directory in your `.env` file. Set `MEDIA_HOST_DIR` to the **absolute path** of the `app/media` directory within your project. `MEDIA_CONTAINER_DIR` should be left as `/app/media`.

```env
# .env
MEDIA_HOST_DIR=/path/to/your/project/echobot/app/media
MEDIA_CONTAINER_DIR=./app/media
```

### 4. Configure OBS

1.  In OBS, go to **Tools** -> **WebSocket Server Settings**.
2.  Enable the WebSocket server and set a password.
3.  Update your `.env` file with your OBS host, port, and password.

### 5. Configure Event Notifier (Optional)

If you want to receive event notifications (e.g., when news sections start) on your website or external service:

1. Add your webhook URL(s) to your `.env` file:
   ```env
   EVENT_WEBHOOK_URLS=https://your-hub.example.com/api/agents/generic/event
   ```
   Or multiple URLs (comma-separated):
   ```env
   EVENT_WEBHOOK_URLS=https://your-hub.example.com/api/agents/generic/event,https://dev.example.com/api/agents/generic/event
   ```

2. Your webhook endpoint should accept POST requests with JSON payloads like:
   ```json
   {
     "event": "news_section_started",
     "timestamp": "2024-01-15T14:30:00Z",
     "scene": "ai_robotics_news",
     "audio_file": "audio_ai_robotics_20240115_143000.mp3",
     "duration_seconds": 180.5
   }
   ```

3. The event_notifier service runs on port `8002` by default (configurable via `EVENT_NOTIFIER_PORT`).

### 6. Set Up the Media Directory

The platform uses a unified media directory to manage all content. To set it up, run the following script:

```bash
./scripts/setup_media_dirs.sh
```

This will create the `app/media` directory inside your project root, along with all the necessary subdirectories.

## 🚀 Usage

### Running the Services

You can run all the services at once using Docker Compose:

```bash
docker-compose up -d --build
```

To run services, you can use the `start_services.py` script. **Make sure your virtual environment is activated** (see Setup step 3):

```bash
source .venv/bin/activate
```

**To launch all services:**

```bash
python start_services.py --launch
```

**To launch a specific service:**

```bash
python start_services.py --launch <service-name>
```

**To launch multiple specific services:**

```bash
python start_services.py --launch <service-name1> <service-name2> ...
```

**Note**: If the `python` command is not found, use `python3` instead.

For example, to launch the OBS service:

```bash
python start_services.py --launch obs
```

To launch all services except music:

```bash
python start_services.py --launch youtube obs news api event_notifier
```

Available services: `youtube`, `obs`, `music`, `news`, `api`, `event_notifier`.

### Managing Services

The `start_services.py` script also allows you to stop and restart services:

-   **Stop all services**: `python start_services.py --stop`
-   **Stop a specific service**: `python start_services.py --stop <service-name>`
-   **Restart all services**: `python start_services.py --launch --force`
-   **Restart a specific service**: `python start_services.py --launch <service-name> --force`

**Examples:**
```bash
# Restart the YouTube service
python start_services.py --launch youtube --force

# Restart the OBS service
python start_services.py --launch obs --force

# Restart the event_notifier service (useful after changing EVENT_WEBHOOK_URLS)
python start_services.py --launch event_notifier --force

# Restart multiple services
python start_services.py --launch obs event_notifier --force
```

**Note**: After changing configuration (like `EVENT_WEBHOOK_URLS` in `.env`), you need to restart the affected service(s) for changes to take effect.

### Testing the Event Notifier Service

To test the event notifier service:

1. **Start the service**:
   ```bash
   python start_services.py --launch event_notifier
   ```

2. **Test the health endpoint**:
   ```bash
   curl http://127.0.0.1:8002/health
   ```

3. **Send a test event to the local event_notifier service** (which will forward it to configured webhooks):
   ```bash
   curl -X POST http://127.0.0.1:8002/events \
     -H "Content-Type: application/json" \
     -d '{
       "event": "news_section_started",
       "data": {
         "scene": "ai_robotics_news",
         "audio_file": "test.mp3",
         "duration_seconds": 180.5
       }
     }'
   ```
   
   This will forward the event to `https://your-hub.example.com/api/agents/generic/event` if configured in your `.env` file.

4. **Test the webhook endpoint directly** (to verify the hub endpoint is working):
   ```bash
   curl -X POST https://your-hub.example.com/api/agents/generic/event \
     -H "Content-Type: application/json" \
     -d '{
       "event": "news_section_started",
       "timestamp": "2024-01-15T14:30:00Z",
       "scene": "ai_robotics_news",
       "audio_file": "test.mp3",
       "duration_seconds": 180.5
     }'
   ```
   
   **Note**: This tests the external webhook endpoint directly. If you get a 404, verify the endpoint path is correct on the hub server.

5. **Test with a webhook testing service** (like [webhook.site](https://webhook.site)):
   - Get a unique webhook URL from webhook.site
   - Add it to your `.env`: `EVENT_WEBHOOK_URLS=https://webhook.site/your-unique-id`
   - Restart the service and send a test event to see it forwarded to your webhook

## Media ##

EchoBot uses a unified media structure to simplify content management. All media files are stored in a single host directory, which is mounted into the container at `/app/media`.

### Directory Structure

```
{PROJECT_ROOT}/app/media/
├── news/
├── voice/generated_audio/
├── music/
│   ├── soundcloud_songs/
│   └── google_drive_songs/
├── state/
├── memory/
└── videos/
```

### How It Works

1.  **Host Directory**: All media is stored in `{PROJECT_ROOT}/app/media` on your local machine.
2.  **Container Mount**: This directory is mounted to `/app/media` in the container.
3.  **Path Conversion**: The application provides helper functions to convert between host and container paths, ensuring seamless integration with OBS.

## 🐛 Troubleshooting

### Common Issues

-   **Command 'python' not found**: If you see this error, use `python3` instead of `python`, or ensure your virtual environment is activated (run `source .venv/bin/activate`).
-   **ModuleNotFoundError when using `python -m start_services.py`**: Don't use `python -m` with the script. Run it directly as `python start_services.py` (or `python3 start_services.py`).
-   **OBS Connection Failed**: Ensure OBS is running and your WebSocket settings are correct.
-   **Container Can't Write Files**: Check that the `{PROJECT_ROOT}/app/media` directory has the correct permissions.
-   **Path Conversion Not Working**: Verify that `MEDIA_HOST_DIR` and `MEDIA_CONTAINER_DIR` are set correctly in your `.env` file.


## Contributor Note

This project is under active development.
Community contributions are welcome via pull requests.

## Setup Notes

Before running EchoBot:
- Make sure Docker is installed
- Copy `.example.env` to `.env`
- Fill required API keys

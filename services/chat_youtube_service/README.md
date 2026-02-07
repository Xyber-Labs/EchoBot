# YouTube Live Chat Service

A sophisticated YouTube live chat interaction system that monitors streams and responds to viewer messages using AI language models. This component integrates seamlessly with the EchoBot streaming system and runs as a standalone FastAPI service.

![Chat agent graph](src/agent/youtube_responder_graph.png)

## ✨ Features

- **FastAPI Server**: Runs as a standalone service with a `/healthcheck` endpoint.
- **Live Chat Monitoring**: Fetches new messages from the active YouTube live stream.
- **AI-Powered Responses**: Uses a configurable LangGraph agent to generate contextual and safe responses.
- **Audience Engagement**: Posts responses back to the live chat to interact with viewers.
- **Automatic Broadcast Management**: Automatically finds the active stream or creates a new one on startup.
- **Memory System**: Remembers which messages have been answered to avoid duplication.
- **Self‑healing runtime**: Detects deleted/ended broadcasts, clears stale state, and automatically re‑initializes to the next valid broadcast without manual intervention.
- **Robust healthcheck**: Returns an active chat URL for both live and upcoming streams; only returns 503 when the broadcast is definitively inactive or missing.

## 🚀 Getting Started

### Prerequisites

- **Python 3.13+**
- **Google Cloud Project** with YouTube Data API v3 enabled.
- An LLM provider API key (e.g., Together AI, Google AI).

### Configuration

#### 1. Environment Variables

This service is configured using environment variables. At the root of the `echobot` project, create a `.env` file if you don't have one. Add the following variables required by this service:

```env
# --- YouTube OAuth (required) ---
# Replace the placeholders below with your actual credentials
OAUTH_CLIENT_ID=<INSERT_YOUR_CLIENT_ID_HERE>.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=<INSERT_YOUR_CLIENT_SECRET_HERE>
YOUTUBE_REFRESH_TOKEN=<INSERT_YOUR_REFRESH_TOKEN_HERE>

# --- Service Control ---
YOUTUBE_ENABLED=true
PRIVACY_STATUS=unlisted  # Options: 'public', 'private', or 'unlisted'

# --- LLM Provider ---
# Add your API keys for any AI services you plan to use
GOOGLE_API_KEY=<INSERT_YOUR_GOOGLE_API_KEY_HERE>
TOGETHER_API_KEY=<INSERT_YOUR_TOGETHER_API_KEY_HERE>
```
*(For a full list of all possible environment variables, see `services/chat_youtube_service/env.example`)*

[09:53, 07/02/2026] mwaqasamin1987: # --- YouTube OAuth (required) ---
# Replace the placeholders below with your actual credentials
OAUTH_CLIENT_ID=<INSERT_YOUR_CLIENT_ID_HERE>.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=<INSERT_YOUR_CLIENT_SECRET_HERE>
YOUTUBE_REFRESH_TOKEN=<INSERT_YOUR_REFRESH_TOKEN_HERE>

# --- Service Control ---
YOUTUBE_ENABLED=true
PRIVACY_STATUS=unlisted  # Options: 'public', 'private', or 'unlisted'

# --- LLM Provider ---
# Add your API keys for any AI services you plan to use
GOOGLE_API_KEY=<INSERT_YOUR_GOOGLE_API_KEY_HERE>
TOGETHER_API_KEY=<INSERT_YOUR_TOGETHER_API_KEY_HERE>
[10:04, 07/02/2026] mwaqasamin1987: ### OAuth Setup (Getting YouTube Refresh Token)

1. *Enable YouTube Data API v3*  
   - Go to Google Cloud Console → APIs & Services → Library → Search "YouTube Data API v3" → Enable.

2. *Configure OAuth Consent Screen*  
   - Choose External, fill app name, support email, developer email → Save.  
   - Add scope: https://www.googleapis.com/auth/youtube.force-ssl.

3. *Create OAuth Client ID*  
   - Go to APIs & Services → Credentials → +CREATE CREDENTIALS → OAuth client ID → Desktop application → Create.  
   - Copy Client ID & Client Secret.

4. *Add Credentials to .env*  
   ```env
   OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
   OAUTH_CLIENT_SECRET=your-client-secret

   Generate Refresh Token
Run: python scripts/get_youtube_refresh_token.py
Browser opens → Login → Allow permissions → Copy token from terminal.

YOUTUBE_REFRESH_TOKEN=your-refresh-token

## 🎮 Usage

### Running the Service Locally

To run the FastAPI server directly for development:

```bash
# From the root of the echobot project
python -m uvicorn services.chat_youtube_service.src.main:app --host 0.0.0.0 --port 8002 --reload
```
You can now access the OpenAPI documentation at [http://localhost:8002/docs](http://localhost:8002/docs).

### Docker Usage

This service is designed to be run as a Docker container.

#### Building the Image

To build the Docker image, run the following command from the **root directory** of the `echobot` project:

```bash
docker build -t chat_youtube_service -f services/chat_youtube_service/Dockerfile .
```

#### Running the Container

Once built, run the container with this command, also from the project root. This command maps the necessary log and media folders and provides the environment variables from your `.env` file.

```bash
docker run -d --rm --name chat_youtube_service_container -p 8002:8002 -v "$(pwd)/logs:/app/logs" -v "$(pwd)/app/media:/app/media" --env-file ./.env chat_youtube_service
```
*(Note: The internal port is now also 8002 for consistency)*

#### Accessing the Service

- **Health Check**: `http://localhost:8002/healthcheck`
- **API Docs**: `http://localhost:8002/docs`
- **Logs**: `docker logs -f chat_youtube_service_container`

## 🛡️ Healthcheck & Self‑Healing Behavior

- The /healthcheck endpoint returns:
- 200 OK with { "chat_url": "<youtube_url>" } if:
  - There is an active live broadcast with chat, or
  - The broadcast is upcoming (waiting room) and chat is available.
- 503 Service Unavailable if the broadcast is missing or inactive.

Self‑Healing Behavior:
- If a broadcast ends or is deleted, the service clears its internal state and tries to start the next valid broadcast automatically.
- After creating a broadcast, it waits ~30 seconds for chat to initialize before marking it unavailable.
- Temporary API or network errors during checks do NOT mark the broadcast invalid, preventing false negatives.

---

**Happy Chatting! 💬🤖**


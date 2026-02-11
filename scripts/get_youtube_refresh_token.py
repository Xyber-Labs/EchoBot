from __future__ import annotations

import sys

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config.config import YouTubeSettings

# This is the scope required by the application to manage your YouTube account.
# It should not be changed.
YOUTUBE_SCOPES = YouTubeSettings().SCOPES


def get_refresh_token(settings: YouTubeSettings) -> str:
    """
    Runs the OAuth 2.0 flow to obtain a refresh token for the YouTube API.

    Uses the client ID and client secret from the provided settings.

    Args:
        settings: An instance of YouTubeSettings containing your credentials.

    Returns:
        The refresh token string.
    """
    print("Starting OAuth2 flow using credentials from your .env file...")

    if not settings.OAUTH_CLIENT_ID or not settings.OAUTH_CLIENT_SECRET:
        print("\n❌ ERROR: OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET are not set.")
        print("Please set these variables in your .env file in the project root.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=YOUTUBE_SCOPES)
        # Force account selection screen and specify the account email
        # Using fixed port 8080 - make sure this is in your OAuth client's authorized redirect URIs
        creds: Credentials = flow.run_local_server(
            port=8080,
            prompt="select_account",  # Force account selection screen
            login_hint="your-email@example.com",  # Hint for the correct account
        )

        if creds.refresh_token:
            return creds.refresh_token
        else:
            print("\n❌ ERROR: Failed to obtain a refresh token.")
            print("Please ensure you have authorized the application correctly.")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ An error occurred during the OAuth flow: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("Loading YouTube settings from your project's .env file...")
    youtube_settings = YouTubeSettings()
    refresh_token = get_refresh_token(youtube_settings)

    print("\n" + "=" * 50)
    print("✅ Successfully obtained refresh token!")
    print("=" * 50)
    print("\nYour refresh token is:\n")
    print(f"{refresh_token}\n")
    print(
        "Please store this token securely in your .env file as YOUTUBE_REFRESH_TOKEN."
    )
    print("\nExample for your .env file:")
    print(f'YOUTUBE_REFRESH_TOKEN="{refresh_token}"')
    print("-" * 50 + "\n")

"""
This script is used to manually refresh the SoundCloud access token using the refresh token.
It reads the current refresh token from the configuration and updates both access and refresh tokens.
"""

import json

import requests

from app_logging.logger import logger
from config.config import Settings

settings = Settings()


def refresh_soundcloud_token():
    """
    Manually refreshes the SoundCloud access token using the refresh token.
    Updates both access and refresh tokens in the configuration.
    """
    # Get credentials from settings
    client_id = settings.soundcloud.SOUNDCLOUD_CLIENT_ID
    client_secret = settings.soundcloud.SOUNDCLOUD_CLIENT_SECRET
    refresh_token = settings.soundcloud.refresh_token

    if not refresh_token:
        logger.error(
            "SOUNDCLOUD_REFRESH_TOKEN is not set in your configuration (neither directly nor via path)."
        )
        return False

    if not client_id or not client_secret:
        logger.error("SOUNDCLOUD_CLIENT_ID or SOUNDCLOUD_CLIENT_SECRET is not set.")
        return False

    # SoundCloud API endpoint for token refresh
    token_url = "https://api.soundcloud.com/oauth2/token"

    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    logger.info("Attempting to refresh SoundCloud access token...")
    logger.info(f"Using Client ID: {client_id}")
    logger.info(f"Using Refresh Token (first 15 chars): {refresh_token[:15]}...")

    try:
        # Send request to SoundCloud API
        response = requests.post(token_url, data=payload)
        response.raise_for_status()

        # Parse response
        data = response.json()
        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")

        if not new_access_token:
            logger.error("Refresh failed: Did not receive a new access token.")
            return False

        # Update access token in settings
        settings.soundcloud.SOUNDCLOUD_ACCESS_TOKEN = new_access_token
        logger.info("Successfully updated SOUNDCLOUD_ACCESS_TOKEN in memory.")

        # Update refresh token if provided
        if new_refresh_token:
            settings.soundcloud.SOUNDCLOUD_REFRESH_TOKEN = new_refresh_token
            save_refresh_token_to_file(new_refresh_token)
            logger.info(
                "Successfully updated SOUNDCLOUD_REFRESH_TOKEN in memory and file."
            )

        print("\n--- SUCCESS! ---")
        print("SoundCloud tokens have been refreshed successfully.")
        print(f"\nNew Access Token: {new_access_token}")
        if new_refresh_token:
            print(f"New Refresh Token: {new_refresh_token}")
        else:
            print("Refresh Token: (unchanged)")

        return True

    except requests.exceptions.HTTPError as http_err:
        logger.error("HTTP error occurred during token refresh:")
        logger.error(f"Status Code: {http_err.response.status_code}")
        logger.error("Error response from SoundCloud:")

        try:
            error_details = http_err.response.json()
            logger.error(json.dumps(error_details, indent=2))
        except json.JSONDecodeError:
            logger.error(http_err.response.text)

        return False

    except Exception as err:
        logger.error(f"An unexpected error occurred during token refresh: {err}")
        return False


def save_refresh_token_to_file(new_refresh_token: str):
    """Saves the new refresh token to the JSON file specified in settings."""
    token_path = settings.soundcloud.SOUNDCLOUD_REFRESH_TOKEN_PATH
    if not token_path:
        logger.warning(
            "SOUNDCLOUD_REFRESH_TOKEN_PATH is not set, cannot save new token to file."
        )
        return

    try:
        # Ensure directory exists
        token_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing or create new dictionary
        try:
            with open(token_path, "r+") as f:
                tokens = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            tokens = {}

        # Update and write back
        tokens["SOUNDCLOUD_REFRESH_TOKEN"] = new_refresh_token
        with open(token_path, "w") as f:
            json.dump(tokens, f, indent=4)

    except Exception as e:
        logger.error(f"Error updating {token_path}: {e}")


def main():
    """Main function to run the token refresh."""
    print("SoundCloud Token Refresh Script")
    print("=" * 40)

    success = refresh_soundcloud_token()

    if success:
        print("\n✅ Token refresh completed successfully!")
        print("You can now use the updated tokens for SoundCloud API calls.")
    else:
        print("\n❌ Token refresh failed!")
        print("Please check your configuration and try again.")
        print(
            "If the refresh token has expired, you may need to run soundcloud_auth.py again."
        )


if __name__ == "__main__":
    main()

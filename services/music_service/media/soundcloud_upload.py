"""
This script is used to upload songs to SoundCloud.
It also handles token refresh and ensures the track and playlist are public for successful addition.
"""

import json
import os
import time

import requests

from app_logging.logger import logger
from config.config import Settings

settings = Settings()


class SoundCloudUploader:
    """
    A class to handle uploading songs to SoundCloud, with automatic token refresh.
    """

    def __init__(self):
        """
        Initializes the SoundCloudUploader with credentials from settings.
        """
        self.client_id = settings.soundcloud.SOUNDCLOUD_CLIENT_ID
        self.client_secret = settings.soundcloud.SOUNDCLOUD_CLIENT_SECRET
        self.access_token = settings.soundcloud.SOUNDCLOUD_ACCESS_TOKEN

        # Dynamically build the path to the token file
        self.token_path = (
            settings.media.media_root_dir / "config" / "soundcloud_refresh_token.json"
        )
        # Force loading the token ONLY from the JSON file, ignoring any environment variables
        self.refresh_token = self._load_refresh_token()

        self.token_url = "https://api.soundcloud.com/oauth2/token"
        self.api_base_url = "https://api.soundcloud.com"

        if not self.access_token:
            logger.error(
                "SOUNDCLOUD_ACCESS_TOKEN is not set. Please run the initial token script first."
            )

    def _load_refresh_token(self) -> str | None:
        """Loads the refresh token from the JSON file."""
        if not self.token_path.exists():
            logger.warning(f"Refresh token file not found at path: {self.token_path}")
            return None
        try:
            with open(self.token_path, "r") as f:
                token_data = json.load(f)
            token = token_data.get("SOUNDCLOUD_REFRESH_TOKEN")
            logger.info(
                f"DEBUG: Successfully loaded refresh token from {self.token_path}. Token: {token}"
            )
            return token
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error reading refresh token from {self.token_path}: {e}")
            return None

    def _get_auth_headers(self):
        """
        Returns the authorization headers for API requests.
        """
        return {"Authorization": f"OAuth {self.access_token}"}

    def _refresh_and_save_tokens(self) -> bool:
        """
        Uses the refresh token to get a new access token and saves it to the .env file.
        Returns True on success, False on failure.
        """
        logger.warning("Access Token has expired. Attempting to refresh...")

        if not self.refresh_token:
            logger.error(
                "Cannot refresh: SOUNDCLOUD_REFRESH_TOKEN is not set in your .env file."
            )
            return False

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        logger.info(f"DEBUG: Attempting token refresh with Client ID: {self.client_id}")
        logger.info(f"DEBUG: Using Refresh Token: {self.refresh_token}")

        try:
            response = requests.post(self.token_url, data=payload)
            response.raise_for_status()
            data = response.json()

            new_access_token = data.get("access_token")
            new_refresh_token = data.get(
                "refresh_token"
            )  # SoundCloud might issue a new one

            if not new_access_token:
                logger.error("Refresh failed: Did not receive a new access token.")
                return False

            # Update the access token in the current instance
            self.access_token = new_access_token
            settings.soundcloud.SOUNDCLOUD_ACCESS_TOKEN = new_access_token
            logger.info("Successfully updated SOUNDCLOUD_ACCESS_TOKEN in memory.")

            if new_refresh_token:
                self.refresh_token = new_refresh_token
                settings.soundcloud.SOUNDCLOUD_REFRESH_TOKEN = new_refresh_token
                self._save_refresh_token(new_refresh_token)
                logger.info(
                    "Successfully updated SOUNDCLOUD_REFRESH_TOKEN in memory and file."
                )

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"An API error occurred during token refresh: {e}")
            if e.response is not None:
                logger.error(f"Error details: {e.response.text}")
            return False

    def _save_refresh_token(self, new_refresh_token: str):
        """Saves the new refresh token to the JSON file."""
        try:
            # Ensure directory exists
            self.token_path.parent.mkdir(parents=True, exist_ok=True)

            # Read existing or create new dictionary
            try:
                with open(self.token_path, "r+") as f:
                    tokens = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                tokens = {}

            # Update and write back
            tokens["SOUNDCLOUD_REFRESH_TOKEN"] = new_refresh_token
            with open(self.token_path, "w") as f:
                json.dump(tokens, f, indent=4)
            logger.info(f"Successfully saved new refresh token to {self.token_path}")

        except Exception as e:
            logger.error(f"Error updating {self.token_path}: {e}")

    def _request_with_retry(self, method: str, url: str, **kwargs):
        """
        Performs a request with retries on connection errors and server errors.
        """
        max_retries = 3
        backoff_factor = 5  # seconds
        for attempt in range(max_retries):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
                return response
            except requests.exceptions.HTTPError as e:
                # For client errors (4xx), don't retry as they are unlikely to succeed.
                # The caller will handle them, e.g., 401 for token refresh.
                if 400 <= e.response.status_code < 500:
                    raise e
                # For server errors (5xx), we can retry.
                logger.warning(
                    f"Server error on attempt {attempt + 1}/{max_retries}: {e}"
                )
                if attempt == max_retries - 1:
                    raise e  # Re-raise the exception on the last attempt
            except requests.exceptions.RequestException as e:
                # For other errors like connection errors (e.g., SSLError).
                logger.warning(
                    f"Connection error on attempt {attempt + 1}/{max_retries}: {e}"
                )
                if attempt == max_retries - 1:
                    raise e

            sleep_time = backoff_factor * (attempt + 1)
            logger.info(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def upload(
        self,
        file_path: str,
        playlist_name: str,
        track_title: str,
        is_retry: bool = False,
    ) -> bool:
        """
        Uploads a song to SoundCloud. Automatically handles token refresh and ensures
        both the track and playlist are public for successful addition.
        """
        if not os.path.exists(file_path):
            logger.error(f"The file '{file_path}' was not found.")
            return False
        if not self.access_token:
            logger.error(
                "SOUNDCLOUD_ACCESS_TOKEN is not set. Please run the initial token script first."
            )
            return False

        try:
            # --- 1. VERIFY AUTHENTICATION ---
            logger.info("Verifying authentication...")
            me_response = self._request_with_retry(
                "get", f"{self.api_base_url}/me", headers=self._get_auth_headers()
            )
            me_data = me_response.json()
            logger.info(f"Successfully authenticated as: {me_data['username']}")

            # --- 2. UPLOAD THE TRACK AS PUBLIC ---
            logger.info(f"Uploading track as PUBLIC: '{track_title}'...")
            track_data = {
                "track[title]": track_title,
                "track[sharing]": "public",
            }  # Ensure track is public
            files = {
                "track[asset_data]": (
                    os.path.basename(file_path),
                    open(file_path, "rb"),
                )
            }
            upload_response = self._request_with_retry(
                "post",
                f"{self.api_base_url}/tracks",
                headers=self._get_auth_headers(),
                data=track_data,
                files=files,
            )
            new_track = upload_response.json()
            new_track_id = new_track["id"]
            logger.info(f"Track uploaded successfully. Track ID: {new_track_id}")

            # --- 3. FIND THE TARGET PLAYLIST ---
            logger.info(f"Searching for playlist: '{playlist_name}'...")
            playlists_response = self._request_with_retry(
                "get",
                f"{self.api_base_url}/me/playlists",
                headers=self._get_auth_headers(),
            )
            target_playlist = next(
                (
                    p
                    for p in playlists_response.json()
                    if p["title"].lower() == playlist_name.lower()
                ),
                None,
            )
            if not target_playlist:
                logger.warning(
                    f"Playlist '{playlist_name}' not found. Track was uploaded but not added to a playlist."
                )
                return True
            playlist_id = target_playlist["id"]
            logger.info(f"Found playlist. Playlist ID: {playlist_id}")

            # --- NEW STEP 3.5: ENSURE PLAYLIST IS PUBLIC ---
            if target_playlist.get("sharing") != "public":
                logger.warning(
                    f"Playlist '{playlist_name}' is private. Changing to public to ensure track can be added."
                )
                playlist_update_payload = {"playlist": {"sharing": "public"}}
                self._request_with_retry(
                    "put",
                    f"{self.api_base_url}/playlists/{playlist_id}",
                    headers=self._get_auth_headers(),
                    json=playlist_update_payload,
                )
                logger.info("Playlist successfully updated to public.")

            # --- 4. ADD THE TRACK TO THE PLAYLIST ---
            current_track_ids = [track["id"] for track in target_playlist["tracks"]]
            new_track_ids = current_track_ids + [new_track_id]
            form_data_payload = {"playlist[tracks][]": new_track_ids}
            self._request_with_retry(
                "put",
                f"{self.api_base_url}/playlists/{playlist_id}",
                headers=self._get_auth_headers(),
                data=form_data_payload,
            )
            logger.info(
                f"SUCCESS! Track '{new_track['title']}' has been added to playlist '{target_playlist['title']}'."
            )
            return True

        except requests.exceptions.RequestException as e:
            # --- Error handling block (no changes here) ---
            if e.response is not None and e.response.status_code == 401:
                if is_retry:
                    logger.error(
                        "Authentication failed even after refreshing the token. Please check your credentials."
                    )
                    return False
                if self._refresh_and_save_tokens():
                    logger.info("Token refreshed successfully. Retrying the upload...")
                    return self.upload(
                        file_path, playlist_name, track_title, is_retry=True
                    )
                else:
                    logger.error(
                        "Could not refresh token. Please run the initial token script to re-authenticate."
                    )
                    return False
            else:
                logger.error(f"An API error occurred: {e}")
                if e.response is not None:
                    logger.error(f"Error details: {e.response.text}")
                return False


def main():
    """Main function to configure and run the script."""
    # --- CONFIGURE YOUR UPLOAD HERE ---
    audio_file_path = "music_generator/soundcloud_songs/Agent - Song Name.mp3"
    target_playlist_name = "Draft"
    new_track_title = "Agent - Track Title"
    # ----------------------------------

    uploader = SoundCloudUploader()
    uploader.upload(
        file_path=audio_file_path,
        playlist_name=target_playlist_name,
        track_title=new_track_title,
    )


if __name__ == "__main__":
    main()

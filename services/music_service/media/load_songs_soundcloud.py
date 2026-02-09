import glob
import os
import re
from pathlib import Path

import requests

from app_logging.logger import logger
from config.config import Settings


class Soundcloud:
    """
    Class to load songs from SoundCloud using the official API.
    """

    def __init__(self, settings: Settings):
        self.client_id = settings.soundcloud.SOUNDCLOUD_CLIENT_ID
        self.client_secret = settings.soundcloud.SOUNDCLOUD_CLIENT_SECRET
        self.access_token = settings.soundcloud.SOUNDCLOUD_ACCESS_TOKEN
        self.settings = settings.soundcloud
        self.output_folder = settings.media.soundcloud_output_dir
        self.urls_to_download = settings.soundcloud.SOUNDCLOUD_PLAYLIST_URL

        self.api_base_url = "https://api.soundcloud.com"

        # Log what we have
        if self.client_id:
            logger.info(
                f"Found SoundCloud CLIENT_ID: {self.client_id[:10]}... (length: {len(self.client_id)})"
            )
        else:
            logger.warning("SOUNDCLOUD_CLIENT_ID is not set in .env file")

        if self.client_secret:
            logger.info(
                f"Found SoundCloud CLIENT_SECRET: {self.client_secret[:10]}... (length: {len(self.client_secret)})"
            )

        if self.access_token:
            logger.info(
                f"Found SoundCloud ACCESS_TOKEN: {self.access_token[:10]}... (length: {len(self.access_token)})"
            )
        else:
            logger.info(
                "SOUNDCLOUD_ACCESS_TOKEN not set - will use Client Credentials grant for public resources"
            )
            # Try to get token via client credentials if we have client_id and secret
            if self.client_id and self.client_secret:
                self._get_client_credentials_token()

        if not self.client_id:
            raise ValueError(
                "SOUNDCLOUD_CLIENT_ID is required. Get it from https://developers.soundcloud.com/"
            )

        if not self.access_token and not self.client_secret:
            raise ValueError(
                "Either SOUNDCLOUD_ACCESS_TOKEN or SOUNDCLOUD_CLIENT_SECRET is required.\n"
                "For public resources, use Client Credentials grant (set CLIENT_SECRET)."
            )

    def _get_auth_headers(self):
        """Returns authorization headers for API requests."""
        if self.access_token:
            return {"Authorization": f"OAuth {self.access_token}"}
        return {}

    def _get_client_credentials_token(self) -> bool:
        """
        Get access token using Client Credentials grant (for public resources).
        According to SoundCloud's security updates, this should be used for server-side access to public resources.
        """
        client_secret = self.settings.SOUNDCLOUD_CLIENT_SECRET

        if not client_secret:
            logger.error(
                "SOUNDCLOUD_CLIENT_SECRET is not set. Cannot get client credentials token."
            )
            return False

        logger.info(
            "Getting access token via Client Credentials grant (for public resources)..."
        )

        token_url = "https://api.soundcloud.com/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": client_secret,
        }

        try:
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            data = response.json()

            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token")

            if new_access_token:
                self.access_token = new_access_token
                logger.info(f"✅ Successfully obtained client credentials token")

                if new_refresh_token:
                    self.settings.SOUNDCLOUD_REFRESH_TOKEN = new_refresh_token
                    logger.info("✅ Got refresh token")

                return True
            else:
                logger.error("Client credentials failed: No access token in response")
                logger.error(f"Response: {data}")
                return False

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Failed to get client credentials token: HTTP {e.response.status_code}"
            )
            logger.error(f"Response: {e.response.text}")
            return False

    def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        refresh_token = self.settings.SOUNDCLOUD_REFRESH_TOKEN
        client_secret = self.settings.SOUNDCLOUD_CLIENT_SECRET

        if not refresh_token:
            logger.warning(
                "SOUNDCLOUD_REFRESH_TOKEN is not set. Trying Client Credentials grant instead..."
            )
            return self._get_client_credentials_token()

        if not client_secret:
            logger.error(
                "SOUNDCLOUD_CLIENT_SECRET is not set. Cannot refresh access token."
            )
            return False

        logger.info("Access token expired. Attempting to refresh...")

        token_url = "https://api.soundcloud.com/oauth2/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

        try:
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            data = response.json()

            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token")

            if new_access_token:
                old_token_preview = (
                    self.access_token[:20] if self.access_token else "None"
                )
                self.access_token = new_access_token
                logger.info(f"✅ Successfully refreshed access token")
                logger.debug(
                    f"Old token: {old_token_preview}... -> New token: {new_access_token[:20]}..."
                )

                if new_refresh_token:
                    self.settings.SOUNDCLOUD_REFRESH_TOKEN = new_refresh_token
                    logger.info("✅ Got new refresh token")

                return True
            else:
                logger.warning(
                    "Refresh failed: No access token in response. Trying Client Credentials..."
                )
                return self._get_client_credentials_token()

        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"Failed to refresh token: HTTP {e.response.status_code}. Trying Client Credentials..."
            )
            return self._get_client_credentials_token()

    def _extract_playlist_id_from_url(self, url: str) -> str | None:
        """Try to extract playlist ID or permalink from URL."""
        # URL format: https://soundcloud.com/{username}/sets/{playlist_name}
        # We can try to get it via resolve or extract from URL
        match = re.search(r"soundcloud\.com/([^/]+)/sets/([^/?]+)", url)
        if match:
            username, playlist_name = match.groups()
            return f"{username}/sets/{playlist_name}"
        return None

    def _resolve_url(self, url: str) -> dict:
        """
        Resolve a SoundCloud URL to get resource information.
        Uses the resolve endpoint: /resolve?url=...
        SoundCloud now requires Authorization header for ALL API requests.
        """
        if not self.access_token:
            raise Exception(
                "SOUNDCLOUD_ACCESS_TOKEN is required. SoundCloud API now requires authentication for all requests.\n"
                "Get a token using: ./get_soundcloud_token.sh"
            )

        resolve_url = f"{self.api_base_url}/resolve"
        # According to SoundCloud's security updates, don't use client_id in params when using Authorization header
        params = {"url": url}

        headers = self._get_auth_headers()

        # Log what we're sending for debugging
        logger.debug(f"Resolving URL: {url}")
        logger.debug(f"Headers: {dict(headers)}")
        logger.debug(f"Params: {params}")

        try:
            response = requests.get(
                resolve_url, params=params, headers=headers, timeout=10
            )

            # Log response details
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            if response.status_code == 401:
                # Check if it's a token issue
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else response.text
                )
                logger.error(f"401 Error details: {error_data}")

                # Try refreshing token
                if self._refresh_access_token():
                    logger.info("Retrying with refreshed token...")
                    headers = self._get_auth_headers()
                    response = requests.get(
                        resolve_url, params=params, headers=headers, timeout=10
                    )

                    if response.status_code == 401:
                        error_data = (
                            response.json()
                            if response.headers.get("content-type", "").startswith(
                                "application/json"
                            )
                            else response.text
                        )
                        raise Exception(
                            f"HTTP 401 Unauthorized: Token refresh succeeded but request still fails.\n"
                            f"SoundCloud response: {error_data}\n"
                            f"\nPossible issues:\n"
                            f"  1. SoundCloud's /resolve endpoint may not work with user OAuth tokens\n"
                            f"  2. The token might need different scopes\n"
                            f"  3. SoundCloud API might have changed\n"
                            f"\nTry updating your .env with the fresh tokens and restart the service."
                        )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_data = (
                e.response.json()
                if e.response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else e.response.text
            )
            logger.error(f"HTTP {e.response.status_code} error: {error_data}")

            if e.response.status_code == 401:
                raise Exception(
                    f"HTTP 401 Unauthorized: Cannot resolve URL.\n"
                    f"Error: {error_data}\n"
                    f"\nSoundCloud API requires valid authentication.\n"
                    f"Update your .env with fresh tokens from: ./get_soundcloud_token.sh"
                ) from e
            elif e.response.status_code == 403:
                raise Exception(
                    f"HTTP 403 Forbidden: SoundCloud is blocking the request.\n"
                    f"Error: {error_data}"
                ) from e
            else:
                raise Exception(f"HTTP {e.response.status_code}: {error_data}") from e

    def _get_playlist_tracks(self, playlist_id: int) -> list:
        """Get all tracks from a playlist."""
        if not self.access_token:
            raise Exception("SOUNDCLOUD_ACCESS_TOKEN is required")

        playlist_url = f"{self.api_base_url}/playlists/{playlist_id}"
        # Don't use client_id in params when using Authorization header
        params = {}
        headers = self._get_auth_headers()

        try:
            response = requests.get(playlist_url, params=params, headers=headers)
            response.raise_for_status()
            playlist_data = response.json()
            return playlist_data.get("tracks", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Try refreshing token
                if self._refresh_access_token():
                    logger.info("Retrying playlist request with refreshed token...")
                    headers = self._get_auth_headers()
                    response = requests.get(
                        playlist_url, params=params, headers=headers
                    )
                    response.raise_for_status()
                    playlist_data = response.json()
                    return playlist_data.get("tracks", [])
            logger.error(
                f"Failed to get playlist tracks: HTTP {e.response.status_code}"
            )
            logger.error(f"Response: {e.response.text}")
            raise

    def _get_track_stream_url(self, track_id: int) -> str | None:
        """Get the streaming URL for a track."""
        if not self.access_token:
            logger.error("SOUNDCLOUD_ACCESS_TOKEN is required")
            return None

        track_url = f"{self.api_base_url}/tracks/{track_id}"
        # Don't use client_id in params when using Authorization header
        params = {}
        headers = self._get_auth_headers()

        try:
            response = requests.get(track_url, params=params, headers=headers)
            response.raise_for_status()
            track_data = response.json()

            # Try to get stream URL (might require authentication)
            stream_url = track_data.get("stream_url")
            if stream_url:
                # Don't append client_id - use Authorization header instead
                return stream_url

            # Fallback: try download_url
            download_url = track_data.get("download_url")
            if download_url:
                # Don't append client_id - use Authorization header instead
                return download_url

            logger.warning(f"Track {track_id} has no stream_url or download_url")
            return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Try refreshing token
                if self._refresh_access_token():
                    logger.info("Retrying track request with refreshed token...")
                    headers = self._get_auth_headers()
                    response = requests.get(track_url, params=params, headers=headers)
                    response.raise_for_status()
                    track_data = response.json()
                    stream_url = track_data.get("stream_url")
                    if stream_url:
                        # Don't append client_id - use Authorization header instead
                        return stream_url
            logger.error(
                f"Failed to get track stream URL: HTTP {e.response.status_code}"
            )
            logger.error(f"Response: {e.response.text}")
            return None

    def _sanitize_filename(self, text: str) -> str:
        """Sanitize text for use in filenames."""
        return "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).rstrip()

    def download_track(self, track_data: dict) -> None:
        """Downloads a single track from track data."""
        track_id = track_data.get("id")
        title = track_data.get("title", "Unknown")
        artist = track_data.get("user", {}).get("username", "Unknown")

        # Sanitize filename
        safe_title = self._sanitize_filename(title)
        safe_artist = self._sanitize_filename(artist)
        base_filename = f"{safe_artist} - {safe_title}"

        # Check if track already exists
        if track_id:
            pattern_with_id = os.path.join(
                self.output_folder, f"{base_filename} [{track_id}]*.mp3"
            )
            existing_files = glob.glob(pattern_with_id)
            if existing_files:
                logger.info(
                    f"  Track already exists (same ID): {os.path.basename(existing_files[0])}"
                )
                return
            filename = os.path.join(
                self.output_folder, f"{base_filename} [{track_id}].mp3"
            )
        else:
            filename = os.path.join(self.output_folder, f"{base_filename}.mp3")

        # Handle filename collisions
        counter = 1
        while os.path.exists(filename):
            if track_id:
                filename = os.path.join(
                    self.output_folder, f"{base_filename} [{track_id}] ({counter}).mp3"
                )
            else:
                filename = os.path.join(
                    self.output_folder, f"{base_filename} ({counter}).mp3"
                )
            counter += 1

            if counter > 1000:
                logger.error(f"  Too many filename collisions for {title}, skipping.")
                return

        logger.info(f"  Downloading: {artist} - {title}")

        # Get stream URL
        stream_url = self._get_track_stream_url(track_id)
        if not stream_url:
            logger.error(f"  Failed to get stream URL for {title}")
            return

        try:
            # Download the track
            headers = self._get_auth_headers()
            if not headers:
                logger.error(f"  No Authorization header available for {title}")
                return

            response = requests.get(
                stream_url, headers=headers, stream=True, timeout=30
            )

            # If 401, try refreshing token
            if response.status_code == 401:
                logger.debug(f"  Got 401, refreshing token and retrying...")
                if self._refresh_access_token():
                    headers = self._get_auth_headers()
                    response = requests.get(
                        stream_url, headers=headers, stream=True, timeout=30
                    )

            response.raise_for_status()

            # Save to file
            with open(filename, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            logger.info(f"  ✅ Successfully downloaded: {os.path.basename(filename)}")

        except requests.exceptions.HTTPError as e:
            error_msg = e.response.text[:200] if e.response.text else str(e)
            logger.error(
                f"  Failed to download {title}. HTTP {e.response.status_code}: {error_msg}"
            )
        except Exception as e:
            logger.error(f"  Failed to download {title}. Error: {e}")

    def download_songs(self) -> None:
        """
        Main function to download all tracks from a list of SoundCloud URLs,
        which can be single tracks or playlists.
        """
        os.makedirs(self.output_folder, exist_ok=True)
        logger.info(f"Songs will be saved in: {self.output_folder}")
        logger.info(f"Found {len(self.urls_to_download)} URL(s) to process.")

        for i, url in enumerate(self.urls_to_download):
            logger.info(
                f"\n--- Processing URL {i + 1}/{len(self.urls_to_download)} ---"
            )
            logger.info(f"Resolving: {url}")

            try:
                # Resolve the URL
                resolved_data = self._resolve_url(url)
                resource_type = resolved_data.get("kind")

                if resource_type == "playlist":
                    playlist_id = resolved_data.get("id")
                    playlist_title = resolved_data.get("title", "Unknown Playlist")
                    logger.info(
                        f"Playlist found: '{playlist_title}' (ID: {playlist_id})"
                    )

                    # Get all tracks from the playlist
                    tracks = self._get_playlist_tracks(playlist_id)
                    logger.info(f"Found {len(tracks)} tracks in playlist.")

                    # Download each track
                    for track_data in tracks:
                        self.download_track(track_data)

                elif resource_type == "track":
                    logger.info("Single track found.")
                    self.download_track(resolved_data)

                else:
                    logger.warning(f"Unknown resource type: {resource_type}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Error processing {url}:\n{error_msg}")
                import traceback

                logger.debug(f"Full traceback:\n{traceback.format_exc()}")

        logger.info("\nScript finished.")


if __name__ == "__main__":
    settings = Settings()
    soundcloud_downloader = Soundcloud(settings)
    soundcloud_downloader.download_songs()

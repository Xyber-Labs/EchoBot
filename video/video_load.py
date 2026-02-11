import os
import time

import gdown

from app_logging.logger import logger
from config.config import Settings


def main():
    settings = Settings()
    # The public Google Drive folder URL
    folder_url = settings.google_drive.GOOGLE_DRIVE_FOLDER_URL

    # Validate that the URL is set
    if not folder_url:
        logger.error("❌ GOOGLE_DRIVE_FOLDER_URL is not set in .env file!")
        logger.error(
            "Please add GOOGLE_DRIVE_FOLDER_URL=https://drive.google.com/drive/folders/YOUR_FOLDER_ID?usp=sharing to your .env file"
        )
        return

    # The path to the folder where you want to save the files.
    # This will create a 'videos' subfolder in the same directory as the script.
    output_folder = str(settings.media.videos_output_dir)
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)
    logger.info(f"Files will be saved in: {output_folder}")

    try:
        logger.info(f"\nDownloading all files from folder: {folder_url}")

        # Get the list of files to download without downloading them
        files_to_download = gdown.download_folder(
            url=folder_url,
            output=output_folder,
            quiet=True,
            skip_download=True,
            remaining_ok=True,  # Allow more than 50 files
        )
        logger.info(f"Files to download: {files_to_download}")
        if not files_to_download:
            logger.warning("No files found in the Google Drive folder.")
            return

        # Check which files already exist locally
        existing_files = set()
        if os.path.exists(output_folder):
            # Get just the filenames (not full paths) for comparison
            existing_files = {
                f
                for f in os.listdir(output_folder)
                if os.path.isfile(os.path.join(output_folder, f))
            }
            logger.info(f"Found {len(existing_files)} existing file(s) in local folder")

        # Filter to only download missing files
        files_to_download_filtered = []
        skipped_count = 0
        for file in files_to_download:
            # file.path might be just filename or include subdirectory, extract just the filename
            file_name = os.path.basename(file.path)
            if file_name in existing_files:
                logger.debug(f"Skipping {file_name} - already exists locally")
                skipped_count += 1
            else:
                files_to_download_filtered.append(file)
                logger.debug(f"Missing file detected: {file_name}")

        if skipped_count > 0:
            logger.info(
                f"⏭️  Skipping {skipped_count} file(s) that already exist locally"
            )

        if not files_to_download_filtered:
            logger.info("✅ All files already exist locally. No downloads needed.")
            return

        logger.info(
            f"📥 Downloading {len(files_to_download_filtered)} missing file(s)..."
        )

        # Download each missing file individually with retry logic
        failed_files = []
        for file in files_to_download_filtered:
            file_id = file.id
            file_name = file.path
            output_path = file.local_path

            max_retries = 3
            base_delay = 10  # Base delay in seconds for exponential backoff

            for attempt in range(max_retries):
                try:
                    # Add delay between downloads to avoid rate limiting
                    if attempt > 0:
                        # Exponential backoff: 10s, 20s, 40s
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(
                            f"Retrying download of {file_name} (attempt {attempt + 1}/{max_retries})... Waiting {delay}s before retry..."
                        )
                        time.sleep(delay)
                    else:
                        # Small delay even on first attempt to avoid rate limits
                        time.sleep(3)

                    # Download the file with use_cookies=True for better compatibility
                    gdown.download(
                        id=file_id,
                        output=output_path,
                        quiet=False,
                        use_cookies=True,  # Helps with permission issues
                    )
                    logger.info(f"✅ Successfully downloaded: {file_name}")
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        logger.error(
                            f"Failed to download {file_name} (ID: {file_id}) after {max_retries} attempts: {e}"
                        )
                        failed_files.append((file_name, file_id))
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {file_name}: {e}"
                        )

        if failed_files:
            logger.warning(f"\n⚠️  {len(failed_files)} file(s) failed to download:")
            for file_name, file_id in failed_files:
                logger.warning(f"  - {file_name}")
                logger.warning(
                    f"    Manual download URL: https://drive.google.com/uc?id={file_id}"
                )
            logger.warning("\n💡 Solutions:")
            logger.warning(
                "  1. Check file permissions: Right-click file → Share → 'Anyone with the link'"
            )
            logger.warning("  2. Wait a few minutes and try again (rate limiting)")
            logger.warning("  3. Download manually using the URLs above")
        else:
            logger.info(
                f"✅ All files from Google Drive folder downloaded successfully to: {output_folder}"
            )

    except Exception as e:
        logger.error(f"An error occurred while downloading the folder: {e}")


if __name__ == "__main__":
    main()

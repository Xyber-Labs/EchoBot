"""
Audio file utilities for news generation.
Provides functions to find and manage audio files for different topics.
"""

import os
import glob
from typing import Optional


def find_latest_audio_file(topic: str, voice_dir: str) -> Optional[str]:
    """
    Find the latest valid (non-empty) audio file for a given topic.

    Args:
        topic: The topic name (e.g., "AI_Robotics", "Web3")
        voice_dir: Directory containing audio files

    Returns:
        Full path to the latest valid audio file, or None if none found
    """
    # Clean topic name for filename matching
    clean_topic = topic.lower().replace(" ", "_").replace("-", "_")

    # Look for topic-specific files
    topic_pattern = f"{voice_dir}/audio_{clean_topic}_*.*"
    topic_files = glob.glob(topic_pattern)

    if not topic_files:
        print(f"⚠️  No audio files found for topic '{topic}' in {voice_dir}")
        return None

    # Filter out empty files (0 bytes) and sort by modification time (newest first)
    valid_files = [f for f in topic_files if os.path.getsize(f) > 0]

    if not valid_files:
        print(f"⚠️  No valid (non-empty) audio files found for topic '{topic}'")
        print(f"   Found {len(topic_files)} files but all are empty:")
        for f in topic_files:
            size = os.path.getsize(f)
            print(f"   - {os.path.basename(f)} ({size} bytes)")
        return None

    # Get the latest file
    latest_file = max(valid_files, key=os.path.getmtime)
    file_size = os.path.getsize(latest_file)

    print(
        f"📁 Found latest valid audio file for '{topic}': {os.path.basename(latest_file)} ({file_size} bytes)"
    )
    return latest_file


def list_audio_files_by_topic(voice_dir: str) -> dict[str, list[str]]:
    """
    List all audio files grouped by topic.

    Args:
        voice_dir: Directory containing audio files

    Returns:
        Dictionary mapping topic names to lists of file paths
    """
    all_files = glob.glob(f"{voice_dir}/audio_*.mp3")
    topics = {}

    for file_path in all_files:
        filename = os.path.basename(file_path)
        # Extract topic from filename: audio_topic_timestamp.mp3
        if filename.startswith("audio_") and filename.endswith(".mp3"):
            parts = filename[6:-4].split("_")  # Remove "audio_" and ".mp3"
            if len(parts) >= 2:
                # Topic is everything except the last part (timestamp)
                topic = "_".join(parts[:-1])
                if topic not in topics:
                    topics[topic] = []
                topics[topic].append(file_path)

    # Sort files by modification time (newest first) for each topic
    for topic in topics:
        topics[topic].sort(key=os.path.getmtime, reverse=True)

    return topics


def get_audio_file_info(file_path: str) -> dict:
    """
    Get information about an audio file.

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary with file information
    """
    if not os.path.exists(file_path):
        return {"exists": False, "error": "File does not exist"}

    stat = os.stat(file_path)
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": stat.st_mtime,
        "is_empty": stat.st_size == 0,
        "filename": os.path.basename(file_path),
    }


def main():
    """
    CLI utility to manage audio files.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Audio file utilities for news generation"
    )
    parser.add_argument(
        "--voice-dir",
        default="/Users/wotori/echobot_media/voice/generated_audio",
        help="Directory containing audio files",
    )
    parser.add_argument("--topic", help="Find latest file for specific topic")
    parser.add_argument(
        "--list", action="store_true", help="List all audio files by topic"
    )
    parser.add_argument("--info", help="Get info about specific file")

    args = parser.parse_args()

    if args.list:
        print(f"📁 Audio files in {args.voice_dir}:")
        topics = list_audio_files_by_topic(args.voice_dir)

        if not topics:
            print("   No audio files found")
            return

        for topic, files in topics.items():
            print(f"\n🎵 {topic}:")
            for file_path in files:
                info = get_audio_file_info(file_path)
                status = "✅" if not info["is_empty"] else "❌ (empty)"
                print(f"   {status} {info['filename']} ({info['size_mb']} MB)")

    elif args.topic:
        latest_file = find_latest_audio_file(args.topic, args.voice_dir)
        if latest_file:
            info = get_audio_file_info(latest_file)
            print(f"✅ Latest file: {info['filename']}")
            print(f"   Size: {info['size_mb']} MB")
            print(f"   Path: {latest_file}")
        else:
            print(f"❌ No valid audio file found for topic '{args.topic}'")
            sys.exit(1)

    elif args.info:
        info = get_audio_file_info(args.info)
        if info["exists"]:
            print(f"📄 File: {info['filename']}")
            print(f"   Size: {info['size_mb']} MB ({info['size_bytes']} bytes)")
            print(f"   Empty: {info['is_empty']}")
            print(f"   Path: {args.info}")
        else:
            print(f"❌ {info['error']}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

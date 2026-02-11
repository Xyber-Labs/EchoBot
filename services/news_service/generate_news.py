#!/usr/bin/env python3
"""
Simple command-line interface for manual news generation.

Usage:
    python services/news_service/generate_news.py web3          # Generate Web3 news
    python services/news_service/generate_news.py robotics       # Generate AI Robotics news
    python services/news_service/generate_news.py --help        # Show help
"""

import argparse
import sys
from pathlib import Path

from app_logging.logger import logger

# Add the project root to the Python path BEFORE any other imports
project_root = Path(__file__).parent.parent  # Go up one level from news_generator/
sys.path.insert(0, str(project_root))

# Import modules after path setup - use dynamic imports to prevent reordering


def _import_modules():
    """Import modules after path is set up."""
    global load_dotenv, generate_news_for_web3, generate_news_for_ai_robotics
    from dotenv import load_dotenv  # noqa: E402

    from services.news_service.src.main import (  # noqa: E402
        generate_news_for_ai_robotics, generate_news_for_web3)


# Initialize modules
_import_modules()


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Generate news for specific topics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python services/news_service/generate_news.py web3          # Generate Web3 news (uses cache if fresh)
  python services/news_service/generate_news.py robotics      # Generate AI Robotics news (uses cache if fresh)
  python services/news_service/generate_news.py --force web3  # Force fresh news content (preserves all data)
        """,
    )

    parser.add_argument(
        "topic",
        choices=["web3", "robotics"],
        help="Topic to generate news for (web3 or robotics)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of news content (bypasses cache check, preserves all existing data)",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    logger.info(f"🚀 Starting news generation for {args.topic.upper()}...")
    logger.info()

    try:
        if args.topic == "web3":
            if args.force:
                logger.info(
                    "🔄 Force mode: Generating fresh Web3 news (bypassing cache check)..."
                )
                logger.info("ℹ️  Preserving all existing news memories and audio files")
                logger.info()

            generate_news_for_web3(force=args.force)

        elif args.topic == "robotics":
            if args.force:
                logger.info(
                    "🔄 Force mode: Generating fresh AI Robotics news (bypassing cache check)..."
                )
                logger.info("ℹ️  Preserving all existing news memories and audio files")
                logger.info()

            generate_news_for_ai_robotics(force=args.force)

        logger.info()
        logger.info("✅ News generation completed successfully!")

    except Exception as e:
        logger.info(f"❌ Error generating news: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

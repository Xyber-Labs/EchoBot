#!/usr/bin/env python3
"""
Media Directory Status Checker for EchoBot

Usage:
    python scripts/check_media.py          # Check status
    python scripts/check_media.py --fix    # Fix missing directories
    python scripts/check_media.py --info   # Detailed information
"""

import sys
from pathlib import Path

from radio.utils.media_manager import MediaDirectoryManager

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check EchoBot media directories")
    parser.add_argument("--fix", action="store_true", help="Create missing directories")
    parser.add_argument("--info", action="store_true", help="Show detailed information")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("🎵 EchoBot Media Directory Checker")
    print("=" * 50)

    manager: MediaDirectoryManager = MediaDirectoryManager()

    if args.fix:
        print("🔧 Fixing missing directories...")
        success, created = manager.validate_and_create_directories()

        if created:
            print(f"✅ Created {len(created)} missing directories:")
            for dir_path in created:
                print(f"   - {dir_path}")
        else:
            print("ℹ️  No missing directories to create")

        if success:
            print("✅ All media directories are now valid")
        else:
            print("❌ Some issues remain - check logs for details")

    elif args.info:
        print("📊 Detailed Media Directory Information:")
        print()
        info = manager.get_directory_info()

        for dir_name, details in info.items():
            status = details["status"]
            path = details["path"]
            exists = "EXISTS" if details["exists"] else "MISSING"
            writable = "WRITABLE" if details["writable"] else "NOT_WRITABLE"
            is_dir = "DIR" if details["is_directory"] else "NOT_DIR"

            print(f"{status} {dir_name:20} | {path}")
            print(f"     {'':20} | {exists} | {writable} | {is_dir}")
            print()

    else:
        # Default: just check status
        print("🔍 Checking media directory status...")
        success, created = manager.validate_and_create_directories()

        if success:
            print("✅ All media directories are valid")
        else:
            print("❌ Media directory validation failed")
            print("\n💡 To fix issues, run:")
            print("   python scripts/check_media.py --fix")
            print("\n📊 For detailed info, run:")
            print("   python scripts/check_media.py --info")

        if args.verbose:
            print("\n📋 Directory Summary:")
            manager.print_directory_status()


if __name__ == "__main__":
    main()  # type: ignore

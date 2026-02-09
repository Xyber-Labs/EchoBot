import argparse
import os
import subprocess
import sys

SERVICES: dict[str, str] = {
    # friendly_name -> script path
    "youtube": "services/chat_youtube_service/src/main.py --port 8001",
    "obs": "services/obs_stream_service/src/main.py",
    "music": "services/music_service/src/main.py",
    "news": "services/news_service/src/main.py",
    "api": "services/api/src/main.py --port 8000",
    "event_notifier": "services/event_notifier_service/src/main.py --port 8002",
}


def _tmux_session_exists(session: str) -> bool:
    try:
        return (
            subprocess.run(
                ["tmux", "has-session", "-t", session], capture_output=True
            ).returncode
            == 0
        )
    except FileNotFoundError:
        print(
            "Error: 'tmux' command not found. Please ensure tmux is installed and in your PATH."
        )
        print(
            "This script is intended for environments where tmux is available (e.g., Linux, macOS, or WSL on Windows)."
        )
        sys.exit(1)


def _launch_service(session_name: str, script_cmd: str, force: bool) -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))
    python_executable = sys.executable

    # splits command: ["services/api/src/main.py"] and args: "[--port 8000]"
    script_parts = script_cmd.split()
    script_rel_path = script_parts[0]
    args = " ".join(script_parts[1:])

    # Restart behavior: kill if exists, but only if forced
    if _tmux_session_exists(session_name):
        if not force:
            print(
                f"Service for '{script_rel_path}' is already running in session '{session_name}'. Use -f/--force to restart."
            )
            return
        print(f"Force restarting session '{session_name}'...")
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name], capture_output=True
        )

    module_path = (
        script_rel_path.removeprefix("./").removesuffix(".py").replace(os.sep, ".")
    )
    restart_cmd = (
        f'while true; do "{python_executable}" -m {module_path} {args}; '
        "echo 'Script crashed. Restarting in 5 seconds...'; sleep 5; done"
    )
    tmux_command = ["tmux", "new-session", "-d", "-s", session_name, restart_cmd]
    print(f"Launching service '{session_name}' in tmux session '{session_name}'")
    subprocess.run(tmux_command, check=True)


def _stop_service(session_name: str) -> None:
    if _tmux_session_exists(session_name):
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=True)
        print(f"Stopped session '{session_name}'")
    else:
        print(f"Session '{session_name}' is not running. Nothing to stop.")


def main():
    """
    Manage services in tmux: launch or stop selected services.
    - Default: launch all (with YouTube before OBS).
    - --launch accepts multiple names (space-separated) and can be repeated.
    - --stop accepts multiple names and can be repeated.
    - Re-launching a running service will show a message. Use -f/--force to restart it.
    """

    parser = argparse.ArgumentParser(description="Manage EchoBot services in tmux")
    parser.add_argument(
        "--launch",
        dest="launch",
        nargs="*",
        help=f"Services to launch: {', '.join(SERVICES.keys())}. If no services specified, launches all.",
    )
    parser.add_argument(
        "--stop",
        dest="stop",
        nargs="*",
        help=f"Services to stop: {', '.join(SERVICES.keys())}. If no services specified, stops all.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force restart a service if it's already running. If no services are specified, all services are restarted.",
    )
    args = parser.parse_args()

    to_launch = args.launch
    to_stop = args.stop

    # If no arguments are provided, print the help message and exit.
    if to_launch is None and to_stop is None:
        parser.print_help()
        sys.exit(0)

    # Process stops first
    if to_stop is not None:
        services_to_stop = to_stop if to_stop else list(SERVICES.keys())
        for name in services_to_stop:
            if name in SERVICES:
                _stop_service(name)
            else:
                print(f"Unknown service '{name}'. Known: {', '.join(SERVICES.keys())}")

    # Launch services
    if to_launch is not None:
        services_to_launch = to_launch if to_launch else list(SERVICES.keys())
        for name in list(set(services_to_launch)):
            if name in SERVICES:
                _launch_service(name, SERVICES[name], args.force)
            else:
                print(f"Unknown service '{name}'. Known: {', '.join(SERVICES.keys())}")

    print("Done")


if __name__ == "__main__":
    main()
